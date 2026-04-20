"""Per-source quality tracking.

Stores metrics in SQLite `source_scores`:
  - extraction_success_rate
  - card_quality_score (avg card.confidence)
  - backtest_survival_rate (fraction of candidates derived from this source that pass evaluator violations)
  - playbook_clarity_score (avg signal_clarity from decision_scorer)
  - n_attempts (how many data points the rolling averages are over)
  - updated_at

New sources start at NEUTRAL_DEFAULT (0.5) rather than 0, so unseen sources are
not penalized to irrelevance before they have a chance to prove themselves.

Retriever may call `score_for(source)` to apply a bounded weight to ranking.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from config import load_settings

NEUTRAL_DEFAULT = 0.5


_SCHEMA = """
CREATE TABLE IF NOT EXISTS source_scores (
    source_name TEXT PRIMARY KEY,
    extraction_success_rate REAL NOT NULL DEFAULT 0.5,
    card_quality_score REAL NOT NULL DEFAULT 0.5,
    backtest_survival_rate REAL NOT NULL DEFAULT 0.5,
    playbook_clarity_score REAL NOT NULL DEFAULT 0.5,
    n_extraction INTEGER NOT NULL DEFAULT 0,
    n_cards INTEGER NOT NULL DEFAULT 0,
    n_backtests INTEGER NOT NULL DEFAULT 0,
    n_playbooks INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
"""


@dataclass
class SourceRow:
    source_name: str
    extraction_success_rate: float
    card_quality_score: float
    backtest_survival_rate: float
    playbook_clarity_score: float
    n_extraction: int
    n_cards: int
    n_backtests: int
    n_playbooks: int
    updated_at: str

    @property
    def composite(self) -> float:
        return (
            0.25 * self.extraction_success_rate
            + 0.25 * self.card_quality_score
            + 0.30 * self.backtest_survival_rate
            + 0.20 * self.playbook_clarity_score
        )


def _conn(db_path: Path | None = None) -> sqlite3.Connection:
    s = load_settings()
    con = sqlite3.connect(db_path or s.db_path)
    con.executescript(_SCHEMA)
    return con


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_row(con: sqlite3.Connection, source: str) -> None:
    con.execute(
        """INSERT OR IGNORE INTO source_scores
           (source_name, extraction_success_rate, card_quality_score,
            backtest_survival_rate, playbook_clarity_score, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (source, NEUTRAL_DEFAULT, NEUTRAL_DEFAULT, NEUTRAL_DEFAULT, NEUTRAL_DEFAULT, _now()),
    )


def _rolling(current: float, n: int, observation: float) -> tuple[float, int]:
    """Incremental mean update. Caps n at 200 to keep recency adaptive."""
    n_new = min(n + 1, 200)
    new_val = current + (observation - current) / n_new
    return float(max(0.0, min(1.0, new_val))), n_new


def record_extraction(source: str, success: bool, card_confidence: float | None = None) -> None:
    with _conn() as con:
        _ensure_row(con, source)
        row = con.execute(
            "SELECT extraction_success_rate, n_extraction, card_quality_score, n_cards "
            "FROM source_scores WHERE source_name = ?",
            (source,),
        ).fetchone()
        esr, n_ext = _rolling(row[0], row[1], 1.0 if success else 0.0)
        cqs, n_cards = row[2], row[3]
        if success and card_confidence is not None:
            cqs, n_cards = _rolling(row[2], row[3], float(card_confidence))
        con.execute(
            """UPDATE source_scores SET
                 extraction_success_rate=?, n_extraction=?,
                 card_quality_score=?, n_cards=?,
                 updated_at=?
               WHERE source_name=?""",
            (esr, n_ext, cqs, n_cards, _now(), source),
        )


def record_backtest(source: str, survived: bool) -> None:
    """survived = no hard violations + finite score."""
    with _conn() as con:
        _ensure_row(con, source)
        row = con.execute(
            "SELECT backtest_survival_rate, n_backtests FROM source_scores WHERE source_name=?",
            (source,),
        ).fetchone()
        bsr, n_bt = _rolling(row[0], row[1], 1.0 if survived else 0.0)
        con.execute(
            "UPDATE source_scores SET backtest_survival_rate=?, n_backtests=?, updated_at=? "
            "WHERE source_name=?",
            (bsr, n_bt, _now(), source),
        )


def record_playbook(source: str, signal_clarity: float) -> None:
    with _conn() as con:
        _ensure_row(con, source)
        row = con.execute(
            "SELECT playbook_clarity_score, n_playbooks FROM source_scores WHERE source_name=?",
            (source,),
        ).fetchone()
        pcs, n_pb = _rolling(row[0], row[1], float(signal_clarity))
        con.execute(
            "UPDATE source_scores SET playbook_clarity_score=?, n_playbooks=?, updated_at=? "
            "WHERE source_name=?",
            (pcs, n_pb, _now(), source),
        )


def score_for(source: str) -> float:
    """Return composite score for source. Unseen sources -> NEUTRAL_DEFAULT."""
    with _conn() as con:
        row = con.execute(
            """SELECT extraction_success_rate, card_quality_score,
                      backtest_survival_rate, playbook_clarity_score
               FROM source_scores WHERE source_name=?""",
            (source,),
        ).fetchone()
    if not row:
        return NEUTRAL_DEFAULT
    return (
        0.25 * row[0] + 0.25 * row[1] + 0.30 * row[2] + 0.20 * row[3]
    )


def all_scores() -> list[SourceRow]:
    with _conn() as con:
        rows = con.execute(
            """SELECT source_name, extraction_success_rate, card_quality_score,
                      backtest_survival_rate, playbook_clarity_score,
                      n_extraction, n_cards, n_backtests, n_playbooks, updated_at
               FROM source_scores ORDER BY source_name"""
        ).fetchall()
    return [SourceRow(*r) for r in rows]
