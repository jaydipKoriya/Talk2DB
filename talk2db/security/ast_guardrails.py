from typing import Optional
import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError


class ASTValidationError(Exception):
    pass


FORBIDDEN_OPERATIONS = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.TruncateTable,
    exp.Alter,
    exp.Create,
    exp.Command,
    exp.Set,
)

DIALECT_MAP = {
    "sqlite": "sqlite",
    "postgresql": "postgres",
    "postgres": "postgres",
    "mysql": "mysql",
    "mariadb": "mysql",
    "oracle": "oracle",
    "mssql": "tsql",
    "snowflake": "snowflake",
    "duckdb": "duckdb",
}


class SQLASTGuardrail:
    """Validates that a SQL query is strictly a read-only SELECT statement."""

    @classmethod
    def normalize_dialect(cls, dialect_name: Optional[str]) -> str:
        if not dialect_name:
            return "sqlite"
        cleaned = dialect_name.lower().split("+")[0]
        return DIALECT_MAP.get(cleaned, cleaned)

    @classmethod
    def clean_sql(cls, sql_text: str) -> str:
        sql = sql_text.strip()
        if sql.startswith("```sql"):
            sql = sql[6:]
        elif sql.startswith("```"):
            sql = sql[3:]
        if sql.endswith("```"):
            sql = sql[:-3]
        return sql.strip()

    @classmethod
    def validate_query(cls, sql_text: str, dialect: Optional[str] = "sqlite") -> str:
        clean_sql = cls.clean_sql(sql_text)
        if not clean_sql:
            raise ASTValidationError("SQL query is empty.")

        target_dialect = cls.normalize_dialect(dialect)

        try:
            parsed = sqlglot.parse(clean_sql, read=target_dialect)
        except ParseError as e:
            raise ASTValidationError(f"SQL syntax error ({target_dialect}): {e}")
        except Exception as e:
            raise ASTValidationError(f"Could not parse SQL: {e}")

        statements = [t for t in parsed if t is not None]
        if not statements:
            raise ASTValidationError("No valid SQL statement found.")

        # Disallow semicolon chaining
        if len(statements) > 1:
            raise ASTValidationError("Multiple statements in a single query are not allowed.")

        root = statements[0]

        # Ensure top-level statement is a SELECT or UNION
        if not isinstance(root, (exp.Select, exp.Union)):
            raise ASTValidationError(f"Expected a SELECT query, got {root.key.upper()}.")

        # Walk AST to catch nested mutation operations
        for node in root.walk():
            if isinstance(node, FORBIDDEN_OPERATIONS):
                raise ASTValidationError(f"Disallowed operation found in query: {node.key.upper()}.")

        return clean_sql
