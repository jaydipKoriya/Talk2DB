from dataclasses import dataclass
from typing import Optional, List
import time
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine


@dataclass
class ExecutionResult:
    success: bool
    sql: str
    dataframe: Optional[pd.DataFrame] = None
    row_count: int = 0
    column_names: List[str] = None
    execution_time_ms: float = 0.0
    error_message: Optional[str] = None


class SandboxedExecutor:
    """Executes read-only SQL queries with timeouts and returns a pandas DataFrame."""

    def __init__(self, engine: Engine, timeout_seconds: int = 10):
        self.engine = engine
        self.timeout_seconds = timeout_seconds

    def execute(self, sql_query: str) -> ExecutionResult:
        start_time = time.perf_counter()

        try:
            with self.engine.connect() as conn:
                dialect = self.engine.dialect.name

                # Set dialect-specific statement timeouts
                if dialect == "postgresql":
                    conn.execute(text(f"SET statement_timeout = {int(self.timeout_seconds * 1000)};"))
                elif dialect == "mysql":
                    conn.execute(text(f"SET max_execution_time = {int(self.timeout_seconds * 1000)};"))
                elif dialect == "sqlite":
                    start_tick = time.time()
                    raw_conn = conn.connection
                    if hasattr(raw_conn, "set_progress_handler"):
                        raw_conn.set_progress_handler(
                            lambda: 1 if (time.time() - start_tick > self.timeout_seconds) else 0,
                            10000,
                        )

                cursor = conn.execute(text(sql_query))
                columns = list(cursor.keys())
                rows = cursor.fetchall()

                # Clean up SQLite progress handler
                if dialect == "sqlite":
                    raw_conn = conn.connection
                    if hasattr(raw_conn, "set_progress_handler"):
                        raw_conn.set_progress_handler(None, 0)

                df = pd.DataFrame(rows, columns=columns)
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0

                return ExecutionResult(
                    success=True,
                    sql=sql_query,
                    dataframe=df,
                    row_count=len(df),
                    column_names=columns,
                    execution_time_ms=elapsed_ms,
                )

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return ExecutionResult(
                success=False,
                sql=sql_query,
                execution_time_ms=elapsed_ms,
                error_message=str(e).strip(),
            )
