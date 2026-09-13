"""
State definitions for the LangGraph Text-to-SQL Agent.
"""
from typing import Optional, List, Dict, Any, TypedDict
import pandas as pd


class SQLAgentState(TypedDict, total=False):
    question: str
    dialect: str
    relevant_tables: List[str]
    minimal_schema: str
    query: str
    ast_valid: bool
    ast_error: Optional[str]
    execution_error: Optional[str]
    error: Optional[str]
    dataframe: Optional[pd.DataFrame]
    column_names: List[str]
    row_count: int
    attempts: int
    max_attempts: int
    final_answer: Optional[str]
    telemetry: Dict[str, Any]
