"""Per-family performance memory. Logged after every evaluation."""
from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass

from config import load_settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS family_performance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    round_type TEXT NOT NULL,
    mode TEXT NOT NULL,                -- 'algo' | 'manual'
    strategy_family TEXT NOT NULL,
    asset_class TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    sharpe REAL,
    drawdown REAL,
    composite REAL,
    final_rank INTEGER,
    success INTEGER NOT NULL,          -- 0 or 1
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fp_family ON family_performance(strategy_family);
CREATE INDEX IF NOT EXISTS idx_fp_round ON family_performance(round_type);
"""


def _conn() -> sqlite3.Connection:
    s = load_settings()
    con = sqlite3.connect(s.db_path)
    con.executescript(_SCHEMA)
    return con


def log_result(
    round_type: str,
    mode: str,
    strategy_family: str,
    asset_class: str,
    timeframe: str,
    *,
    sharpe: float | None = None,
    drawdown: float | None = None,
    composite: float | None = None,
    final_rank: int | None = None,
    success: bool = False,
) -> None:
    with _conn() as con:
        con.execute(
            """INSERT INTO family_performance
               (round_type, mode, strategy_family, asset_class, timeframe,
                sharpe, drawdown, composite, final_rank, success, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                round_type,
                mode,
                strategy_family,
                asset_class,
                timeframe,
                sharpe,
                drawdown,
                composite,
                final_rank,
                1 if success else 0,
                time.time(),
            ),
        )


@dataclass
class FamilyWinRate:
    family: str
    n: int
    wins: int

    @property
    def rate(self) -> float:
        return self.wins / self.n if self.n else 0.0


def win_rates(round_type: str | None = None) -> list[FamilyWinRate]:
    query = "SELECT strategy_family, SUM(success), COUNT(*) FROM family_performance"
    params: tuple = ()
    if round_type:
        query += " WHERE round_type = ?"
        params = (round_type,)
    query += " GROUP BY strategy_family"
    with _conn() as con:
        rows = con.execute(query, params).fetchall()
    return [FamilyWinRate(family=r[0], n=int(r[2]), wins=int(r[1] or 0)) for r in rows]


NEUTRAL_BOOST = 1.0


def boost_for(family: str, round_type: str | None = None) -> float:
    """Return a bounded multiplier in [0.5, 1.5] based on historical win rate.

    Unseen family -> NEUTRAL_BOOST (1.0). Saturates past n=30.
    """
    rates = {r.family: r for r in win_rates(round_type)}
    r = rates.get(family)
    if r is None or r.n == 0:
        return NEUTRAL_BOOST
    confidence = min(1.0, r.n / 30.0)  # blend toward neutral when sample small
    # win rate 0.5 -> neutral; 1.0 -> 1.5; 0.0 -> 0.5
    adj = 1.0 + (r.rate - 0.5) * confidence
    return max(0.5, min(1.5, adj))
