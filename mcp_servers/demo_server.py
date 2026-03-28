"""Demo MCP server with two tools:
  1. get_greeting  — always succeeds
  2. flaky_lookup  — fails on first call, succeeds on second (demonstrates Temporal retry)

Run: python mcp_servers/demo_server.py
"""
from __future__ import annotations

import json
import os
import tempfile

from fastmcp import FastMCP

mcp = FastMCP("DemoTools")

# ---------------------------------------------------------------------------
# Tool 1: always succeeds
# ---------------------------------------------------------------------------

@mcp.tool()
def get_greeting(name: str) -> str:
    """Return a friendly greeting for the given name."""
    return f"Hello, {name}! Welcome to the Temporal Agents demo."


# ---------------------------------------------------------------------------
# Tool 2: fails on first invocation, succeeds on second
# Uses a temp file to track invocation count per unique input.
# ---------------------------------------------------------------------------

_FAIL_STATE_DIR = os.path.join(tempfile.gettempdir(), "temporal_agents_flaky")
os.makedirs(_FAIL_STATE_DIR, exist_ok=True)


def _state_file(query: str) -> str:
    safe = "".join(c if c.isalnum() else "_" for c in query)[:80]
    return os.path.join(_FAIL_STATE_DIR, f"flaky_{safe}.json")


@mcp.tool()
def flaky_lookup(query: str) -> str:
    """Look up information about a topic.  (Intentionally unreliable — may require retry.)"""
    path = _state_file(query)
    count = 0
    if os.path.exists(path):
        with open(path) as f:
            count = json.load(f).get("count", 0)

    count += 1
    with open(path, "w") as f:
        json.dump({"count": count}, f)

    if count < 2:
        raise RuntimeError(
            f"Transient failure looking up '{query}' (attempt {count}). "
            "This simulates a flaky external service — Temporal will retry."
        )

    # Reset for next unique query cycle
    os.remove(path)
    return f"Successfully retrieved information about '{query}': This is the result after a retry."


if __name__ == "__main__":
    mcp.run(transport="stdio")
