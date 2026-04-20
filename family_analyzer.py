"""Thin wrappers around family_performance for reporting."""
from __future__ import annotations

from family_performance import FamilyWinRate, win_rates


def ranked_win_rates(round_type: str | None = None) -> list[FamilyWinRate]:
    rows = win_rates(round_type)
    rows.sort(key=lambda r: r.rate, reverse=True)
    return rows
