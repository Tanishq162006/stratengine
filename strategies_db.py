"""SQLite store for saved strategies, run results, and user feedback.

Lives in the same `stratengine.db` as the Strategy Cards index but in
separate tables. Schema is intentionally minimal — strategies are short
(BRAIN expressions are one-liners; QC and IMC are short Python files) so
free-text storage + a few indexed columns is enough.

  strategies        : every alpha/algorithm the user has saved.
  strategy_results  : metric snapshots tied to a strategy (Sharpe, Fitness,
                      pnl, etc.) — many per strategy.
  strategy_feedback : ONE row per strategy. Star rating 1-5, status, notes.

The schema is created lazily on first connection so the UI and CLI can
both touch the DB without an explicit migration step.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from config import load_settings


# Competitions we model. Same string is used as a tab label in the UI.
COMPETITIONS = ("worldquant_iqc", "quantconnect", "imc_prosperity")
COMPETITION_LABELS = {
    "worldquant_iqc": "WorldQuant BRAIN",
    "quantconnect": "QuantConnect",
    "imc_prosperity": "IMC Prosperity",
}

# Status values for feedback.status. Free-form on the UI side; these are the
# canonical buckets we surface in filters.
STATUS_VALUES = ("draft", "iterating", "submitted", "passed", "failed", "shelved")

# Metric vocabularies per competition. Used by the UI to render the right
# input form. Free-form metric names are still allowed.
METRIC_VOCAB: dict[str, tuple[str, ...]] = {
    "worldquant_iqc": (
        "sharpe", "fitness", "sub_universe_sharpe", "turnover_pct",
        "ic", "drawdown", "self_corr_max",
    ),
    "quantconnect": (
        "sharpe", "total_return_pct", "annualized_return_pct",
        "max_drawdown_pct", "win_rate_pct", "psr",
    ),
    "imc_prosperity": (
        "round_pnl", "total_pnl", "rank", "score",
    ),
}


_SCHEMA = """
CREATE TABLE IF NOT EXISTS strategies (
    strategy_id TEXT PRIMARY KEY,
    competition TEXT NOT NULL,
    name        TEXT NOT NULL,
    expression  TEXT NOT NULL,
    thesis      TEXT,
    config_json TEXT,
    source      TEXT,
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_strategies_comp ON strategies(competition);
CREATE INDEX IF NOT EXISTS idx_strategies_created ON strategies(created_at DESC);

CREATE TABLE IF NOT EXISTS strategy_results (
    result_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id  TEXT NOT NULL,
    metric       TEXT NOT NULL,
    value        REAL,
    text_value   TEXT,
    observed_at  REAL NOT NULL,
    notes        TEXT,
    FOREIGN KEY (strategy_id) REFERENCES strategies(strategy_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_results_strategy ON strategy_results(strategy_id);

CREATE TABLE IF NOT EXISTS strategy_feedback (
    strategy_id TEXT PRIMARY KEY,
    rating      INTEGER NOT NULL DEFAULT 0,
    status      TEXT    NOT NULL DEFAULT 'draft',
    notes       TEXT,
    updated_at  REAL    NOT NULL,
    FOREIGN KEY (strategy_id) REFERENCES strategies(strategy_id) ON DELETE CASCADE
);
"""


def _conn(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or load_settings().db_path
    con = sqlite3.connect(str(path))
    con.row_factory = sqlite3.Row
    con.executescript(_SCHEMA)
    con.execute("PRAGMA foreign_keys = ON")
    return con


def _stable_id(competition: str, name: str, expression: str) -> str:
    raw = f"{competition}|{name}|{expression.strip()}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:16]


@dataclass
class Strategy:
    strategy_id: str
    competition: str
    name: str
    expression: str
    thesis: str = ""
    config: dict = field(default_factory=dict)
    source: str = "manual"
    created_at: float = 0.0
    updated_at: float = 0.0


def upsert_strategy(
    *,
    competition: str,
    name: str,
    expression: str,
    thesis: str = "",
    config: dict | None = None,
    source: str = "manual",
    db_path: Path | None = None,
) -> str:
    """Insert a strategy if absent, else refresh thesis/config/source. Returns id."""
    if competition not in COMPETITIONS:
        raise ValueError(f"unknown competition: {competition!r}")
    sid = _stable_id(competition, name, expression)
    now = time.time()
    with _conn(db_path) as con:
        existing = con.execute(
            "SELECT strategy_id FROM strategies WHERE strategy_id = ?", (sid,)
        ).fetchone()
        if existing is None:
            con.execute(
                """INSERT INTO strategies
                   (strategy_id, competition, name, expression, thesis, config_json, source, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (sid, competition, name, expression, thesis,
                 json.dumps(config or {}), source, now, now),
            )
            con.execute(
                """INSERT OR IGNORE INTO strategy_feedback
                   (strategy_id, rating, status, notes, updated_at)
                   VALUES (?, 0, 'draft', '', ?)""",
                (sid, now),
            )
        else:
            con.execute(
                """UPDATE strategies SET thesis=?, config_json=?, source=?, updated_at=?
                   WHERE strategy_id=?""",
                (thesis, json.dumps(config or {}), source, now, sid),
            )
    return sid


def list_strategies(competition: str, db_path: Path | None = None) -> list[dict[str, Any]]:
    with _conn(db_path) as con:
        rows = con.execute(
            """SELECT s.*,
                      f.rating  AS rating,
                      f.status  AS status,
                      f.notes   AS feedback_notes
                 FROM strategies s
                 LEFT JOIN strategy_feedback f USING (strategy_id)
                WHERE s.competition = ?
                ORDER BY s.updated_at DESC""",
            (competition,),
        ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        d["config"] = json.loads(d.pop("config_json") or "{}")
        out.append(d)
    return out


def get_strategy(strategy_id: str, db_path: Path | None = None) -> dict[str, Any] | None:
    with _conn(db_path) as con:
        r = con.execute(
            """SELECT s.*, f.rating, f.status, f.notes AS feedback_notes
                 FROM strategies s
                 LEFT JOIN strategy_feedback f USING (strategy_id)
                WHERE s.strategy_id = ?""",
            (strategy_id,),
        ).fetchone()
    if r is None:
        return None
    d = dict(r)
    d["config"] = json.loads(d.pop("config_json") or "{}")
    return d


def delete_strategy(strategy_id: str, db_path: Path | None = None) -> None:
    with _conn(db_path) as con:
        con.execute("DELETE FROM strategies WHERE strategy_id = ?", (strategy_id,))


# ---------- Results ----------

def add_result(
    strategy_id: str,
    metric: str,
    value: float | None = None,
    text_value: str | None = None,
    notes: str = "",
    db_path: Path | None = None,
) -> int:
    if value is None and text_value is None:
        raise ValueError("provide value or text_value for the result")
    now = time.time()
    with _conn(db_path) as con:
        cur = con.execute(
            """INSERT INTO strategy_results
                 (strategy_id, metric, value, text_value, observed_at, notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (strategy_id, metric, value, text_value, now, notes),
        )
        return int(cur.lastrowid or 0)


def list_results(strategy_id: str, db_path: Path | None = None) -> list[dict[str, Any]]:
    with _conn(db_path) as con:
        rows = con.execute(
            """SELECT * FROM strategy_results
                WHERE strategy_id = ?
                ORDER BY observed_at DESC""",
            (strategy_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def latest_metrics(strategy_id: str, db_path: Path | None = None) -> dict[str, float]:
    """Most-recent value per metric — what the UI shows in the list view."""
    with _conn(db_path) as con:
        rows = con.execute(
            """SELECT metric, value, observed_at
                 FROM strategy_results
                WHERE strategy_id = ? AND value IS NOT NULL
                ORDER BY observed_at DESC""",
            (strategy_id,),
        ).fetchall()
    out: dict[str, float] = {}
    for r in rows:
        if r["metric"] not in out:
            out[r["metric"]] = float(r["value"])
    return out


def delete_result(result_id: int, db_path: Path | None = None) -> None:
    with _conn(db_path) as con:
        con.execute("DELETE FROM strategy_results WHERE result_id = ?", (result_id,))


# ---------- Feedback ----------

def set_feedback(
    strategy_id: str,
    rating: int | None = None,
    status: str | None = None,
    notes: str | None = None,
    db_path: Path | None = None,
) -> None:
    if rating is not None and not (0 <= rating <= 5):
        raise ValueError("rating must be 0..5")
    now = time.time()
    with _conn(db_path) as con:
        cur = con.execute(
            "SELECT rating, status, notes FROM strategy_feedback WHERE strategy_id = ?",
            (strategy_id,),
        ).fetchone()
        if cur is None:
            con.execute(
                """INSERT INTO strategy_feedback (strategy_id, rating, status, notes, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (strategy_id, rating or 0, status or "draft", notes or "", now),
            )
        else:
            con.execute(
                """UPDATE strategy_feedback
                      SET rating=?, status=?, notes=?, updated_at=?
                    WHERE strategy_id=?""",
                (
                    rating if rating is not None else cur["rating"],
                    status if status is not None else cur["status"],
                    notes if notes is not None else cur["notes"],
                    now, strategy_id,
                ),
            )


def get_feedback(strategy_id: str, db_path: Path | None = None) -> dict[str, Any] | None:
    with _conn(db_path) as con:
        r = con.execute(
            "SELECT * FROM strategy_feedback WHERE strategy_id = ?",
            (strategy_id,),
        ).fetchone()
    return dict(r) if r else None


# ---------- Bulk import ----------

def import_alpha_history(
    history_path: Path | None = None, db_path: Path | None = None
) -> int:
    """Parse `knowledge/worldquant_iqc/alpha_history.md` and insert each entry."""
    import re

    from config import ROOT
    path = history_path or (ROOT / "knowledge" / "worldquant_iqc" / "alpha_history.md")
    if not path.exists():
        return 0
    text = path.read_text(encoding="utf-8")
    sections = re.split(r"\n###\s+", text)
    inserted = 0
    for section in sections[1:]:
        head, *_ = section.split("\n", 1)
        name = head.strip()
        m = re.search(r"```\s*\n(.*?)\n```", section, re.DOTALL)
        if not m:
            continue
        expression = m.group(1).strip()
        # Pull any explicit metrics ("Sharpe 1.47", "Fitness 0.78", etc.)
        results_match = re.search(r"\*\*Results:\*\*\s*([^\n]+)", section)
        thesis_match = re.search(r"\*\*Lesson:\*\*\s*([^\n]+)", section)
        thesis = (thesis_match.group(1).strip() if thesis_match else "")
        sid = upsert_strategy(
            competition="worldquant_iqc",
            name=name,
            expression=expression,
            thesis=thesis,
            source="alpha_history",
            db_path=db_path,
        )
        if results_match:
            for token, metric in (
                (r"Sharpe\s+([0-9.]+)", "sharpe"),
                (r"Turnover\s+([0-9.]+)", "turnover_pct"),
                (r"Fitness\s+([0-9.]+)", "fitness"),
                (r"Sub-Sharpe\s+([0-9.]+)", "sub_universe_sharpe"),
            ):
                hit = re.search(token, results_match.group(1))
                if hit:
                    add_result(sid, metric, float(hit.group(1)),
                               notes="imported from alpha_history.md", db_path=db_path)
        inserted += 1
    return inserted
