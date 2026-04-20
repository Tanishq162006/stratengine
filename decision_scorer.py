"""Decision scorer (manual mode). Scores a playbook on signal clarity, risk
completeness, and source grounding."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PlaybookScore:
    signal_clarity: float  # 0..1
    risk_completeness: float  # 0..1
    source_grounding: float  # 0..1
    invalidation_explicit: bool
    overall: float
    notes: list[str]


def score_playbook(playbook: dict) -> PlaybookScore:
    notes: list[str] = []

    entry_signals = playbook.get("entry_signals", []) or []
    confirmation = playbook.get("confirmation_signals", []) or []
    invalidation = playbook.get("invalidation_criteria", []) or []
    risk = playbook.get("risk_framework", {}) or {}
    checklist = playbook.get("pre_trade_checklist", []) or []

    # signal clarity: specific, non-vague entries
    vague = ("watch", "consider", "monitor", "look for")
    clarity_hits = 0
    for s in entry_signals + confirmation:
        text = (s.get("signal") if isinstance(s, dict) else str(s)) or ""
        if text and not any(v in text.lower() for v in vague):
            clarity_hits += 1
    sc = min(1.0, clarity_hits / 3.0)
    if sc < 0.5:
        notes.append("Entry/confirmation signals are vague or sparse.")

    # risk completeness
    risk_keys = ["stop_placement", "position_sizing", "max_portfolio_risk"]
    have = sum(1 for k in risk_keys if risk.get(k))
    rc = have / len(risk_keys)
    if rc < 1.0:
        notes.append(f"Risk framework missing fields: {[k for k in risk_keys if not risk.get(k)]}")

    # source grounding: fraction of items citing card ids
    def _has_src(item):
        return bool(isinstance(item, dict) and item.get("source_card_ids"))

    items = entry_signals + confirmation + invalidation + checklist + (playbook.get("exit_plan", []) or [])
    sg = (sum(1 for i in items if _has_src(i)) / len(items)) if items else 0.0
    if sg < 0.5:
        notes.append("Few playbook items cite source cards.")

    inv_explicit = len(invalidation) > 0
    if not inv_explicit:
        notes.append("Missing invalidation criteria.")

    overall = 0.4 * sc + 0.3 * rc + 0.2 * sg + 0.1 * (1.0 if inv_explicit else 0.0)
    return PlaybookScore(
        signal_clarity=sc,
        risk_completeness=rc,
        source_grounding=sg,
        invalidation_explicit=inv_explicit,
        overall=overall,
        notes=notes,
    )
