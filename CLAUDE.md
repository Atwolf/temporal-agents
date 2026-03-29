# CLAUDE.md — Temporal Agents

## Project Overview

Durable multi-agent workflows combining **Temporal** (workflow orchestration, crash recovery, retries) with **LangChain** (LLM reasoning, tool calling, supervisor pattern). Subagent configurations are stored in SQLite and loaded dynamically at runtime — the agent graph is never hardcoded.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│              Temporal Workflow (AgentWorkflow)                 │
│                                                                │
│  1. Activity: load_agent_configs()  ← from SQLite DB          │
│                                                                │
│  2. SUPERVISOR LOOP:                                          │
│     a. Activity: call_llm(supervisor)                         │
│         → Decides which subagent to invoke, or final answer   │
│         → Decision preserved in Temporal event history         │
│                                                                │
│     b. Child Workflow: SubagentWorkflow                       │
│        ┌──────────────────────────────────────────────┐       │
│        │  TOOL LOOP:                                  │       │
│        │   i.  Activity: call_llm(subagent)           │       │
│        │        → Returns tool_calls[] or final text  │       │
│        │   ii. Activity: execute_tool(name, args)     │       │
│        │        → MCP tool / vector search            │       │
│        │        → If fails: Temporal retries THIS     │       │
│        │          only. LLM decision NOT re-executed.  │       │
│        │   iii. Append result → loop to (i)           │       │
│        └──────────────────────────────────────────────┘       │
│                                                                │
│     c. Append subagent result → loop to (a)                   │
│                                                                │
│  3. Return final answer                                       │
└──────────────────────────────────────────────────────────────┘
```

### Why Tool-Level Temporal Boundaries

Each LLM call and each tool execution is a **separate Temporal Activity**. If a tool fails:
- Temporal retries only that `execute_tool` activity
- The `call_llm` that decided to use that tool replays from event history — zero tokens, zero cost
- All prior iterations also replay from history

This is fundamentally different from wrapping the entire agent as one activity (where a tool failure re-runs all LLM reasoning from scratch).

## Key Design Decisions

1. **Workflows are deterministic** — all non-deterministic work (LLM calls, MCP tools, file I/O) runs inside Activities
2. **Messages as dicts** at Temporal boundaries — LangChain Message objects are NOT serializable; conversion happens inside activities via `_dict_to_lc_message()`
3. **Pydantic models for config**, dataclasses for Temporal DTOs (`ToolCall`, `LLMResponse`, `ToolResult`)
4. **SQLite for agent definitions** (`agent_definitions.db`) — loaded at workflow start, not hardcoded
5. **SQLite for execution tracking** (`temporal_agents.db`) — records every workflow run and transaction
6. **Stateless MCP tool execution** — `MultiServerMCPClient` creates fresh sessions per call, safe for Temporal retry on any worker
7. **Anthropic Claude** via `langchain-anthropic`, model string: `anthropic:claude-sonnet-4-6`

## Project Structure

```
src/temporal_agents/
├── config/
│   ├── settings.py          # Pydantic Settings — loads .env (ANTHROPIC_API_KEY, TEMPORAL_ADDRESS)
│   └── schemas.py           # All data types: WorkflowConfig, SubagentConfig, ToolCall, LLMResponse, etc.
├── db/
│   ├── agent_store.py       # SQLite: CRUD for agent definitions (supervisor + subagents)
│   ├── execution_store.py   # SQLite: workflow executions + transaction log
│   └── seed.py              # Seed demo agents into agent_definitions.db
├── workflows/
│   ├── agent_workflow.py    # Top-level Temporal Workflow (supervisor loop)
│   └── subagent_workflow.py # Child Workflow (subagent tool loop with per-tool durability)
├── activities/
│   ├── config_activities.py     # load_agent_configs, load_tool_schemas
│   ├── llm_activities.py        # call_llm (used by both supervisor and subagents)
│   ├── tool_activities.py       # execute_tool (MCP or vector search)
│   └── execution_activities.py  # record_workflow_start/complete to SQLite
├── tools/
│   ├── mcp_loader.py        # MCP tool schema discovery + execution via langchain-mcp-adapters
│   └── vector_search.py     # Chroma vector similarity search
├── graph.py                 # LangGraph wrapper for Agent Chat UI
├── worker.py                # Temporal worker (registers all workflows + activities)
└── main.py                  # CLI entry point to start a workflow
mcp_servers/
└── demo_server.py           # FastMCP: get_greeting (always works) + flaky_lookup (fails once)
```

## How to Run

```bash
make install          # pip install -e ".[dev]"
make seed             # Seed agent definitions DB
make temporal         # Terminal 1: start Temporal dev server (localhost:7233, UI at :8233)
make worker           # Terminal 2: start the Temporal worker
make run TASK="..."   # Terminal 3: run a workflow
make ui               # Optional: LangGraph Agent Chat UI
make db-reset         # Wipe and re-seed both databases
make test             # Run pytest
```

## Configuration

### Environment (.env)
```
ANTHROPIC_API_KEY=sk-ant-xxxxx     # Required
TEMPORAL_ADDRESS=localhost:7233     # Default
TEMPORAL_TASK_QUEUE=agent-task-queue
```

### Agent Definitions (SQLite)

Agent configs live in `agent_definitions.db`, loaded dynamically by the `load_agent_configs` activity at workflow start. Tables:
- `supervisor` — single row: model, system_prompt, max_rounds
- `subagents` — one row per subagent: name, description, system_prompt, model, mcp_servers (JSON), vector_collections (JSON)

To add a new subagent, either:
- Add it to `src/temporal_agents/db/seed.py` and run `make seed`
- Insert directly via SQL into `agent_definitions.db`

### MCP Servers

Subagent MCP server configs are stored as JSON in the `subagents.mcp_servers` column. Each entry specifies transport (`stdio` or `http`), command/args, or URL. The `langchain-mcp-adapters` `MultiServerMCPClient` handles connection and tool discovery.

## How to Extend

### Add a new subagent
1. Add a `upsert_subagent(SubagentConfig(...))` call in `db/seed.py`
2. Run `make seed`
3. The supervisor will see it as a new tool on the next workflow run

### Add a new MCP server to a subagent
1. Add an `MCPServerConfig` to the subagent's `mcp_servers` list in `db/seed.py`
2. The MCP server's tools are discovered at workflow start via `load_tool_schemas`

### Add vector search to a subagent
1. Add a `VectorCollectionConfig` to the subagent's `vector_collections` list
2. Ensure the Chroma collection exists at the specified `persist_directory`

## Code Conventions

- **Temporal workflow code** must be deterministic — no I/O, no randomness, no LLM calls
- **Activities** handle all external calls (LLM, MCP, DB, filesystem)
- **Data crossing Temporal boundaries** must be serializable: use `@dataclass` with primitive types or Pydantic `.model_dump()`/`.model_validate()`
- **LangChain messages** are converted to/from `list[dict]` at activity boundaries
- Config is always `Pydantic BaseModel`, Temporal DTOs are always `@dataclass`

## Testing

```bash
make test              # Run all tests
pytest tests/ -v       # Verbose
pytest tests/test_config.py -v   # Specific file
```

Test framework: pytest + pytest-asyncio. Temporal workflows can be tested with `temporalio.testing.WorkflowEnvironment`.
