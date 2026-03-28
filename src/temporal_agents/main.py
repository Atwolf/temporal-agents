"""CLI entry point — start a workflow execution."""
from __future__ import annotations

import asyncio
import sys
from uuid import uuid4

from temporalio.client import Client

from temporal_agents.config.schemas import WorkflowInput
from temporal_agents.config.settings import settings
from temporal_agents.db.agent_store import init_agent_db
from temporal_agents.db.execution_store import init_execution_db


async def start_workflow(task: str, config_source: str = "db") -> str:
    init_agent_db()
    init_execution_db()

    client = await Client.connect(settings.temporal_address)

    wf_id = f"agent-workflow-{uuid4().hex[:12]}"
    print(f"Starting workflow {wf_id} ...")
    print(f"Task: {task}")
    print(f"Temporal UI: http://localhost:8233/namespaces/default/workflows/{wf_id}")
    print()

    result = await client.execute_workflow(
        "AgentWorkflow",
        WorkflowInput(task=task, config_source=config_source),
        id=wf_id,
        task_queue=settings.temporal_task_queue,
    )

    print(f"\n{'='*60}")
    print(f"Workflow {wf_id} completed.")
    print(f"Result:\n{result}")
    return result


def main() -> None:
    task = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Hello, what can you do?"
    asyncio.run(start_workflow(task))


if __name__ == "__main__":
    main()
