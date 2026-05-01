"""Prompt-call logging. Every LLM invocation should route through here so we
can later analyze which prompt templates produce the best downstream outcomes.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass

from config import PROMPTS_DIR, load_settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS prompt_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template TEXT NOT NULL,
    template_version TEXT NOT NULL,
    template_hash TEXT NOT NULL,
    context_hash TEXT,
    input_hash TEXT,
    output_id TEXT,
    outcome TEXT,              -- 'pending' | 'success' | 'failure'
    outcome_metric REAL,       -- sharpe / composite / 0|1
    outcome_notes TEXT,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_prompt_log_template ON prompt_log(template);
CREATE INDEX IF NOT EXISTS idx_prompt_log_outcome ON prompt_log(outcome);
"""


@dataclass
class LogEntry:
    id: int
    template: str
    template_version: str
    template_hash: str
    context_hash: str | None
    input_hash: str | None
    output_id: str | None
    outcome: str
    outcome_metric: float | None
    outcome_notes: str | None
    created_at: float


def _conn() -> sqlite3.Connection:
    s = load_settings()
    con = sqlite3.connect(s.db_path)
    con.executescript(_SCHEMA)
    return con


def _hash(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]


def template_version(template_name: str) -> tuple[str, str]:
    """(hash, version) for a prompts/<template_name> file.

    Version is 'v<short hash>' so it sorts chronologically when files change.
    """
    path = PROMPTS_DIR / template_name
    if not path.exists():
        return "0" * 16, "missing"
    body = path.read_text(encoding="utf-8")
    h = _hash(body)
    return h, f"v{h[:8]}"


def log_call(
    template: str,
    context: object | None = None,
    input_obj: object | None = None,
    output_id: str | None = None,
) -> int:
    """Insert a pending log row and return its id."""
    h, v = template_version(template)
    ctx_h = _hash(json.dumps(context, default=str, sort_keys=True)) if context is not None else None
    in_h = _hash(json.dumps(input_obj, default=str, sort_keys=True)) if input_obj is not None else None
    with _conn() as con:
        cur = con.execute(
            """INSERT INTO prompt_log
               (template, template_version, template_hash, context_hash, input_hash,
                output_id, outcome, outcome_metric, outcome_notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 'pending', NULL, NULL, ?)""",
            (template, v, h, ctx_h, in_h, output_id, time.time()),
        )
        return int(cur.lastrowid)


def finalize(
    log_id: int,
    outcome: str,
    metric: float | None = None,
    notes: str | None = None,
    output_id: str | None = None,
) -> None:
    if outcome not in ("success", "failure", "pending"):
        raise ValueError(f"bad outcome: {outcome}")
    with _conn() as con:
        con.execute(
            """UPDATE prompt_log
               SET outcome=?, outcome_metric=?, outcome_notes=?,
                   output_id=COALESCE(?, output_id)
               WHERE id=?""",
            (outcome, metric, notes, output_id, log_id),
        )


def all_entries() -> list[LogEntry]:
    with _conn() as con:
        rows = con.execute(
            """SELECT id, template, template_version, template_hash, context_hash,
                      input_hash, output_id, outcome, outcome_metric, outcome_notes,
                      created_at
               FROM prompt_log ORDER BY id"""
        ).fetchall()
    return [LogEntry(*r) for r in rows]
