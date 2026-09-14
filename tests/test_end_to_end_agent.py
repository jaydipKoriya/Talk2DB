"""
End-to-End Test for the LangGraph Text-to-SQL Agent with Self-Correction (Phases 1-5).
"""
import pytest
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model

from talk2db.config import DEFAULT_DB_URI, DEFAULT_MODEL
from talk2db.database.connection import DatabaseConnectionManager
from talk2db.database.inspector import CatalogInspector
from talk2db.database.executor import SandboxedExecutor
from talk2db.schema_pruning.indexer import SchemaVectorIndex
from talk2db.agent.graph import create_sql_agent_graph

load_dotenv()


def test_agent_end_to_end_execution():
    conn_mgr = DatabaseConnectionManager.from_uri(DEFAULT_DB_URI)
    conn_mgr.verify_connection()
    engine = conn_mgr.get_engine()
    catalog = CatalogInspector.inspect_engine(engine)

    v_index = SchemaVectorIndex(catalog)
    llm = init_chat_model(DEFAULT_MODEL)
    executor = SandboxedExecutor(engine=engine, timeout_seconds=10)

    graph = create_sql_agent_graph(
        llm=llm,
        catalog=catalog,
        executor=executor,
        dialect=conn_mgr.dialect_name,
        vector_index=v_index,
    )

    # Ask an analytical question that requires table join
    question = "What is the total sales amount achieved by each employee? List their name and total sales."
    result = graph.invoke({
        "question": question,
        "max_attempts": 3,
    })

    assert result["ast_valid"] is True
    assert result["query"] is not None
    assert "SELECT" in result["query"].upper()
    assert result["dataframe"] is not None
    assert len(result["dataframe"]) > 0
    assert result["final_answer"] is not None
    assert len(result["final_answer"]) > 10

    conn_mgr.dispose()


if __name__ == "__main__":
    test_agent_end_to_end_execution()
    print("End-to-End Agent test passed!")
