from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Configuration models (persisted in agent_definitions DB)
# ---------------------------------------------------------------------------

class MCPServerConfig(BaseModel):
    name: str
    transport: Literal["stdio", "http"]
    # stdio
    command: str | None = None
    args: list[str] = []
    env: dict[str, str] = {}
    # http
    url: str | None = None
    headers: dict[str, str] = {}


class VectorCollectionConfig(BaseModel):
    collection_name: str
    description: str
    persist_directory: str = "./chroma_data"
    embedding_model: str = "text-embedding-3-small"


class SubagentConfig(BaseModel):
    name: str
    description: str
    system_prompt: str
    model: str = "anthropic:claude-sonnet-4-6"
    mcp_servers: list[MCPServerConfig] = []
    vector_collections: list[VectorCollectionConfig] = []
    max_iterations: int = 10


class SupervisorConfig(BaseModel):
    model: str = "anthropic:claude-sonnet-4-6"
    system_prompt: str = (
        "You are a supervisor agent coordinating specialized subagents.\n"
        "Analyze the user's request and delegate to the most appropriate subagent.\n"
        "You may call multiple subagents in sequence to complete complex tasks.\n"
        "When you have a complete answer, respond directly without calling any tools."
    )
    max_rounds: int = 15


class WorkflowConfig(BaseModel):
    supervisor: SupervisorConfig
    subagents: list[SubagentConfig]
    task_queue: str = "agent-task-queue"


# ---------------------------------------------------------------------------
# Temporal data-transfer types  (must be serializable dataclasses)
# ---------------------------------------------------------------------------

@dataclass
class ToolSchema:
    name: str
    description: str
    parameters: dict


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str  # JSON-encoded

    def parse_arguments(self) -> dict:
        return json.loads(self.arguments)


@dataclass
class ToolResult:
    tool_call_id: str
    name: str
    content: str
    success: bool = True


@dataclass
class LLMResponse:
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


@dataclass
class LLMCallInput:
    model: str
    system_prompt: str
    messages: list[dict]
    tool_schemas: list[ToolSchema]


@dataclass
class ToolExecutionInput:
    tool_call: ToolCall
    mcp_servers: list[dict]           # serialized MCPServerConfig dicts
    vector_collections: list[dict]    # serialized VectorCollectionConfig dicts


@dataclass
class WorkflowInput:
    task: str
    config_source: str = "db"  # "db" or path to YAML


@dataclass
class SubagentWorkflowInput:
    config: dict            # serialized SubagentConfig
    task: str
    tool_schemas: list[ToolSchema]
    workflow_execution_id: str
