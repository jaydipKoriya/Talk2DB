from langchain_core.prompts import ChatPromptTemplate

DIALECT_GUIDANCE = {
    "sqlite": (
        "- SQLite 3 syntax\n"
        "- Dates: use strftime('%Y-%m-%d', col) or date(col)\n"
        "- Concat: use '||'\n"
        "- Use 1.0 * col for floating point division"
    ),
    "postgresql": (
        "- PostgreSQL syntax\n"
        "- Dates: use DATE_TRUNC('month', col) or TO_CHAR()\n"
        "- Concat: use '||' or CONCAT()\n"
        "- Quote case-sensitive identifiers if needed"
    ),
    "mysql": (
        "- MySQL 8 syntax\n"
        "- Dates: use DATE_FORMAT(col, '%Y-%m-%d') or YEAR(col)\n"
        "- Use backticks for reserved keywords if needed"
    ),
}

def get_dialect_guidance(dialect: str) -> str:
    cleaned = dialect.lower().split("+")[0]
    return DIALECT_GUIDANCE.get(
        cleaned,
        f"- Use standard {dialect.upper()} syntax with explicit JOIN ON conditions."
    )


SQL_GENERATION_PROMPT = ChatPromptTemplate.from_template(
    """Write a single read-only SQL SELECT query in {dialect} to answer the user request.

Dialect Notes:
{dialect_guidance}

Schema:
{minimal_schema}

Request: {question}

Output requirements:
- Return ONLY the executable SQL query (no markdown code blocks, explanations, or commentary).
- Read-only queries only: do not use INSERT, UPDATE, DELETE, DROP, or ALTER.
- Use only tables and columns from the provided schema.
"""
)


SQL_SELF_CORRECTION_PROMPT = ChatPromptTemplate.from_template(
    """The following SQL query failed against the {dialect} database. Fix the query using the error details and schema.

Dialect Notes:
{dialect_guidance}

Schema:
{minimal_schema}

Request: {question}
Failing SQL: {query}
Error: {error}

Output requirements:
- Return ONLY the corrected SQL query without markdown formatting or explanation.
- Must remain a read-only SELECT statement.
"""
)


INSIGHT_SYNTHESIS_PROMPT = ChatPromptTemplate.from_template(
    """Provide a 2-3 sentence business summary of the query results answering the user's question.

Question: {question}
SQL Query: {query}
Data Overview: {stats_overview}
Sample Rows:
{data_preview}

Highlight key figures and trends directly. Do not repeat raw SQL.
"""
)
