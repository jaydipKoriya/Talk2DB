"""
Unit tests for Static AST Guardrails (Phase 3).
"""
import pytest
from talk2db.security.ast_guardrails import SQLASTGuardrail, ASTValidationError


def test_valid_select_queries():
    # Simple SELECT
    q1 = "SELECT id, name FROM employees WHERE salary > 50000;"
    assert SQLASTGuardrail.validate_query(q1, "sqlite") == q1

    # Join SELECT
    q2 = """
    SELECT e.name, SUM(s.amount) as total_sales
    FROM employees e
    JOIN sales s ON e.id = s.employee_id
    GROUP BY e.name
    """
    assert "JOIN sales s" in SQLASTGuardrail.validate_query(q2, "sqlite")

    # CTE (Common Table Expression) with SELECT
    q3 = """
    WITH dept_avg AS (
        SELECT department, AVG(salary) as avg_sal
        FROM employees
        GROUP BY department
    )
    SELECT * FROM dept_avg;
    """
    assert "WITH dept_avg" in SQLASTGuardrail.validate_query(q3, "sqlite")


def test_markdown_fence_cleaning():
    fenced = "```sql\nSELECT count(*) FROM sales;\n```"
    cleaned = SQLASTGuardrail.validate_query(fenced, "sqlite")
    assert cleaned == "SELECT count(*) FROM sales;"


def test_blocked_destructive_mutations():
    forbidden_queries = [
        "DROP TABLE employees;",
        "DELETE FROM sales WHERE id = 1;",
        "UPDATE employees SET salary = salary * 2;",
        "INSERT INTO employees (id, name, department, salary) VALUES (4, 'Eve', 'HR', 50000);",
        "ALTER TABLE employees ADD COLUMN bonus REAL;",
        "TRUNCATE TABLE sales;",
    ]
    for q in forbidden_queries:
        with pytest.raises(ASTValidationError) as exc:
            SQLASTGuardrail.validate_query(q, "sqlite")
        assert len(str(exc.value)) > 0


def test_blocked_multi_statement_injection():
    injected = "SELECT * FROM employees; DROP TABLE employees;"
    with pytest.raises(ASTValidationError) as exc:
        SQLASTGuardrail.validate_query(injected, "sqlite")
    assert "multiple statements" in str(exc.value).lower()


if __name__ == "__main__":
    test_valid_select_queries()
    test_markdown_fence_cleaning()
    test_blocked_destructive_mutations()
    test_blocked_multi_statement_injection()
    print("All AST Guardrail tests passed!")
