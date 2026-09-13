# Talk2DB

Talk2DB is an autonomous Text-to-SQL system that translates natural language requests into SQL, executes them safely against your database, and synthesizes tabular results into plain-language business takeaways.

It supports MySQL, PostgreSQL, and SQLite out of the box.

---

## Key Features

- **Dynamic Connection & Catalog Reflection**: Transient connection pooling via SQLAlchemy with automatic table and foreign key schema extraction.
- **Semantic Schema Pruning**: Indexes table descriptors in an ephemeral ChromaDB collection to retrieve only query-relevant tables and foreign keys, protecting LLM context limits.
- **AST Safety Guardrails**: Uses `sqlglot` to parse generated queries and enforce read-only `SELECT` statements, actively blocking destructive mutations (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`) and SQL injection attacks.
- **Cyclic Error Recovery**: Orchestrated with LangGraph to automatically capture runtime database errors and repair faulty queries up to 3 attempts.
- **Tabular Extraction & Synthesis**: Parses records into pandas DataFrames and synthesizes an executive summary answering the user's question.
- **Web UI & CLI**: Run interactively via Streamlit or headless from the command line.

---

## Quick Start

### 1. Installation

```bash
python -m venv .venv
.\.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/macOS

pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file with your Gemini API key:
```env
GEMINI_API_KEY=your_gemini_api_key
TALK2DB_MODEL=google_genai:gemini-3.6-flash
TALK2DB_EMBEDDING_MODEL=models/gemini-embedding-001
```

### 3. Usage

**Interactive Web UI (Streamlit):**
```bash
streamlit run talk2db/ui/streamlit_app.py
```

**CLI Runner:**
```bash
# Query default SQLite sales database
python app.py --question "What is the total sales amount per department?"

# Query a live MySQL or PostgreSQL database
python app.py --uri "mysql+pymysql://root:password@localhost:3306/mydb" --question "Top 5 selling products"
```

**Run Tests:**
```bash
pytest tests/ -v
```

---

## Docker

```bash
docker build -t talk2db:latest .
docker run -p 8501:8501 --env-file .env talk2db:latest
```