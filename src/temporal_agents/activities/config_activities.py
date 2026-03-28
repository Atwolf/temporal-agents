"""Activities for loading agent configuration and discovering tool schemas."""
from __future__ import annotations

from temporalio import activity

from temporal_agents.config.schemas import (
    MCPServerConfig,
    SubagentConfig,
    ToolSchema,
    VectorCollectionConfig,
    WorkflowConfig,
)
from temporal_agents.db.agent_store import load_workflow_config
from temporal_agents.tools.mcp_loader import discover_mcp_tool_schemas


@activity.defn(name="load_agent_configs")
async def load_agent_configs(config_source: str) -> WorkflowConfig:
    """Load workflow config from the agent definitions SQLite DB."""
    if config_source == "db":
        return load_workflow_config()
    # Future: support YAML path
    return load_workflow_config()


@activity.defn(name="load_tool_schemas")
async def load_tool_schemas(config_dict: dict) -> list[ToolSchema]:
    """Connect to MCP servers and build tool schemas for a subagent."""
    config = SubagentConfig.model_validate(config_dict)
    schemas: list[ToolSchema] = []

    # Discover MCP tool schemas
    if config.mcp_servers:
        mcp_schemas = await discover_mcp_tool_schemas(config.mcp_servers)
        schemas.extend(mcp_schemas)

    # Add vector search tool schemas
    for vc in config.vector_collections:
        schemas.append(
            ToolSchema(
                name=f"search_{vc.collection_name}",
                description=vc.description,
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query",
                        }
                    },
                    "required": ["query"],
                },
            )
        )

    return schemas
