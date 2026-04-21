"""Manual-mode playbook scorer.

Criteria, each in [0, 1]:
  - signal_clarity:     Are entry/exit conditions specific and checkable?
  - risk_completeness:  Are stops, sizing, portfolio limits, correlation defined?
  - cognitive_load:     Can a human execute this under pressure? Fewer steps -> higher.
  - regime_specificity: Does it specify which regime it works in and how to detect exit?
  - historical_scenarios: Does the rule-set produce reasonable results over 3-5 real
                          historical windows using locally cached price data?

A composite is computed as a weighted sum. Missing historical data raises a
clear error rather than silently zero-scoring.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import pandas as pd


VAGUE_TOKENS = ("watch", "consider", "monitor", "look for", "be aware", "as needed")


@dataclass
class ScorerWeights:
    signal_clarity: float = 0.25
    risk_completeness: float = 0.20
    cognitive_load: float = 0.15
    regime_specificity: float = 0.15
    historical_scenarios: float = 0.25

    def normalize(self) -> "ScorerWeights":
        total = (
            self.signal_clarity
            + self.risk_completeness
            + self.cognitive_load
            + self.regime_specificity
            + self.historical_scenarios
        )
        if total <= 0:
            raise ValueError("ScorerWeights must sum to a positive value.")
        return ScorerWeights(
            self.signal_clarity / total,
            self.risk_completeness / total,
            self.cognitive_load / total,
            self.regime_specificity / total,
            self.historical_scenarios / total,
        )


# Canonical scenario windows — real dates, not synthetic.
DEFAULT_SCENARIOS: list[tuple[str, str, str]] = [
    ("2020-covid", "2020-02-15", "2020-04-30"),
    ("2022-rate-hikes", "2022-01-01", "2022-10-31"),
    ("2023-ai-rally", "2023-01-01", "2023-12-31"),
    ("2018-q4-selloff", "2018-10-01", "2018-12-31"),
    ("2015-aug-flash-crash", "2015-08-01", "2015-09-30"),
]


@dataclass
class ScenarioResult:
    name: str
    start: str
    end: str
    score: float  # 0..1 per-scenario
    notes: str


@dataclass
class PlaybookScore:
    signal_clarity: float
    risk_completeness: float
    cognitive_load: float
    regime_specificity: float
    historical_scenarios: float
    composite: float
    scenarios: list[ScenarioResult] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _flatten_checklist(items) -> list[str]:
    """Accept a list[str] or dict[str, list[str]] (exit_checklist case) and flatten."""
    if items is None:
        return []
    if isinstance(items, list):
        return [str(x) for x in items]
    if isinstance(items, dict):
        out: list[str] = []
        for v in items.values():
            if isinstance(v, list):
                out.extend(str(x) for x in v)
            elif v is not None:
                out.append(str(v))
        return out
    return [str(items)]


def _score_signal_clarity(playbook: dict) -> tuple[float, list[str]]:
    notes: list[str] = []
    entry = _flatten_checklist(playbook.get("entry_checklist"))
    exit_ = _flatten_checklist(playbook.get("exit_checklist"))
    regime = _flatten_checklist(
        (playbook.get("regime_detection") or {}).get("current_regime_rules")
    )
    all_items = entry + exit_ + regime
    if not all_items:
        return 0.0, ["no checklist items"]

    specific = 0
    for item in all_items:
        lo = item.lower()
        if any(tok in lo for tok in VAGUE_TOKENS):
            continue
        # Heuristic: specific items tend to include numbers, operators, or named indicators.
        if any(ch.isdigit() for ch in item) or any(op in item for op in ("<", ">", "=", "%")):
            specific += 1
        elif len(item.split()) >= 5:
            specific += 0  # long prose alone isn't specific
    score = specific / len(all_items)
    if score < 0.5:
        notes.append("Entry/exit/regime items lack quantitative specificity.")
    return min(1.0, score), notes


def _score_risk_completeness(playbook: dict) -> tuple[float, list[str]]:
    notes: list[str] = []
    risk = playbook.get("risk_protocol") or {}
    sizing = playbook.get("sizing_framework") or {}
    required = {
        "max_position_pct": risk.get("max_position_pct"),
        "max_portfolio_drawdown_pct": risk.get("max_portfolio_drawdown_pct"),
        "sizing_method": (sizing.get("method") if isinstance(sizing, dict) else None),
        "stop_loss_defined": bool(
            _flatten_checklist((playbook.get("exit_checklist") or {}))
        )
        if not isinstance(playbook.get("exit_checklist"), dict)
        else bool((playbook.get("exit_checklist") or {}).get("stop_loss")),
        "correlation_limits": risk.get("correlation_limits"),
    }
    have = sum(1 for v in required.values() if v)
    score = have / len(required)
    missing = [k for k, v in required.items() if not v]
    if missing:
        notes.append(f"risk/sizing fields missing: {missing}")
    return score, notes


def _score_cognitive_load(playbook: dict) -> tuple[float, list[str]]:
    """Fewer steps -> higher score. 5-7 steps is the sweet spot."""
    total_steps = 0
    total_steps += len(_flatten_checklist(playbook.get("entry_checklist")))
    total_steps += len(_flatten_checklist(playbook.get("exit_checklist")))
    if total_steps == 0:
        return 0.0, ["no steps"]
    # Optimal ~6 steps. Penalize both ends.
    dist = abs(total_steps - 6)
    score = max(0.0, 1.0 - dist / 10.0)
    notes: list[str] = []
    if total_steps > 15:
        notes.append(f"Too many steps ({total_steps}) to execute under pressure.")
    elif total_steps < 3:
        notes.append("Too few steps; likely under-specified.")
    return score, notes


def _score_regime_specificity(playbook: dict) -> tuple[float, list[str]]:
    notes: list[str] = []
    regime = playbook.get("regime_detection") or {}
    rules = _flatten_checklist(regime.get("current_regime_rules"))
    invalid = _flatten_checklist(regime.get("invalidation_signals"))
    if not rules and not invalid:
        return 0.0, ["no regime detection defined"]
    score = 0.0
    if rules:
        score += 0.5
    if invalid:
        score += 0.5
    if not invalid:
        notes.append("Missing invalidation signals — can't tell when to stop trading this.")
    return score, notes


class MissingHistoricalDataError(RuntimeError):
    """Raised when the scenario scorer cannot locate required price data."""


def _default_scenario_evaluator(
    playbook: dict,
    start: str,
    end: str,
    data_dir: Path,
) -> tuple[float, str]:
    """Stub scenario evaluator. Loads a CSV from data_dir/<symbol>.csv for the
    first symbol hinted by the playbook/context and does a crude regime check:
    score 0.5 baseline, +0.25 if drawdown over window < 20%, +0.25 if final
    return > 0. This is intentionally simple — the scorer's job is to refuse
    to run without real data, not to be a full backtester.
    """
    symbol_hint = None
    rules = _flatten_checklist((playbook.get("regime_detection") or {}).get("current_regime_rules"))
    for r in rules:
        for tok in r.split():
            up = tok.strip(",.():;").upper()
            if up.isalpha() and 1 < len(up) <= 5:
                symbol_hint = up
                break
        if symbol_hint:
            break
    symbol = symbol_hint or "SPY"

    csv_path = data_dir / f"{symbol}.csv"
    if not csv_path.exists():
        # Attempt auto-fetch via Stooq before raising.
        try:
            import price_fetcher
            price_fetcher.PRICES_DIR = data_dir
            price_fetcher.fetch(symbol, start="2015-01-01", save=True)
        except Exception as fetch_err:
            raise MissingHistoricalDataError(
                f"No historical CSV for scenario evaluation: {csv_path}. "
                f"Auto-fetch also failed: {fetch_err}. "
                f"Run: stratengine fetch-prices {symbol}"
            ) from fetch_err
        if not csv_path.exists():
            raise MissingHistoricalDataError(
                f"Auto-fetch ran but {csv_path} still missing."
            )
    df = pd.read_csv(csv_path)
    df["date"] = pd.to_datetime(df["date"])
    window = df[(df["date"] >= start) & (df["date"] <= end)]
    if window.empty:
        raise MissingHistoricalDataError(
            f"CSV {csv_path} has no rows between {start} and {end}."
        )
    close = window["close"].to_numpy()
    ret = (close[-1] / close[0]) - 1.0
    peak = close[0]
    max_dd = 0.0
    for c in close:
        if c > peak:
            peak = c
        dd = (peak - c) / peak
        if dd > max_dd:
            max_dd = dd
    score = 0.5
    if max_dd < 0.20:
        score += 0.25
    if ret > 0:
        score += 0.25
    return min(1.0, score), f"{symbol} {start}..{end} ret={ret:+.2%} maxDD={max_dd:.2%}"


def _score_historical_scenarios(
    playbook: dict,
    scenarios: list[tuple[str, str, str]],
    data_dir: Path,
    evaluator: Callable[[dict, str, str, Path], tuple[float, str]] | None,
) -> tuple[float, list[ScenarioResult], list[str]]:
    if not scenarios:
        return 0.0, [], ["no scenarios configured"]
    eval_fn = evaluator or _default_scenario_evaluator
    results: list[ScenarioResult] = []
    for name, start, end in scenarios:
        # Intentionally let MissingHistoricalDataError propagate.
        score, note = eval_fn(playbook, start, end, data_dir)
        if not (0.0 <= score <= 1.0) or not math.isfinite(score):
            raise ValueError(f"Scenario {name} returned invalid score {score!r}")
        results.append(ScenarioResult(name=name, start=start, end=end, score=score, notes=note))
    mean = statistics.mean(r.score for r in results)
    return mean, results, []


def score_playbook(
    playbook: dict,
    *,
    weights: ScorerWeights | None = None,
    scenarios: list[tuple[str, str, str]] | None = None,
    data_dir: Path | None = None,
    scenario_evaluator: Callable[[dict, str, str, Path], tuple[float, str]] | None = None,
    skip_scenarios: bool = False,
) -> PlaybookScore:
    w = (weights or ScorerWeights()).normalize()
    notes: list[str] = []

    sc, n = _score_signal_clarity(playbook)
    notes.extend(n)
    rc, n = _score_risk_completeness(playbook)
    notes.extend(n)
    cl, n = _score_cognitive_load(playbook)
    notes.extend(n)
    rs, n = _score_regime_specificity(playbook)
    notes.extend(n)

    if skip_scenarios:
        hs, scenario_results = 0.0, []
        notes.append("Scenario scoring skipped.")
    else:
        hs, scenario_results, sn = _score_historical_scenarios(
            playbook,
            scenarios or DEFAULT_SCENARIOS,
            data_dir or Path("data/prices"),
            scenario_evaluator,
        )
        notes.extend(sn)

    composite = (
        w.signal_clarity * sc
        + w.risk_completeness * rc
        + w.cognitive_load * cl
        + w.regime_specificity * rs
        + w.historical_scenarios * (0.0 if skip_scenarios else hs)
    )
    # If scenarios skipped, redistribute their weight proportionally.
    if skip_scenarios:
        remaining = (
            w.signal_clarity
            + w.risk_completeness
            + w.cognitive_load
            + w.regime_specificity
        )
        if remaining > 0:
            composite = composite / remaining

    for v in (sc, rc, cl, rs, hs, composite):
        if not (0.0 <= v <= 1.0 + 1e-9):
            raise ValueError(f"score outside [0,1]: {v}")

    return PlaybookScore(
        signal_clarity=sc,
        risk_completeness=rc,
        cognitive_load=cl,
        regime_specificity=rs,
        historical_scenarios=hs,
        composite=min(1.0, composite),
        scenarios=scenario_results,
        notes=notes,
    )
