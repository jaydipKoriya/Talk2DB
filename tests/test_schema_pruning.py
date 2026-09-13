"""
Unit tests for Schema Pruning & Minimal Viable Schema Linker (Phase 2).
"""
from pathlib import Path
from talk2db.database.connection import DatabaseConnectionManager
from talk2db.database.inspector import CatalogInspector
from talk2db.schema_pruning.indexer import SchemaVectorIndex
from talk2db.schema_pruning.linker import MinimalViableSchemaBuilder

BASE_DIR = Path(__file__).resolve().parent.parent
DB_URI = f"sqlite:///{BASE_DIR / 'company_sales.db'}"


def test_schema_indexer_and_linker():
    mgr = DatabaseConnectionManager.from_uri(DB_URI)
    catalog = CatalogInspector.inspect_engine(mgr.get_engine())

    # Build vector index
    v_index = SchemaVectorIndex(catalog)
    results = v_index.search("How much did employee Bob sell?", top_k=2)
    assert len(results) > 0
    assert "sales" in results or "employees" in results

    # Test Minimal Viable Schema Linker
    linker = MinimalViableSchemaBuilder(catalog)
    # If we request 'sales', linker should expand to include 'employees' due to FK relation
    expanded = linker.expand_fk_links(["sales"])
    assert "sales" in expanded
    assert "employees" in expanded

    schema_doc = linker.build_minimal_schema(["sales"])
    assert "CREATE TABLE sales" in schema_doc
    assert "CREATE TABLE employees" in schema_doc
    assert "FOREIGN KEY" in schema_doc
    assert linker.count_tokens(schema_doc) > 0

    mgr.dispose()


if __name__ == "__main__":
    test_schema_indexer_and_linker()
    print("All Schema Pruning tests passed!")
