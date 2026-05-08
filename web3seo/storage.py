"""SQLite storage with idempotency keys.

Three-stage pipeline maps to three tables:
  responses  — raw LLM responses, unique on (run_date, query_id, provider)
  mentions   — extracted protocol mentions, FK to responses
  errors     — anything that failed during a phase, with class + message

Idempotency:
  - fetch checks `has_response(run_date, query_id, provider)` before calling LLM
  - extract deletes mentions for response_id before re-extracting
  - aggregate writes a fresh JSON per run_date (overwrite is fine)
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .providers.base import LLMResponse


SCHEMA = """
CREATE TABLE IF NOT EXISTS responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date TEXT NOT NULL,
    query_id TEXT NOT NULL,
    query_text TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    response_text TEXT NOT NULL,
    citations_json TEXT NOT NULL,
    raw_json TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd REAL NOT NULL DEFAULT 0.0,
    UNIQUE(run_date, query_id, provider)
);

CREATE INDEX IF NOT EXISTS idx_responses_run_date ON responses(run_date);
CREATE INDEX IF NOT EXISTS idx_responses_provider ON responses(provider);

CREATE TABLE IF NOT EXISTS mentions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    response_id INTEGER NOT NULL,
    protocol_id TEXT NOT NULL,
    matched_alias TEXT NOT NULL,
    context TEXT NOT NULL,
    char_offset INTEGER NOT NULL,
    ordinal INTEGER NOT NULL,
    FOREIGN KEY (response_id) REFERENCES responses(id),
    UNIQUE(response_id, ordinal)
);

CREATE INDEX IF NOT EXISTS idx_mentions_protocol_id ON mentions(protocol_id);
CREATE INDEX IF NOT EXISTS idx_mentions_response_id ON mentions(response_id);

CREATE TABLE IF NOT EXISTS errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date TEXT NOT NULL,
    phase TEXT NOT NULL,
    query_id TEXT,
    provider TEXT,
    error_class TEXT NOT NULL,
    error_message TEXT NOT NULL,
    occurred_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_errors_run_date ON errors(run_date);
"""


@contextmanager
def connect(db_path: str | Path):
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def has_response(
    conn: sqlite3.Connection,
    run_date: str,
    query_id: str,
    provider: str,
) -> bool:
    row = conn.execute(
        "SELECT 1 FROM responses WHERE run_date = ? AND query_id = ? AND provider = ?",
        (run_date, query_id, provider),
    ).fetchone()
    return row is not None


def save_response(
    conn: sqlite3.Connection,
    run_date: str,
    query_id: str,
    response: LLMResponse,
) -> int:
    citations_json = json.dumps([c.__dict__ for c in response.citations], ensure_ascii=False)
    raw_json = json.dumps(response.raw, default=str, ensure_ascii=False)
    cur = conn.execute(
        """
        INSERT INTO responses
            (run_date, query_id, query_text, provider, model, response_text,
             citations_json, raw_json, fetched_at, input_tokens, output_tokens, cost_usd)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_date,
            query_id,
            response.query,
            response.provider,
            response.model,
            response.response_text,
            citations_json,
            raw_json,
            response.fetched_at.isoformat(),
            response.input_tokens,
            response.output_tokens,
            response.cost_usd,
        ),
    )
    return cur.lastrowid


def save_error(
    conn: sqlite3.Connection,
    run_date: str,
    phase: str,
    error: Exception,
    *,
    query_id: str | None = None,
    provider: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO errors (run_date, phase, query_id, provider, error_class, error_message, occurred_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_date,
            phase,
            query_id,
            provider,
            type(error).__name__,
            str(error),
            datetime.now(timezone.utc).isoformat(),
        ),
    )
