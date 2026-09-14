import argparse
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model

from talk2db.config import DEFAULT_DB_URI, DEFAULT_MODEL, DEFAULT_QUERY_TIMEOUT_SECONDS
from talk2db.database.connection import DatabaseConnectionManager
from talk2db.database.inspector import CatalogInspector
from talk2db.database.executor import SandboxedExecutor
from talk2db.schema_pruning.indexer import SchemaVectorIndex
from talk2db.agent.graph import create_sql_agent_graph


def run_pipeline(question: str, db_uri: str = DEFAULT_DB_URI):
    load_dotenv()
    print(f"Connecting to: {db_uri}")
    print(f"User Query: {question}\n")

    conn_mgr = DatabaseConnectionManager.from_uri(db_uri)
    conn_mgr.verify_connection()

    engine = conn_mgr.get_engine()
    catalog = CatalogInspector.inspect_engine(engine)
    print(f"Dialect: {conn_mgr.dialect_name.upper()} | Tables: {list(catalog.tables.keys())}")

    vector_index = SchemaVectorIndex(catalog)
    llm = init_chat_model(DEFAULT_MODEL)
    executor = SandboxedExecutor(engine=engine, timeout_seconds=DEFAULT_QUERY_TIMEOUT_SECONDS)

    agent = create_sql_agent_graph(
        llm=llm,
        catalog=catalog,
        executor=executor,
        dialect=conn_mgr.dialect_name,
        vector_index=vector_index,
    )

    print("Generating and running SQL...")
    result = agent.invoke({"question": question, "max_attempts": 3})

    print("\n--- Result ---")
    print(f"SQL: {result.get('query')}")
    print(f"AST Valid: {result.get('ast_valid')} | Attempts: {result.get('attempts', 0) + 1}")

    df = result.get("dataframe")
    if df is not None and not df.empty:
        print(f"\nData ({len(df)} rows):")
        print(df.to_string(index=False))

    print("\nSummary:")
    print(result.get("final_answer"))

    conn_mgr.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Talk2DB CLI Runner")
    parser.add_argument(
        "--question",
        type=str,
        default="what is the total sales",
        help="Natural language question",
    )
    parser.add_argument(
        "--uri",
        type=str,
        default=DEFAULT_DB_URI,
        help="Database URI",
    )
    args = parser.parse_args()

    run_pipeline(question=args.question, db_uri=args.uri)