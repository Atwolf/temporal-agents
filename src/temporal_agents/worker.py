"""Temporal worker — registers all workflows and activities."""
from __future__ import annotations

import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from temporal_agents.activities.config_activities import (
    load_agent_configs,
    load_tool_schemas,
)
from temporal_agents.activities.execution_activities import (
    record_workflow_complete_activity,
    record_workflow_start_activity,
)
from temporal_agents.activities.llm_activities import call_llm
from temporal_agents.activities.tool_activities import execute_tool
from temporal_agents.config.settings import settings
from temporal_agents.db.agent_store import init_agent_db
from temporal_agents.db.execution_store import init_execution_db
from temporal_agents.workflows.agent_workflow import AgentWorkflow
from temporal_agents.workflows.subagent_workflow import SubagentWorkflow


async def run_worker() -> None:
    # Ensure DBs are initialised
    init_agent_db()
    init_execution_db()

    client = await Client.connect(settings.temporal_address)

    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[AgentWorkflow, SubagentWorkflow],
        activities=[
            load_agent_configs,
            load_tool_schemas,
            call_llm,
            execute_tool,
            record_workflow_start_activity,
            record_workflow_complete_activity,
        ],
    )
    print(
        f"Worker started — listening on queue '{settings.temporal_task_queue}' "
        f"at {settings.temporal_address}"
    )
    await worker.run()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
