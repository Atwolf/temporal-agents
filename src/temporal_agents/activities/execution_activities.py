"""Activities for recording workflow execution events to SQLite."""
from __future__ import annotations

from temporalio import activity

from temporal_agents.db.execution_store import (
    record_workflow_complete,
    record_workflow_start,
)


@activity.defn(name="record_workflow_start_activity")
async def record_workflow_start_activity(
    workflow_id: str, task: str, config_snapshot: dict
) -> None:
    record_workflow_start(workflow_id, task, config_snapshot)


@activity.defn(name="record_workflow_complete_activity")
async def record_workflow_complete_activity(
    workflow_id: str, status: str, result: str
) -> None:
    record_workflow_complete(workflow_id, status=status, result=result)
