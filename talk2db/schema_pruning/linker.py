from typing import List, Set, Optional
import tiktoken
from talk2db.database.inspector import DatabaseCatalog
from talk2db.config import MAX_CONTEXT_TOKENS


class MinimalViableSchemaBuilder:
    """Builds a compact schema with only query-relevant tables and required foreign keys."""

    def __init__(self, catalog: DatabaseCatalog, max_tokens: int = MAX_CONTEXT_TOKENS):
        self.catalog = catalog
        self.max_tokens = max_tokens
        try:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        except Exception:
            self.tokenizer = None

    def count_tokens(self, text: str) -> int:
        if self.tokenizer is not None:
            try:
                return len(self.tokenizer.encode(text))
            except Exception:
                pass
        return len(text) // 4

    def expand_fk_links(self, base_tables: List[str]) -> List[str]:
        included: Set[str] = set(base_tables)
        fk_graph = self.catalog.get_foreign_key_graph()

        # Connect two disconnected tables if a common bridge table exists
        if len(base_tables) == 2:
            t1, t2 = base_tables[0], base_tables[1]
            bridges = fk_graph.get(t1, set()).intersection(fk_graph.get(t2, set()))
            for b in bridges:
                included.add(b)

        # Include referenced foreign key target tables
        for tbl_name in list(included):
            tbl = self.catalog.get_table(tbl_name)
            if tbl:
                for fk in tbl.foreign_keys:
                    if fk.referred_table in self.catalog.tables:
                        included.add(fk.referred_table)

        return sorted(list(included))

    def build_minimal_schema(self, relevant_tables: List[str]) -> str:
        expanded = self.expand_fk_links(relevant_tables)
        schema_blocks = []
        joins = []

        for tbl_name in expanded:
            tbl = self.catalog.get_table(tbl_name)
            if not tbl:
                continue

            col_lines = []
            for col in tbl.columns:
                pk = " PRIMARY KEY" if col.primary_key else ""
                null = " NOT NULL" if not col.nullable else ""
                col_lines.append(f"  {col.name} {col.type}{pk}{null}")

            for fk in tbl.foreign_keys:
                c = ", ".join(fk.constrained_columns)
                r = ", ".join(fk.referred_columns)
                col_lines.append(f"  FOREIGN KEY ({c}) REFERENCES {fk.referred_table}({r})")
                joins.append(f"- {tbl.name}.{c} -> {fk.referred_table}.{r}")

            block = f"CREATE TABLE {tbl.name} (\n" + ",\n".join(col_lines) + "\n);"
            schema_blocks.append(block)

        ddl = "\n\n".join(schema_blocks)
        join_summary = ("\n\nJoins:\n" + "\n".join(joins)) if joins else ""
        full_schema = f"Dialect: {self.catalog.dialect.upper()}\n\n{ddl}{join_summary}"

        # If token limit is exceeded, fall back to basic table definitions
        if self.count_tokens(full_schema) > self.max_tokens:
            return self._build_strict_schema(relevant_tables)

        return full_schema

    def _build_strict_schema(self, tables: List[str]) -> str:
        blocks = []
        for tbl_name in tables:
            tbl = self.catalog.get_table(tbl_name)
            if tbl:
                cols = [f"  {c.name} {c.type}" for c in tbl.columns]
                blocks.append(f"CREATE TABLE {tbl.name} (\n" + ",\n".join(cols) + "\n);")
        return f"Dialect: {self.catalog.dialect.upper()}\n\n" + "\n\n".join(blocks)
