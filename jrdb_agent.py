"""
LangGraph Agent connected to JRDB
Purpose: Observe Flow executions and Bot errors
"""

# ======================================================
# 0. ENVIRONMENT SETUP
# ======================================================

from dotenv import load_dotenv
import os

load_dotenv()  # Load variables from .env file

# Required database environment variables
DB_SERVER = os.getenv("DB_SERVER")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# Fail fast if anything is missing
missing_vars = [
    name for name in ["DB_SERVER", "DB_NAME", "DB_USER", "DB_PASSWORD"]
    if not os.getenv(name)
]
if missing_vars:
    raise RuntimeError(
        f"Missing required environment variables: {missing_vars}. "
        "Check your .env file."
    )

# ======================================================
# 1. DATABASE CONNECTION
# ======================================================

import pyodbc
from typing import TypedDict, List, Dict, Any

JRDB_CONNECTION_STRING = (
    "Driver={ODBC Driver 17 for SQL Server};"
    f"Server={DB_SERVER};"
    f"Database={DB_NAME};"
    f"UID={DB_USER};"
    f"PWD={DB_PASSWORD};"
    "Encrypt=yes;"
    "TrustServerCertificate=yes;"
)


def run_sql(query: str, params: tuple = ()) -> List[Dict[str, Any]]:
    conn = pyodbc.connect(JRDB_CONNECTION_STRING)
    cursor = conn.cursor()
    try:
        cursor.execute(query, params)
        if cursor.description is None:
            return []
        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows]
    finally:
        cursor.close()
        conn.close()


# ======================================================
# 2. TOOLS (REAL SCHEMAS)
# ======================================================

from langchain_core.tools import tool


@tool
def get_recent_flow_executions(limit: int = 10):
    """Retrieve recent flow execution log entries."""
    return run_sql(
        """
        SELECT TOP (?)
            LogId,
            FlowName,
            RunId,
            StepName,
            LogLevel,
            Message,
            Status,
            CorrelationId,
            CreatedOn
        FROM dbo.FlowExecutionLog
        ORDER BY CreatedOn DESC
        """,
        (limit,)
    )


@tool
def get_recent_bot_errors(limit: int = 10):
    """Retrieve recent bot errors."""
    return run_sql(
        """
        SELECT TOP (?)
            BotErrorId,
            BotName,
            ErrorCode,
            ErrorMessage,
            FriendlyMessage,
            StepName,
            OccurredUtc
        FROM dbo.BotError
        ORDER BY OccurredUtc DESC
        """,
        (limit,)
    )


# ======================================================
# 3. LLM CONFIG
# ======================================================

from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0
).bind_tools(
    [
        get_recent_flow_executions,
        get_recent_bot_errors,
    ]
)


# ======================================================
# 4. LANGGRAPH
# ======================================================

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode


class AgentState(TypedDict):
    messages: list


def agent_node(state: AgentState):
    response = llm.invoke(state["messages"])
    return {"messages": state["messages"] + [response]}


tool_node = ToolNode(
    [
        get_recent_flow_executions,
        get_recent_bot_errors,
    ]
)

graph = StateGraph(AgentState)
graph.add_node("agent", agent_node)
graph.add_node("tools", tool_node)
graph.set_entry_point("agent")
graph.add_edge("agent", "tools")
graph.add_edge("tools", "agent")
graph.add_edge("agent", END)

app = graph.compile()


# ======================================================
# 5. RUN
# ======================================================

if __name__ == "__main__":

    print("✅ Testing SQL tools...\n")

    print("Recent flow executions:")
    print(get_recent_flow_executions.invoke({"limit": 5}))

    print("\nRecent bot errors:")
    print(get_recent_bot_errors.invoke({"limit": 5}))

    print("\n✅ Running LangGraph agent...\n")

    result = app.invoke(
        {
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an observability assistant for JRDB. "
                        "Summarize flow activity and bot errors using real data only. "
                        "Prefer FriendlyMessage when explaining errors."
                    )
                },
                {
                    "role": "user",
                    "content": (
                        "Summarize recent flow executions and any bot errors."
                    )
                }
            ]
        }
    )

    print("\n--- FINAL ANSWER ---")
    print(result["messages"][-1].content)