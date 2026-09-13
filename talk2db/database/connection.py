from typing import Optional, Dict, Any
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, URL
from sqlalchemy.pool import QueuePool, NullPool, StaticPool


class DatabaseConnectionManager:
    """Manages transient database engine lifecycles and connection pools."""

    def __init__(self, uri: Optional[str] = None, **kwargs: Any):
        self._raw_uri = uri
        self._connection_params = kwargs
        self._engine: Optional[Engine] = None

    @classmethod
    def from_uri(cls, uri: str) -> "DatabaseConnectionManager":
        return cls(uri=uri)

    @classmethod
    def from_credentials(
        cls,
        dialect: str,
        host: str,
        port: int,
        database: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        driver: Optional[str] = None,
        extra_query: Optional[Dict[str, str]] = None,
    ) -> "DatabaseConnectionManager":
        drivername = f"{dialect}+{driver}" if driver else dialect
        url = URL.create(
            drivername=drivername,
            username=username,
            password=password,
            host=host,
            port=port,
            database=database,
            query=extra_query or {},
        )
        return cls(uri=url.render_as_string(hide_password=False))

    def get_engine(self) -> Engine:
        if self._engine is not None:
            return self._engine

        if not self._raw_uri:
            raise ValueError("Database URI or connection parameters must be provided.")

        is_sqlite = self._raw_uri.startswith("sqlite")

        if is_sqlite:
            # Prevent thread-safety warnings for SQLite in web apps
            poolclass = StaticPool if ":memory:" in self._raw_uri else NullPool
            self._engine = create_engine(
                self._raw_uri,
                connect_args={"check_same_thread": False},
                poolclass=poolclass,
            )
        else:
            # Conservative pool size so user queries don't exhaust DB server limits
            self._engine = create_engine(
                self._raw_uri,
                pool_size=2,
                max_overflow=0,
                pool_timeout=10,
                pool_recycle=300,
                poolclass=QueuePool,
            )

        return self._engine

    def verify_connection(self) -> bool:
        """Runs a quick SELECT 1 check to verify reachability."""
        engine = self.get_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1;")).scalar()
            return result == 1

    @property
    def dialect_name(self) -> str:
        return self.get_engine().dialect.name

    def dispose(self) -> None:
        """Closes open socket pools."""
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None

    def __enter__(self) -> "DatabaseConnectionManager":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.dispose()
