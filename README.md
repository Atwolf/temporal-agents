# Temporal Agents

Durable multi-agent workflows powered by **Temporal** + **LangChain** supervisor pattern.

## Architecture

```
Temporal Workflow (AgentWorkflow)
  |
  +-- Activity: load_agent_configs()     (from SQLite DB)
  |
  +-- Supervisor Loop:
  |     |
  |     +-- Activity: call_llm()         (supervisor decides which subagent)
  |     |
  |     +-- Child Workflow: SubagentWorkflow
  |           |
  |           +-- Activity: call_llm()   (subagent reasons about tools)
  |           +-- Activity: execute_tool() (MCP tool / vector search)
  |           +-- ... loop until done
  |
  +-- Return final answer
```

Each LLM call and each tool execution is a **separate Temporal Activity**.
If a tool fails, Temporal retries only that tool -- the LLM decision replays from event history (zero tokens wasted).

## Quick Start

```bash
# 1. Install
make install

# 2. Seed demo agent definitions into SQLite
make seed

# 3. Start Temporal (separate terminal)
make temporal

# 4. Start the worker (separate terminal)
make worker

# 5. Run a task
make run TASK="Greet Alice and research quantum computing"

# 6. (Optional) Start the Chat UI
make ui
```

## Make Commands

| Command | Description |
|---------|-------------|
| `make install` | Install all dependencies |
| `make seed` | Seed agent definitions DB |
| `make temporal` | Start local Temporal dev server |
| `make worker` | Start the Temporal worker |
| `make ui` | Start LangGraph Agent Chat UI |
| `make run TASK="..."` | Run a workflow via CLI |
| `make db-reset` | Delete and re-seed databases |
| `make test` | Run tests |
| `make clean` | Remove generated files |

## Configuration

Set `ANTHROPIC_API_KEY` in `.env`:

```
ANTHROPIC_API_KEY=sk-ant-xxxxx
```

Agent definitions are stored in `agent_definitions.db` (SQLite) and loaded dynamically at workflow start. Edit via the seed script or directly via SQL.

## Demo MCP Server

`mcp_servers/demo_server.py` provides two tools:
- **get_greeting** -- always succeeds
- **flaky_lookup** -- fails on first call, succeeds on retry (demonstrates Temporal's tool-level durability)
