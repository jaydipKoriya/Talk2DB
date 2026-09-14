"""
Talk2DB Configuration module.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# LLM Model Configuration
DEFAULT_MODEL = os.getenv("TALK2DB_MODEL", "google_genai:gemini-3.6-flash")
DEFAULT_EMBEDDING_MODEL = os.getenv("TALK2DB_EMBEDDING_MODEL", "models/gemini-embedding-001")

# Security & Sandboxing
DEFAULT_QUERY_TIMEOUT_SECONDS = int(os.getenv("TALK2DB_QUERY_TIMEOUT", "10"))
MAX_RETRY_ATTEMPTS = int(os.getenv("TALK2DB_MAX_RETRIES", "3"))
MAX_CONTEXT_TOKENS = int(os.getenv("TALK2DB_MAX_TOKENS", "4000"))

# Database Defaults
DEFAULT_SQLITE_PATH = str(BASE_DIR / "company_sales.db")
DEFAULT_DB_URI = os.getenv("TALK2DB_DATABASE_URI", f"sqlite:///{DEFAULT_SQLITE_PATH}")

# Telemetry
LANGCHAIN_TRACING_V2 = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
