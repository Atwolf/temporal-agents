"""Child Temporal Workflow — subagent tool loop with per-tool durability."""
from __future__ import annotations

from dataclasses import asdict
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from temporal_agents.config.schemas import (
        LLMCallInput,
        LLMResponse,
        SubagentConfig,
        SubagentWorkflowInput,
        ToolExecutionInput,
        ToolResult,
    )


@workflow.defn
class SubagentWorkflow:
    """Runs a subagent's tool loop.  Each LLM call and each tool execution
    is a separate Temporal Activity — giving tool-level retry durability."""

    @workflow.run
    async def run(self, input: SubagentWorkflowInput) -> str:
        config = SubagentConfig.model_validate(input.config)
        messages: list[dict] = [{"role": "user", "content": input.task}]

        for iteration in range(config.max_iterations):
            # --- Activity: subagent LLM call ---
            # Recorded in Temporal event history.  On replay this is NOT re-invoked.
            llm_response: LLMResponse = await workflow.execute_activity(
                "call_llm",
                args=[
                    LLMCallInput(
                        model=config.model,
                        system_prompt=config.system_prompt,
                        messages=messages,
                        tool_schemas=input.tool_schemas,
                    ),
                    input.workflow_execution_id,
                ],
                start_to_close_timeout=timedelta(seconds=120),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=2),
                    backoff_coefficient=2.0,
                    maximum_attempts=3,
                ),
            )

            # If no tool calls → subagent is done
            if not llm_response.has_tool_calls:
                return llm_response.content or ""

            # Append assistant message with tool calls
            messages.append(
                {
                    "role": "assistant",
                    "tool_calls": [asdict(tc) for tc in llm_response.tool_calls],
                }
            )

            # --- Activity: execute each tool individually ---
            # If THIS fails, Temporal retries ONLY this tool.
            # The LLM call above replays from history — zero tokens.
            for tool_call in llm_response.tool_calls:
                tool_result: ToolResult = await workflow.execute_activity(
                    "execute_tool",
                    args=[
                        ToolExecutionInput(
                            tool_call=tool_call,
                            mcp_servers=[s.model_dump() for s in config.mcp_servers],
                            vector_collections=[
                                v.model_dump() for v in config.vector_collections
                            ],
                        ),
                        input.workflow_execution_id,
                    ],
                    start_to_close_timeout=timedelta(seconds=120),
                    retry_policy=RetryPolicy(
                        initial_interval=timedelta(seconds=1),
                        backoff_coefficient=2.0,
                        maximum_attempts=5,
                    ),
                )

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_result.content,
                    }
                )

        return "Max subagent iterations reached. " + messages[-1].get("content", "")
