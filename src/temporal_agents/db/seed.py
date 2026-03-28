"""Seed the agent_definitions DB with demo agent configurations."""
from __future__ import annotations

import sys

from temporal_agents.config.schemas import (
    MCPServerConfig,
    SubagentConfig,
    SupervisorConfig,
    VectorCollectionConfig,
)
from temporal_agents.db.agent_store import init_agent_db, upsert_subagent, upsert_supervisor


def seed() -> None:
    init_agent_db()

    # --- Supervisor ---
    upsert_supervisor(
        SupervisorConfig(
            model="anthropic:claude-sonnet-4-6",
            system_prompt=(
                "You are a supervisor agent coordinating specialized subagents.\n"
                "Analyze the user's request and delegate to the most appropriate subagent.\n"
                "You may call multiple subagents in sequence to complete complex tasks.\n"
                "When you have a complete answer, respond directly without calling any tools.\n"
                "Available subagents are provided as tools — call the one that best fits the task."
            ),
            max_rounds=15,
        )
    )

    # --- Subagent: greeter (uses get_greeting — always works) ---
    upsert_subagent(
        SubagentConfig(
            name="greeter_agent",
            description="Greets users and provides friendly welcomes. Delegate when the user wants a greeting or introduction.",
            system_prompt=(
                "You are a friendly greeting specialist. Use the get_greeting tool to "
                "create personalized greetings for users. Always use the tool — don't "
                "make up greetings yourself."
            ),
            model="anthropic:claude-sonnet-4-6",
            max_iterations=5,
            mcp_servers=[
                MCPServerConfig(
                    name="demo_tools",
                    transport="stdio",
                    command="python",
                    args=["mcp_servers/demo_server.py"],
                )
            ],
        )
    )

    # --- Subagent: researcher (uses flaky_lookup — fails first, succeeds on retry) ---
    upsert_subagent(
        SubagentConfig(
            name="research_agent",
            description="Researches topics and looks up information. Delegate when the user needs facts or data.",
            system_prompt=(
                "You are a research specialist. Use the flaky_lookup tool to find "
                "information about topics the user asks about. The tool may be unreliable "
                "but the system will handle retries automatically. Always use the tool."
            ),
            model="anthropic:claude-sonnet-4-6",
            max_iterations=10,
            mcp_servers=[
                MCPServerConfig(
                    name="demo_tools",
                    transport="stdio",
                    command="python",
                    args=["mcp_servers/demo_server.py"],
                )
            ],
        )
    )

    print("Agent definitions DB seeded successfully.")
    print("  - Supervisor configured")
    print("  - greeter_agent: uses get_greeting (always succeeds)")
    print("  - research_agent: uses flaky_lookup (fails once, then succeeds — tests Temporal retry)")


if __name__ == "__main__":
    seed()
