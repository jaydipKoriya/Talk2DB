from typing import Literal, Optional
from langgraph.graph import StateGraph, START, END
from langchain_core.language_models import BaseChatModel

from talk2db.agent.state import SQLAgentState
from talk2db.agent.nodes import SQLAgentNodes
from talk2db.database.inspector import DatabaseCatalog
from talk2db.database.executor import SandboxedExecutor
from talk2db.schema_pruning.indexer import SchemaVectorIndex
from talk2db.schema_pruning.linker import MinimalViableSchemaBuilder
from talk2db.config import MAX_RETRY_ATTEMPTS


def _route_ast(state: SQLAgentState) -> Literal["execute_query", "correct_query", "finalize_error"]:
    if state.get("ast_valid", False):
        return "execute_query"

    attempts = state.get("attempts", 0)
    max_attempts = state.get("max_attempts", MAX_RETRY_ATTEMPTS)
    return "correct_query" if attempts < max_attempts else "finalize_error"


def _route_execution(state: SQLAgentState) -> Literal["synthesize_insight", "correct_query", "finalize_error"]:
    if state.get("error") is None and state.get("dataframe") is not None:
        return "synthesize_insight"

    attempts = state.get("attempts", 0)
    max_attempts = state.get("max_attempts", MAX_RETRY_ATTEMPTS)
    return "correct_query" if attempts < max_attempts else "finalize_error"


def create_sql_agent_graph(
    llm: BaseChatModel,
    catalog: DatabaseCatalog,
    executor: SandboxedExecutor,
    dialect: str = "sqlite",
    vector_index: Optional[SchemaVectorIndex] = None,
):
    """Compiles the LangGraph pipeline with cyclic retry loops."""
    v_index = vector_index or SchemaVectorIndex(catalog)
    schema_builder = MinimalViableSchemaBuilder(catalog)

    nodes = SQLAgentNodes(
        llm=llm,
        vector_index=v_index,
        schema_builder=schema_builder,
        executor=executor,
        dialect=dialect,
    )

    workflow = StateGraph(SQLAgentState)

    workflow.add_node("retrieve_schema", nodes.retrieve_schema)
    workflow.add_node("generate_query", nodes.generate_query)
    workflow.add_node("validate_ast", nodes.validate_ast)
    workflow.add_node("execute_query", nodes.execute_query)
    workflow.add_node("correct_query", nodes.correct_query)
    workflow.add_node("synthesize_insight", nodes.synthesize_insight)
    workflow.add_node("finalize_error", nodes.finalize_error)

    workflow.add_edge(START, "retrieve_schema")
    workflow.add_edge("retrieve_schema", "generate_query")
    workflow.add_edge("generate_query", "validate_ast")

    workflow.add_conditional_edges(
        "validate_ast",
        _route_ast,
        {
            "execute_query": "execute_query",
            "correct_query": "correct_query",
            "finalize_error": "finalize_error",
        },
    )

    workflow.add_conditional_edges(
        "execute_query",
        _route_execution,
        {
            "synthesize_insight": "synthesize_insight",
            "correct_query": "correct_query",
            "finalize_error": "finalize_error",
        },
    )

    # Re-validate repaired queries
    workflow.add_edge("correct_query", "validate_ast")
    workflow.add_edge("synthesize_insight", END)
    workflow.add_edge("finalize_error", END)

    return workflow.compile()
