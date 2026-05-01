"""Walk-forward evaluation, parameter sensitivity, and ablation helpers.

Backtest execution is delegated to a caller-provided runner so this module
stays testable without external data files or Backtrader.
"""
from __future__ import annotations

import re
import statistics
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Callable

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
    sharpe_decay: float
    pass_fraction: float


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
        window_start = d0 + timedelta(days=i * window)
        window_end = window_start + timedelta(days=window)
        train_end = window_start + timedelta(days=int(window * train_frac))
        out.append(
            (
                window_start.isoformat(),
                train_end.isoformat(),
                (train_end + timedelta(days=1)).isoformat(),
                window_end.isoformat(),
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
    splits: list[WalkForwardSplit] = []
    for train_start, train_end, test_start, test_end in _split_windows(
        start, end, n_splits, train_frac
    ):
        train_stats = runner(code, train_start, train_end)
        test_stats = runner(code, test_start, test_end)
        splits.append(
            WalkForwardSplit(
                train_start,
                train_end,
                test_start,
                test_end,
                train_stats,
                test_stats,
            )
        )

    def _mean(field: str, stats_list: list[dict | None]) -> float:
        vals = [float(s[field]) for s in stats_list if s and field in s]
        return statistics.mean(vals) if vals else 0.0

    mean_test = _mean("sharpe", [s.test_stats for s in splits])
    mean_train = _mean("sharpe", [s.train_stats for s in splits])
    pass_fraction = sum(
        1 for split in splits if split.test_stats and float(split.test_stats.get("sharpe", 0)) > 0
    ) / max(1, len(splits))

    return WalkForwardReport(
        splits=splits,
        mean_test_sharpe=mean_test,
        sharpe_decay=mean_train - mean_test,
        pass_fraction=pass_fraction,
    )


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
    match = matches[idx]
    return code[: match.start()] + f"{new_value:g}" + code[match.end() :]


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
        for multiplier in multipliers:
            new_value = original * multiplier
            mutated = _substitute_nth_number(code, idx, new_value)
            if mutated is None:
                continue
            stats = runner(mutated, start, end)
            values.append(new_value)
            sharpes.append(float((stats or {}).get("sharpe", 0.0)))
        if not sharpes:
            continue
        mean = statistics.mean(sharpes)
        stdev = statistics.pstdev(sharpes) if len(sharpes) > 1 else 0.0
        fragile = base_sharpe > 0 and mean > 0 and (stdev / mean) > fragility_ratio
        out.append(
            ParamSweepResult(
                param_label=f"num[{idx}]={original:g}",
                values=values,
                sharpes=sharpes,
                fragile=fragile,
            )
        )
    return out


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
    """Comment out component lines and flag components that do not affect Sharpe."""
    base_stats = runner(code, start, end)
    base_sharpe = float((base_stats or {}).get("sharpe", 0.0))
    results: list[AblationResult] = []

    for component in components:
        ablated_lines = []
        for line in code.splitlines():
            if component in line and not line.lstrip().startswith("#"):
                ablated_lines.append("# " + line)
            else:
                ablated_lines.append(line)
        stats = runner("\n".join(ablated_lines), start, end)
        ablated_sharpe = float((stats or {}).get("sharpe", 0.0))
        results.append(
            AblationResult(
                component=component,
                baseline_sharpe=base_sharpe,
                ablated_sharpe=ablated_sharpe,
                decorative=(base_sharpe - ablated_sharpe) <= tolerance,
            )
        )
    return results
