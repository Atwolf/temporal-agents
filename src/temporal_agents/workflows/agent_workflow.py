"""Top-level Temporal Workflow — supervisor agentic loop."""
from __future__ import annotations

import json
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
        ToolSchema,
        WorkflowConfig,
        WorkflowInput,
    )


@workflow.defn
class AgentWorkflow:
    """Supervisor loop: LLM decides → dispatch child SubagentWorkflow → repeat."""

    @workflow.run
    async def run(self, input: WorkflowInput) -> str:
        wf_id = workflow.info().workflow_id

        # Step 1 — Load agent configs from DB or YAML
        config: WorkflowConfig = await workflow.execute_activity(
            "load_agent_configs",
            args=[input.config_source],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )

        # Step 2 — Discover tool schemas for each subagent
        subagent_tool_schemas: dict[str, list[ToolSchema]] = {}
        for sa in config.subagents:
            schemas: list[ToolSchema] = await workflow.execute_activity(
                "load_tool_schemas",
                args=[sa.model_dump()],
                start_to_close_timeout=timedelta(seconds=60),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
            subagent_tool_schemas[sa.name] = schemas

        # Step 3 — Record workflow start
        await workflow.execute_activity(
            "record_workflow_start_activity",
            args=[wf_id, input.task, config.model_dump()],
            start_to_close_timeout=timedelta(seconds=10),
        )

        # Step 4 — Supervisor agentic loop
        messages: list[dict] = [{"role": "user", "content": input.task}]

        # Build supervisor "tools" — one per subagent
        supervisor_tool_schemas = [
            ToolSchema(
                name=sa.name,
                description=sa.description,
                parameters={
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "The task to delegate to this subagent",
                        }
                    },
                    "required": ["task"],
                },
            )
            for sa in config.subagents
        ]

        final_answer = ""
        for round_num in range(config.supervisor.max_rounds):
            # --- Activity: Supervisor LLM call ---
            llm_response: LLMResponse = await workflow.execute_activity(
                "call_llm",
                args=[
                    LLMCallInput(
                        model=config.supervisor.model,
                        system_prompt=config.supervisor.system_prompt,
                        messages=messages,
                        tool_schemas=supervisor_tool_schemas,
                    ),
                    wf_id,
                ],
                start_to_close_timeout=timedelta(seconds=120),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=2),
                    backoff_coefficient=2.0,
                    maximum_attempts=3,
                ),
            )

            # No tool calls → supervisor is done
            if not llm_response.has_tool_calls:
                final_answer = llm_response.content or ""
                break

            # Append assistant message with tool calls
            messages.append(
                {
                    "role": "assistant",
                    "tool_calls": [asdict(tc) for tc in llm_response.tool_calls],
                }
            )

            # Execute each subagent invocation
            for tool_call in llm_response.tool_calls:
                subagent_name = tool_call.name
                task_args = json.loads(tool_call.arguments)
                subagent_config = next(
                    sa for sa in config.subagents if sa.name == subagent_name
                )

                # --- Child Workflow: subagent with tool-level durability ---
                subagent_result: str = await workflow.execute_child_workflow(
                    "SubagentWorkflow",
                    SubagentWorkflowInput(
                        config=subagent_config.model_dump(),
                        task=task_args["task"],
                        tool_schemas=subagent_tool_schemas[subagent_name],
                        workflow_execution_id=wf_id,
                    ),
                    id=f"{wf_id}-{subagent_name}-r{round_num}",
                )

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": subagent_result,
                    }
                )

            final_answer = subagent_result
        else:
            final_answer = "Max supervisor rounds reached. " + (
                messages[-1].get("content", "") if messages else ""
            )

        # Record completion
        await workflow.execute_activity(
            "record_workflow_complete_activity",
            args=[wf_id, "completed", final_answer],
            start_to_close_timeout=timedelta(seconds=10),
        )

        return final_answer
