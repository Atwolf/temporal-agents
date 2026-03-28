"""LangGraph-compatible agent graph for the Chat UI.

This wraps the Temporal workflow as a LangGraph graph so the Agent Chat UI
can connect to it via `langgraph dev`.
"""
from __future__ import annotations

import asyncio
from typing import Annotated
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from temporalio.client import Client
from typing_extensions import TypedDict

from temporal_agents.config.schemas import WorkflowInput
from temporal_agents.config.settings import settings
from temporal_agents.db.agent_store import init_agent_db
from temporal_agents.db.execution_store import init_execution_db


class ChatState(TypedDict):
    messages: Annotated[list, add_messages]


async def _run_temporal_workflow(task: str) -> str:
    """Submit a task to the Temporal AgentWorkflow and wait for the result."""
    init_agent_db()
    init_execution_db()

    client = await Client.connect(settings.temporal_address)
    wf_id = f"agent-workflow-{uuid4().hex[:12]}"
    result = await client.execute_workflow(
        "AgentWorkflow",
        WorkflowInput(task=task, config_source="db"),
        id=wf_id,
        task_queue=settings.temporal_task_queue,
    )
    return result


async def agent_node(state: ChatState) -> dict:
    """Extract the last user message, run the Temporal workflow, return result."""
    last_msg = state["messages"][-1]
    task = last_msg.content if hasattr(last_msg, "content") else str(last_msg)

    result = await _run_temporal_workflow(task)
    return {"messages": [AIMessage(content=result)]}


# Build the graph
builder = StateGraph(ChatState)
builder.add_node("agent", agent_node)
builder.add_edge(START, "agent")
builder.add_edge("agent", END)

graph = builder.compile()
