"""Activity: execute a single tool call (MCP or vector search).

If this activity fails, Temporal retries ONLY this tool execution.
The LLM call that decided to use this tool replays from event history.
"""
from __future__ import annotations

import json
import time

from temporalio import activity

from temporal_agents.config.schemas import (
    MCPServerConfig,
    ToolExecutionInput,
    ToolResult,
    VectorCollectionConfig,
)
from temporal_agents.db.execution_store import record_transaction
from temporal_agents.tools.mcp_loader import execute_mcp_tool
from temporal_agents.tools.vector_search import execute_vector_search


@activity.defn(name="execute_tool")
async def execute_tool(
    input: ToolExecutionInput, workflow_execution_id: str
) -> ToolResult:
    """Execute a single tool call.  Retried independently by Temporal."""
    tool_name = input.tool_call.name
    tool_args = json.loads(input.tool_call.arguments)
    t0 = time.time()

    # Check vector search tools first
    for vc_dict in input.vector_collections:
        vc = VectorCollectionConfig.model_validate(vc_dict)
        if tool_name == f"search_{vc.collection_name}":
            content = await execute_vector_search(vc, tool_args.get("query", ""))
            duration_ms = int((time.time() - t0) * 1000)
            record_transaction(
                workflow_execution_id=workflow_execution_id,
                activity_type="tool_execution",
                activity_name=tool_name,
                input_summary=json.dumps(tool_args)[:200],
                output_summary=content[:200],
                status="completed",
                duration_ms=duration_ms,
            )
            return ToolResult(
                tool_call_id=input.tool_call.id,
                name=tool_name,
                content=content,
            )

    # Otherwise, execute as MCP tool
    mcp_configs = [MCPServerConfig.model_validate(s) for s in input.mcp_servers]
    content = await execute_mcp_tool(mcp_configs, tool_name, tool_args)

    duration_ms = int((time.time() - t0) * 1000)
    record_transaction(
        workflow_execution_id=workflow_execution_id,
        activity_type="tool_execution",
        activity_name=tool_name,
        input_summary=json.dumps(tool_args)[:200],
        output_summary=content[:200],
        status="completed",
        duration_ms=duration_ms,
    )

    return ToolResult(
        tool_call_id=input.tool_call.id,
        name=tool_name,
        content=content,
    )
