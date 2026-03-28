"""SQLite store for tracking workflow executions and transactions."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("temporal_agents.db")


def _connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    path = str(db_path or DB_PATH)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_execution_db(db_path: Path | str | None = None) -> None:
    conn = _connect(db_path)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS workflow_executions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_id     TEXT NOT NULL UNIQUE,
            task            TEXT NOT NULL,
            status          TEXT NOT NULL DEFAULT 'started',
            result          TEXT,
            config_snapshot TEXT,          -- JSON snapshot of config used
            started_at      TEXT NOT NULL DEFAULT (datetime('now')),
            completed_at    TEXT,
            error           TEXT
        );

        CREATE TABLE IF NOT EXISTS transactions (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_execution_id TEXT NOT NULL,
            activity_type       TEXT NOT NULL,       -- 'llm_call', 'tool_execution', 'config_load'
            activity_name       TEXT,                 -- e.g. tool name or 'supervisor'/'subagent_name'
            input_summary       TEXT,
            output_summary      TEXT,
            status              TEXT NOT NULL DEFAULT 'started',
            duration_ms         INTEGER,
            created_at          TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (workflow_execution_id) REFERENCES workflow_executions(workflow_id)
        );

        CREATE INDEX IF NOT EXISTS idx_tx_workflow ON transactions(workflow_execution_id);
        """
    )
    conn.commit()
    conn.close()


def record_workflow_start(
    workflow_id: str,
    task: str,
    config_snapshot: dict | None = None,
    db_path: Path | str | None = None,
) -> None:
    conn = _connect(db_path)
    conn.execute(
        """INSERT INTO workflow_executions (workflow_id, task, status, config_snapshot)
           VALUES (?, ?, 'started', ?)""",
        (workflow_id, task, json.dumps(config_snapshot) if config_snapshot else None),
    )
    conn.commit()
    conn.close()


def record_workflow_complete(
    workflow_id: str,
    status: str = "completed",
    result: str | None = None,
    error: str | None = None,
    db_path: Path | str | None = None,
) -> None:
    conn = _connect(db_path)
    conn.execute(
        """UPDATE workflow_executions
           SET status=?, result=?, error=?, completed_at=?
           WHERE workflow_id=?""",
        (status, result, error, datetime.now(timezone.utc).isoformat(), workflow_id),
    )
    conn.commit()
    conn.close()


def record_transaction(
    workflow_execution_id: str,
    activity_type: str,
    activity_name: str | None = None,
    input_summary: str | None = None,
    output_summary: str | None = None,
    status: str = "completed",
    duration_ms: int | None = None,
    db_path: Path | str | None = None,
) -> int:
    conn = _connect(db_path)
    cur = conn.execute(
        """INSERT INTO transactions
           (workflow_execution_id, activity_type, activity_name,
            input_summary, output_summary, status, duration_ms)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            workflow_execution_id,
            activity_type,
            activity_name,
            input_summary,
            output_summary,
            status,
            duration_ms,
        ),
    )
    conn.commit()
    tx_id = cur.lastrowid
    conn.close()
    return tx_id


def get_workflow_executions(
    limit: int = 50, db_path: Path | str | None = None
) -> list[dict]:
    conn = _connect(db_path)
    rows = conn.execute(
        "SELECT * FROM workflow_executions ORDER BY started_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_transactions(
    workflow_id: str, db_path: Path | str | None = None
) -> list[dict]:
    conn = _connect(db_path)
    rows = conn.execute(
        "SELECT * FROM transactions WHERE workflow_execution_id=? ORDER BY created_at",
        (workflow_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
