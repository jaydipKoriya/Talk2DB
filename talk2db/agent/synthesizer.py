from typing import Optional
import pandas as pd
from langchain_core.language_models import BaseChatModel

from talk2db.agent.prompts import INSIGHT_SYNTHESIS_PROMPT


def extract_message_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(p if isinstance(p, str) else p.get("text", "") for p in content)
    return str(content)


class InsightSynthesizer:
    def __init__(self, llm: BaseChatModel):
        self.llm = llm

    def _format_stats(self, df: pd.DataFrame) -> str:
        lines = [f"Rows: {len(df)}", f"Columns: {', '.join(df.columns)}"]
        numeric = df.select_dtypes(include=["number"]).columns
        for col in numeric:
            lines.append(f"{col}: min={df[col].min()}, max={df[col].max()}, sum={df[col].sum():.2f}")
        return "\n".join(lines)

    def synthesize(self, question: str, query: str, df: Optional[pd.DataFrame]) -> str:
        if df is None or df.empty:
            return f"Query returned 0 rows for question: '{question}'."

        stats = self._format_stats(df)
        preview = df.head(5).to_string(index=False)

        chain = INSIGHT_SYNTHESIS_PROMPT | self.llm
        response = chain.invoke({
            "question": question,
            "query": query,
            "stats_overview": stats,
            "data_preview": preview,
        })
        return extract_message_text(response.content).strip()
