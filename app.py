from typing import Optional, TypedDict
from langchain_community.utilities import SQLDatabase
from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, START, END
from langchain.agents import create_agent
from dotenv import load_dotenv

load_dotenv()
db = SQLDatabase.from_uri("sqlite:///company_sales.db")

class SQLAgentState(TypedDict):
    question: str
    query: str
    result: Optional[str]
    error: Optional[str]
    attempts: int
    final_answer: Optional[str]



llm = init_chat_model("google_genai:gemini-3.6-flash")

def extract_text(content) -> str:
    """Safely extracts a string from either str or list-based AIMessage content."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part if isinstance(part, str) else part.get("text", "") 
            for part in content
        )
    return str(content)

def generate_query(state: SQLAgentState):
    schema = db.get_table_info()
    prompt = ChatPromptTemplate.from_template(
        "Based on the SQLite schema below, write a raw SQL query that answers the question.\n"
        "Do NOT wrap the code in Markdown formatting (no ```sql fences).\n\n"
        "Schema:\n{schema}\n\n"
        "Question: {question}"
    )
    chain = prompt | llm
    response = chain.invoke({"schema": schema, "question": state["question"]})
    raw_content = extract_text(response.content)
    clean_sql = raw_content.strip().replace("```sql", "").replace("```", "")
    return {"query": clean_sql, "error": None, "attempts": 0}

def execute_query(state: SQLAgentState):
    try:
        raw_result = db.run(state["query"])
        return {"result": raw_result, "error": None}
    except Exception as exc:
        # Capture the exact database error traceback
        return {"error": str(exc), "attempts": state["attempts"] + 1}


def correct_query(state: SQLAgentState):
    schema = db.get_table_info()
    prompt = ChatPromptTemplate.from_template(
        "You previously wrote an invalid SQLite query that caused an execution error.\n"
        "Diagnose the error using the schema and rewrite the query.\n"
        "Return ONLY the fixed SQL query without Markdown blocks.\n\n"
        "Schema:\n{schema}\n\n"
        "User Question: {question}\n\n"
        "Faulty Query: {query}\n\n"
        "Database Error Message: {error}"
    )
    chain = prompt | llm
    response = chain.invoke({
        "schema": schema,
        "question": state["question"],
        "query": state["query"],
        "error": state["error"]
    })
    raw_content = extract_text(response.content)
    clean_sql = raw_content.strip().replace("```sql", "").replace("```", "").strip()
    
    return {"query": clean_sql}


def generate_answer(state: SQLAgentState):
    if state["error"]:
        answer = f"Failed to execute query after {state['attempts']} attempts. Last error: {state['error']}"
    else:
        prompt = ChatPromptTemplate.from_template(
            "Summarize the database query and output into a direct response.\n\n"
            "Question: {question}\n"
            "SQL: {query}\n"
            "Result: {result}"
        )
        chain = prompt | llm
        response = chain.invoke(state)
        answer = extract_text(response.content)
    return {"final_answer": answer}

def routing_logic(state: SQLAgentState) -> str:
    # If there's an error and retries are under the threshold, loop back
    if state["error"] is not None:
        if state["attempts"] < 3:
            return "correct_query"
        return "generate_answer"
    return "generate_answer"

workflow = StateGraph(SQLAgentState)

# Register Nodes
workflow.add_node("generate_query", generate_query)
workflow.add_node("execute_query", execute_query)
workflow.add_node("correct_query", correct_query)
workflow.add_node("generate_answer", generate_answer)

# Connect Edges
workflow.add_edge(START, "generate_query")
workflow.add_edge("generate_query", "execute_query")

# Conditional Branching
workflow.add_conditional_edges(
    "execute_query",
    routing_logic,
    {
        "correct_query": "correct_query",
        "generate_answer": "generate_answer"
    }
)

# Self-healing loop: push repaired query back to execution
workflow.add_edge("correct_query", "execute_query")
workflow.add_edge("generate_answer", END)

app = workflow.compile()


query_input = {
    "question": "what is the totale sales"
}

result = app.invoke(query_input)

print("--- Execution Summary ---")
print(f"Executed SQL: {result['query']}")
print(f"Total Attempts: {result['attempts'] + 1}")
print(f"Final Answer:\n{result['final_answer']}")