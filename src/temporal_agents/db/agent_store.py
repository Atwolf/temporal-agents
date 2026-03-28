"""SQLite store for agent definitions — loaded dynamically at runtime."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from temporal_agents.config.schemas import (
    MCPServerConfig,
    SubagentConfig,
    SupervisorConfig,
    VectorCollectionConfig,
    WorkflowConfig,
)

DB_PATH = Path("agent_definitions.db")


def _connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    path = str(db_path or DB_PATH)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_agent_db(db_path: Path | str | None = None) -> None:
    conn = _connect(db_path)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS supervisor (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            model       TEXT NOT NULL DEFAULT 'anthropic:claude-sonnet-4-6',
            system_prompt TEXT NOT NULL,
            max_rounds  INTEGER NOT NULL DEFAULT 15,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS subagents (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT NOT NULL UNIQUE,
            description     TEXT NOT NULL,
            system_prompt   TEXT NOT NULL,
            model           TEXT NOT NULL DEFAULT 'anthropic:claude-sonnet-4-6',
            max_iterations  INTEGER NOT NULL DEFAULT 10,
            mcp_servers     TEXT NOT NULL DEFAULT '[]',   -- JSON array
            vector_collections TEXT NOT NULL DEFAULT '[]', -- JSON array
            is_active       INTEGER NOT NULL DEFAULT 1,
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """
    )
    conn.commit()
    conn.close()


def upsert_supervisor(config: SupervisorConfig, db_path: Path | str | None = None) -> None:
    conn = _connect(db_path)
    conn.execute("DELETE FROM supervisor")
    conn.execute(
        "INSERT INTO supervisor (model, system_prompt, max_rounds) VALUES (?, ?, ?)",
        (config.model, config.system_prompt, config.max_rounds),
    )
    conn.commit()
    conn.close()


def upsert_subagent(config: SubagentConfig, db_path: Path | str | None = None) -> None:
    conn = _connect(db_path)
    conn.execute(
        """
        INSERT INTO subagents (name, description, system_prompt, model, max_iterations, mcp_servers, vector_collections)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            description=excluded.description,
            system_prompt=excluded.system_prompt,
            model=excluded.model,
            max_iterations=excluded.max_iterations,
            mcp_servers=excluded.mcp_servers,
            vector_collections=excluded.vector_collections
        """,
        (
            config.name,
            config.description,
            config.system_prompt,
            config.model,
            config.max_iterations,
            json.dumps([s.model_dump() for s in config.mcp_servers]),
            json.dumps([v.model_dump() for v in config.vector_collections]),
        ),
    )
    conn.commit()
    conn.close()


def load_workflow_config(db_path: Path | str | None = None) -> WorkflowConfig:
    """Load the full workflow config from the agent definitions DB."""
    conn = _connect(db_path)

    row = conn.execute("SELECT * FROM supervisor ORDER BY id DESC LIMIT 1").fetchone()
    if row is None:
        raise RuntimeError("No supervisor config found in agent_definitions DB")
    supervisor = SupervisorConfig(
        model=row["model"],
        system_prompt=row["system_prompt"],
        max_rounds=row["max_rounds"],
    )

    rows = conn.execute("SELECT * FROM subagents WHERE is_active = 1").fetchall()
    subagents = []
    for r in rows:
        subagents.append(
            SubagentConfig(
                name=r["name"],
                description=r["description"],
                system_prompt=r["system_prompt"],
                model=r["model"],
                max_iterations=r["max_iterations"],
                mcp_servers=[MCPServerConfig(**s) for s in json.loads(r["mcp_servers"])],
                vector_collections=[
                    VectorCollectionConfig(**v) for v in json.loads(r["vector_collections"])
                ],
            )
        )
    conn.close()

    return WorkflowConfig(supervisor=supervisor, subagents=subagents)
