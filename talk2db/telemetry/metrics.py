"""
Telemetry and Tracing for SQL Agent Execution.
Tracks retrieval metrics, AST validation status, execution latency, retry loops, and token overhead.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import time


@dataclass
class ExecutionMetrics:
    question: str
    dialect: str
    total_duration_ms: float = 0.0
    retrieval_duration_ms: float = 0.0
    generation_duration_ms: float = 0.0
    execution_duration_ms: float = 0.0
    synthesis_duration_ms: float = 0.0
    attempts: int = 0
    ast_valid: bool = False
    execution_success: bool = False
    retrieved_tables: List[str] = field(default_factory=list)
    schema_tokens_estimate: int = 0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question": self.question,
            "dialect": self.dialect,
            "total_duration_ms": round(self.total_duration_ms, 2),
            "retrieval_duration_ms": round(self.retrieval_duration_ms, 2),
            "generation_duration_ms": round(self.generation_duration_ms, 2),
            "execution_duration_ms": round(self.execution_duration_ms, 2),
            "synthesis_duration_ms": round(self.synthesis_duration_ms, 2),
            "attempts": self.attempts,
            "ast_valid": self.ast_valid,
            "execution_success": self.execution_success,
            "retrieved_tables": self.retrieved_tables,
            "schema_tokens_estimate": self.schema_tokens_estimate,
            "errors": self.errors,
        }


class AgentTelemetry:
    """
    Session-level telemetry collector.
    """

    def __init__(self):
        self.history: List[ExecutionMetrics] = []

    def record(self, metrics: ExecutionMetrics) -> None:
        self.history.append(metrics)

    def get_latest(self) -> Optional[ExecutionMetrics]:
        return self.history[-1] if self.history else None
