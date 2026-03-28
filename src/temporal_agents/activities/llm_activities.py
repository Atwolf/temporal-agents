"""Activity: call an LLM with tool schemas.  Used by both supervisor and subagents."""
from __future__ import annotations

import json
import time

from temporalio import activity

from temporal_agents.config.schemas import LLMCallInput, LLMResponse, ToolCall
from temporal_agents.db.execution_store import record_transaction


def _dict_to_lc_message(msg: dict):
    """Convert a plain dict message to a LangChain message object."""
    from langchain_core.messages import (
        AIMessage,
        HumanMessage,
        SystemMessage,
        ToolMessage,
    )

    role = msg.get("role", "")
    if role == "system":
        return SystemMessage(content=msg["content"])
    elif role == "user":
        return HumanMessage(content=msg["content"])
    elif role == "assistant":
        tool_calls = msg.get("tool_calls")
        if tool_calls:
            return AIMessage(
                content=msg.get("content", ""),
                tool_calls=[
                    {
                        "id": tc["id"],
                        "name": tc["name"],
                        "args": json.loads(tc["arguments"])
                        if isinstance(tc["arguments"], str)
                        else tc["arguments"],
                    }
                    for tc in tool_calls
                ],
            )
        return AIMessage(content=msg.get("content", ""))
    elif role == "tool":
        return ToolMessage(
            content=msg["content"], tool_call_id=msg["tool_call_id"]
        )
    raise ValueError(f"Unknown role: {role}")


@activity.defn(name="call_llm")
async def call_llm(input: LLMCallInput, workflow_execution_id: str) -> LLMResponse:
    """Call an LLM with conversation history and tool schemas."""
    from langchain_core.messages import SystemMessage
    from langchain.chat_models import init_chat_model

    t0 = time.time()

    model = init_chat_model(input.model)

    # Build LangChain-format tool definitions
    lc_tools = []
    for ts in input.tool_schemas:
        lc_tools.append(
            {
                "type": "function",
                "function": {
                    "name": ts.name,
                    "description": ts.description,
                    "parameters": ts.parameters,
                },
            }
        )

    # Build message list
    lc_messages = [SystemMessage(content=input.system_prompt)]
    for msg in input.messages:
        lc_messages.append(_dict_to_lc_message(msg))

    # Invoke
    bound = model.bind_tools(lc_tools) if lc_tools else model
    response = await bound.ainvoke(lc_messages)

    duration_ms = int((time.time() - t0) * 1000)

    # Normalize
    if response.tool_calls:
        result = LLMResponse(
            tool_calls=[
                ToolCall(
                    id=tc["id"],
                    name=tc["name"],
                    arguments=json.dumps(tc["args"]),
                )
                for tc in response.tool_calls
            ]
        )
    else:
        result = LLMResponse(content=response.content)

    # Record transaction
    record_transaction(
        workflow_execution_id=workflow_execution_id,
        activity_type="llm_call",
        activity_name=input.model,
        input_summary=input.messages[-1].get("content", "")[:200] if input.messages else "",
        output_summary=(result.content or f"tool_calls: {[tc.name for tc in result.tool_calls]}")[:200],
        status="completed",
        duration_ms=duration_ms,
    )

    return result
