from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from sqlalchemy import inspect
from sqlalchemy.engine import Engine


@dataclass
class ColumnMetadata:
    name: str
    type: str
    nullable: bool = True
    primary_key: bool = False
    comment: Optional[str] = None


@dataclass
class ForeignKeyRelation:
    constrained_columns: List[str]
    referred_table: str
    referred_columns: List[str]


@dataclass
class TableMetadata:
    name: str
    columns: List[ColumnMetadata] = field(default_factory=list)
    primary_keys: List[str] = field(default_factory=list)
    foreign_keys: List[ForeignKeyRelation] = field(default_factory=list)
    comment: Optional[str] = None

    def to_descriptor(self) -> str:
        cols_summary = []
        for col in self.columns:
            pk = " [PK]" if col.primary_key else ""
            cols_summary.append(f"{col.name} ({col.type}{pk})")

        fks_summary = []
        for fk in self.foreign_keys:
            c = ", ".join(fk.constrained_columns)
            r = ", ".join(fk.referred_columns)
            fks_summary.append(f"FK: {self.name}({c}) -> {fk.referred_table}({r})")

        fks_text = f" | {'; '.join(fks_summary)}" if fks_summary else ""
        comment_text = f" // {self.comment}" if self.comment else ""
        return f"Table: {self.name}{comment_text}\nColumns: {', '.join(cols_summary)}{fks_text}"


@dataclass
class DatabaseCatalog:
    dialect: str
    tables: Dict[str, TableMetadata] = field(default_factory=dict)

    def get_table(self, name: str) -> Optional[TableMetadata]:
        return self.tables.get(name)

    def list_table_names(self) -> List[str]:
        return list(self.tables.keys())

    def get_foreign_key_graph(self) -> Dict[str, Set[str]]:
        graph: Dict[str, Set[str]] = {t: set() for t in self.tables}
        for name, table in self.tables.items():
            for fk in table.foreign_keys:
                if fk.referred_table in graph:
                    graph[name].add(fk.referred_table)
                    graph[fk.referred_table].add(name)
        return graph


class CatalogInspector:
    @classmethod
    def inspect_engine(cls, engine: Engine) -> DatabaseCatalog:
        inspector = inspect(engine)
        catalog = DatabaseCatalog(dialect=engine.dialect.name)

        for table_name in inspector.get_table_names():
            pk_info = inspector.get_pk_constraint(table_name) or {}
            pk_cols = set(pk_info.get("constrained_columns") or [])

            columns = [
                ColumnMetadata(
                    name=col["name"],
                    type=str(col["type"]),
                    nullable=col.get("nullable", True),
                    primary_key=(col["name"] in pk_cols),
                    comment=col.get("comment"),
                )
                for col in inspector.get_columns(table_name)
            ]

            foreign_keys = []
            for fk in inspector.get_foreign_keys(table_name):
                ref_table = fk.get("referred_table")
                c_cols = fk.get("constrained_columns", [])
                r_cols = fk.get("referred_columns", [])
                if ref_table and c_cols:
                    foreign_keys.append(
                        ForeignKeyRelation(
                            constrained_columns=c_cols,
                            referred_table=ref_table,
                            referred_columns=r_cols,
                        )
                    )

            comment = None
            try:
                c_info = inspector.get_table_comment(table_name)
                if isinstance(c_info, dict):
                    comment = c_info.get("text")
            except Exception:
                pass

            catalog.tables[table_name] = TableMetadata(
                name=table_name,
                columns=columns,
                primary_keys=list(pk_cols),
                foreign_keys=foreign_keys,
                comment=comment,
            )

        return catalog
