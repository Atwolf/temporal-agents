"""Load and execute MCP tools via langchain-mcp-adapters."""
from __future__ import annotations

from temporal_agents.config.schemas import MCPServerConfig, ToolSchema


def _build_server_dict(configs: list[MCPServerConfig]) -> dict:
    server_dict = {}
    for cfg in configs:
        entry: dict = {"transport": cfg.transport}
        if cfg.transport == "stdio":
            entry["command"] = cfg.command
            entry["args"] = cfg.args
            if cfg.env:
                entry["env"] = cfg.env
        elif cfg.transport == "http":
            entry["url"] = cfg.url
            if cfg.headers:
                entry["headers"] = cfg.headers
        server_dict[cfg.name] = entry
    return server_dict


async def discover_mcp_tool_schemas(
    mcp_configs: list[MCPServerConfig],
) -> list[ToolSchema]:
    """Connect to MCP servers and return tool schemas (name, description, params)."""
    from langchain_mcp_adapters.client import MultiServerMCPClient

    server_dict = _build_server_dict(mcp_configs)
    async with MultiServerMCPClient(server_dict) as client:
        tools = client.get_tools()
        schemas = []
        for tool in tools:
            params = {}
            if hasattr(tool, "args_schema") and tool.args_schema is not None:
                params = tool.args_schema.model_json_schema()
            schemas.append(
                ToolSchema(
                    name=tool.name,
                    description=tool.description or "",
                    parameters=params,
                )
            )
        return schemas


async def execute_mcp_tool(
    mcp_configs: list[MCPServerConfig],
    tool_name: str,
    tool_args: dict,
) -> str:
    """Execute a single MCP tool call.  Stateless — safe for Temporal retry."""
    from langchain_mcp_adapters.client import MultiServerMCPClient

    server_dict = _build_server_dict(mcp_configs)
    async with MultiServerMCPClient(server_dict) as client:
        tools = client.get_tools()
        for tool in tools:
            if tool.name == tool_name:
                result = await tool.ainvoke(tool_args)
                return str(result)

    raise ValueError(f"Tool '{tool_name}' not found in MCP servers: {[c.name for c in mcp_configs]}")
