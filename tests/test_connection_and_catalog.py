"""
Unit tests for Dynamic Connection & Metadata Reflection (Phase 1).
"""
import os
from pathlib import Path
from talk2db.database.connection import DatabaseConnectionManager
from talk2db.database.inspector import CatalogInspector
from talk2db.database.executor import SandboxedExecutor

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = str(BASE_DIR / "company_sales.db")
DB_URI = f"sqlite:///{DB_PATH}"


def test_handshake_and_reflection():
    assert os.path.exists(DB_PATH), f"Database file {DB_PATH} must exist"

    mgr = DatabaseConnectionManager.from_uri(DB_URI)
    assert mgr.verify_connection() is True
    assert mgr.dialect_name == "sqlite"

    engine = mgr.get_engine()
    catalog = CatalogInspector.inspect_engine(engine)

    assert "employees" in catalog.tables
    assert "sales" in catalog.tables

    # Check employees columns
    emp = catalog.tables["employees"]
    emp_cols = {c.name for c in emp.columns}
    assert {"id", "name", "department", "salary"}.issubset(emp_cols)
    assert "id" in emp.primary_keys

    # Check sales foreign keys
    sales = catalog.tables["sales"]
    assert len(sales.foreign_keys) == 1
    fk = sales.foreign_keys[0]
    assert fk.referred_table == "employees"
    assert fk.constrained_columns == ["employee_id"]
    assert fk.referred_columns == ["id"]

    # Test execution
    executor = SandboxedExecutor(engine=engine, timeout_seconds=5)
    res = executor.execute("SELECT count(*) as cnt FROM employees;")
    assert res.success is True
    assert res.dataframe is not None
    assert res.dataframe["cnt"].iloc[0] == 3

    # Dispose
    mgr.dispose()
    assert mgr._engine is None


def test_sandboxed_executor_error_handling():
    mgr = DatabaseConnectionManager.from_uri(DB_URI)
    executor = SandboxedExecutor(engine=mgr.get_engine())
    
    # Intentionally invalid query
    res = executor.execute("SELECT non_existent_col FROM employees;")
    assert res.success is False
    assert "no such column" in res.error_message.lower()
    
    mgr.dispose()


if __name__ == "__main__":
    test_handshake_and_reflection()
    test_sandboxed_executor_error_handling()
    print("All Connection & Catalog tests passed!")
