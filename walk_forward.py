"""Walk-forward evaluation, parameter sensitivity, ablation. The actual
backtest execution is delegated to a user-supplied runner so this module is
testable without Backtrader + data files.
"""
from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Callable

# runner signature: (code, start, end) -> stats dict OR None on failure
Runner = Callable[[str, str, str], dict | None]


@dataclass
class WalkForwardSplit:
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    train_stats: dict | None
    test_stats: dict | None


@dataclass
class WalkForwardReport:
    splits: list[WalkForwardSplit]
    mean_test_sharpe: float
    sharpe_decay: float  # mean_train_sharpe - mean_test_sharpe (positive => overfit)
    pass_fraction: float  # fraction of splits with test sharpe > 0


def _split_windows(
    start: str, end: str, n_splits: int, train_frac: float
) -> list[tuple[str, str, str, str]]:
    d0 = date.fromisoformat(start)
    d1 = date.fromisoformat(end)
    total = (d1 - d0).days
    if total <= 30 or n_splits <= 0:
        raise ValueError("Window too short or n_splits invalid for walk-forward.")
    window = total // n_splits
    out: list[tuple[str, str, str, str]] = []
    for i in range(n_splits):
        ws = d0 + timedelta(days=i * window)
        we = ws + timedelta(days=window)
        train_end = ws + timedelta(days=int(window * train_frac))
        out.append(
            (
                ws.isoformat(),
                train_end.isoformat(),
                (train_end + timedelta(days=1)).isoformat(),
                we.isoformat(),
            )
        )
    return out


def walk_forward(
    code: str,
    start: str,
    end: str,
    runner: Runner,
    *,
    n_splits: int = 4,
    train_frac: float = 0.7,
) -> WalkForwardReport:
    splits_raw = _split_windows(start, end, n_splits, train_frac)
    splits: list[WalkForwardSplit] = []
    for ts, te, ts2, te2 in splits_raw:
        train_stats = runner(code, ts, te)
        test_stats = runner(code, ts2, te2)
        splits.append(WalkForwardSplit(ts, te, ts2, te2, train_stats, test_stats))

    def _mean(field: str, stats_list: list[dict | None]) -> float:
        vals = [float(s[field]) for s in stats_list if s and field in s]
        return statistics.mean(vals) if vals else 0.0

    mean_test = _mean("sharpe", [s.test_stats for s in splits])
    mean_train = _mean("sharpe", [s.train_stats for s in splits])
    pass_frac = sum(
        1 for s in splits if s.test_stats and float(s.test_stats.get("sharpe", 0)) > 0
    ) / max(1, len(splits))

    return WalkForwardReport(
        splits=splits,
        mean_test_sharpe=mean_test,
        sharpe_decay=mean_train - mean_test,
        pass_fraction=pass_frac,
    )


# ------------------------------ parameter sweep ------------------------------

_NUM_RE = re.compile(r"(?<![\w.])(-?\d+(?:\.\d+)?)(?![\w.])")


@dataclass
class ParamSweepResult:
    param_label: str
    values: list[float]
    sharpes: list[float]
    fragile: bool


def _substitute_nth_number(code: str, idx: int, new_value: float) -> str | None:
    """Replace the idx-th numeric literal in code with new_value."""
    matches = list(_NUM_RE.finditer(code))
    if idx >= len(matches):
        return None
    m = matches[idx]
    before = code[: m.start()]
    after = code[m.end() :]
    rendered = f"{new_value:g}"
    return before + rendered + after


def param_sweep(
    code: str,
    start: str,
    end: str,
    runner: Runner,
    *,
    param_indices: list[int],
    multipliers: tuple[float, ...] = (0.5, 0.75, 1.0, 1.25, 1.5),
    fragility_ratio: float = 0.5,
) -> list[ParamSweepResult]:
    out: list[ParamSweepResult] = []
    matches = list(_NUM_RE.finditer(code))
    base_stats = runner(code, start, end)
    base_sharpe = float((base_stats or {}).get("sharpe", 0.0))
    for idx in param_indices:
        if idx >= len(matches):
            continue
        original = float(matches[idx].group(0))
        values: list[float] = []
        sharpes: list[float] = []
        for mult in multipliers:
            new_val = original * mult
            mutated = _substitute_nth_number(code, idx, new_val)
            if mutated is None:
                continue
            stats = runner(mutated, start, end)
            values.append(new_val)
            sharpes.append(float((stats or {}).get("sharpe", 0.0)))
        if not sharpes:
            continue
        mean = statistics.mean(sharpes) if sharpes else 0.0
        stdev = statistics.pstdev(sharpes) if len(sharpes) > 1 else 0.0
        fragile = False
        if base_sharpe > 0 and mean > 0:
            fragile = (stdev / mean) > fragility_ratio
        out.append(
            ParamSweepResult(
                param_label=f"num[{idx}]={original:g}",
                values=values,
                sharpes=sharpes,
                fragile=fragile,
            )
        )
    return out


# ------------------------------ ablation ------------------------------

@dataclass
class AblationResult:
    component: str
    baseline_sharpe: float
    ablated_sharpe: float
    decorative: bool


def ablation(
    code: str,
    start: str,
    end: str,
    runner: Runner,
    *,
    components: list[str],
    tolerance: float = 0.05,
) -> list[AblationResult]:
    """For each component string (e.g. 'self.atr'), comment out lines mentioning
    it and re-run. If ablated Sharpe is not materially lower, flag as decorative.
    """
    base_stats = runner(code, start, end)
    base_sharpe = float((base_stats or {}).get("sharpe", 0.0))
    results: list[AblationResult] = []
    for comp in components:
        lines = code.splitlines()
        ablated = []
        for ln in lines:
            if comp in ln and not ln.lstrip().startswith("#"):
                ablated.append("# " + ln)
            else:
                ablated.append(ln)
        mutated = "\n".join(ablated)
        stats = runner(mutated, start, end)
        ablated_sharpe = float((stats or {}).get("sharpe", 0.0))
        decorative = (base_sharpe - ablated_sharpe) <= tolerance
        results.append(
            AblationResult(
                component=comp,
                baseline_sharpe=base_sharpe,
                ablated_sharpe=ablated_sharpe,
                decorative=decorative,
            )
        )
    return results
