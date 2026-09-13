from typing import Dict, Any
import time
from langchain_core.language_models import BaseChatModel

from talk2db.agent.state import SQLAgentState
from talk2db.agent.prompts import (
    SQL_GENERATION_PROMPT,
    SQL_SELF_CORRECTION_PROMPT,
    get_dialect_guidance,
)
from talk2db.agent.synthesizer import InsightSynthesizer, extract_message_text
from talk2db.security.ast_guardrails import SQLASTGuardrail, ASTValidationError
from talk2db.schema_pruning.indexer import SchemaVectorIndex
from talk2db.schema_pruning.linker import MinimalViableSchemaBuilder
from talk2db.database.executor import SandboxedExecutor


class SQLAgentNodes:
    def __init__(
        self,
        llm: BaseChatModel,
        vector_index: SchemaVectorIndex,
        schema_builder: MinimalViableSchemaBuilder,
        executor: SandboxedExecutor,
        dialect: str = "sqlite",
    ):
        self.llm = llm
        self.vector_index = vector_index
        self.schema_builder = schema_builder
        self.executor = executor
        self.dialect = dialect
        self.synthesizer = InsightSynthesizer(llm)

    def retrieve_schema(self, state: SQLAgentState) -> Dict[str, Any]:
        t0 = time.perf_counter()
        relevant_tables = self.vector_index.search(state["question"], top_k=4)
        minimal_schema = self.schema_builder.build_minimal_schema(relevant_tables)
        duration_ms = (time.perf_counter() - t0) * 1000.0

        telemetry = state.get("telemetry", {})
        telemetry["retrieval_duration_ms"] = duration_ms
        telemetry["retrieved_tables"] = relevant_tables
        telemetry["schema_tokens_estimate"] = self.schema_builder.count_tokens(minimal_schema)

        return {
            "dialect": self.dialect,
            "relevant_tables": relevant_tables,
            "minimal_schema": minimal_schema,
            "attempts": 0,
            "max_attempts": state.get("max_attempts", 3),
            "telemetry": telemetry,
        }

    def generate_query(self, state: SQLAgentState) -> Dict[str, Any]:
        t0 = time.perf_counter()
        chain = SQL_GENERATION_PROMPT | self.llm
        response = chain.invoke({
            "dialect": self.dialect,
            "dialect_guidance": get_dialect_guidance(self.dialect),
            "minimal_schema": state["minimal_schema"],
            "question": state["question"],
        })

        sql = SQLASTGuardrail.clean_sql(extract_message_text(response.content))
        duration_ms = (time.perf_counter() - t0) * 1000.0

        telemetry = state.get("telemetry", {})
        telemetry["generation_duration_ms"] = telemetry.get("generation_duration_ms", 0.0) + duration_ms

        return {
            "query": sql,
            "error": None,
            "ast_error": None,
            "execution_error": None,
            "telemetry": telemetry,
        }

    def validate_ast(self, state: SQLAgentState) -> Dict[str, Any]:
        telemetry = state.get("telemetry", {})
        try:
            clean_sql = SQLASTGuardrail.validate_query(state["query"], dialect=self.dialect)
            telemetry["ast_valid"] = True
            return {
                "query": clean_sql,
                "ast_valid": True,
                "ast_error": None,
                "error": None,
                "telemetry": telemetry,
            }
        except ASTValidationError as err:
            telemetry["ast_valid"] = False
            telemetry.setdefault("errors", []).append(f"AST Error: {err}")
            return {
                "ast_valid": False,
                "ast_error": str(err),
                "error": f"AST validation failed: {err}",
                "attempts": state.get("attempts", 0) + 1,
                "telemetry": telemetry,
            }

    def execute_query(self, state: SQLAgentState) -> Dict[str, Any]:
        result = self.executor.execute(state["query"])
        telemetry = state.get("telemetry", {})
        telemetry["execution_duration_ms"] = telemetry.get("execution_duration_ms", 0.0) + result.execution_time_ms

        if result.success:
            telemetry["execution_success"] = True
            return {
                "dataframe": result.dataframe,
                "column_names": result.column_names,
                "row_count": result.row_count,
                "error": None,
                "execution_error": None,
                "telemetry": telemetry,
            }

        telemetry["execution_success"] = False
        telemetry.setdefault("errors", []).append(f"DB Error: {result.error_message}")
        return {
            "dataframe": None,
            "column_names": [],
            "row_count": 0,
            "error": f"Database execution error: {result.error_message}",
            "execution_error": result.error_message,
            "attempts": state.get("attempts", 0) + 1,
            "telemetry": telemetry,
        }

    def correct_query(self, state: SQLAgentState) -> Dict[str, Any]:
        t0 = time.perf_counter()
        chain = SQL_SELF_CORRECTION_PROMPT | self.llm
        response = chain.invoke({
            "dialect": self.dialect,
            "dialect_guidance": get_dialect_guidance(self.dialect),
            "minimal_schema": state["minimal_schema"],
            "question": state["question"],
            "query": state["query"],
            "error": state["error"],
        })

        repaired_sql = SQLASTGuardrail.clean_sql(extract_message_text(response.content))
        duration_ms = (time.perf_counter() - t0) * 1000.0

        telemetry = state.get("telemetry", {})
        telemetry["generation_duration_ms"] = telemetry.get("generation_duration_ms", 0.0) + duration_ms

        return {
            "query": repaired_sql,
            "error": None,
            "ast_error": None,
            "execution_error": None,
            "telemetry": telemetry,
        }

    def synthesize_insight(self, state: SQLAgentState) -> Dict[str, Any]:
        t0 = time.perf_counter()
        summary = self.synthesizer.synthesize(
            question=state["question"],
            query=state["query"],
            df=state.get("dataframe"),
        )
        duration_ms = (time.perf_counter() - t0) * 1000.0

        telemetry = state.get("telemetry", {})
        telemetry["synthesis_duration_ms"] = duration_ms

        return {
            "final_answer": summary,
            "telemetry": telemetry,
        }

    def finalize_error(self, state: SQLAgentState) -> Dict[str, Any]:
        return {
            "final_answer": f"Query could not be executed after {state.get('attempts', 0)} attempts.\nError: {state.get('error')}"
        }
