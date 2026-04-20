"""Evaluation layer. Runs generated Backtrader code and scores results.

The evaluator is intentionally strict:
- Runs the candidate's code as a subprocess against a user-supplied CSV.
- Looks for a `STRATENGINE_STATS:` line on stdout containing metrics JSON.
- Scores on Sharpe, max drawdown, turnover, total return, robustness (multi-slice).
- Candidates without a STRATENGINE_STATS line fail with a clear error, they are NOT silently ranked.
"""
from __future__ import annotations

import json
import math
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console

from schema import RoundContext
import family_performance

console = Console()

_STATS_RE = re.compile(r"^STRATENGINE_STATS:\s*(\{.*\})\s*$", re.MULTILINE)


@dataclass
class BacktestResult:
    candidate_name: str
    ok: bool
    stats: dict
    stdout: str
    stderr: str
    slice_stats: list[dict]
    score: float
    violations: list[str]


def _parse_stats(stdout: str) -> dict | None:
    m = _STATS_RE.search(stdout)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def _run_script(
    code: str,
    data_path: Path,
    start: str,
    end: str,
    cash: float,
    timeout: int = 600,
) -> tuple[str, str, int]:
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(code)
        script_path = Path(f.name)
    try:
        proc = subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--data",
                str(data_path),
                "--start",
                start,
                "--end",
                end,
                "--cash",
                str(cash),
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.stdout, proc.stderr, proc.returncode
    finally:
        script_path.unlink(missing_ok=True)


def _score(stats: dict, round_ctx: RoundContext) -> tuple[float, list[str]]:
    """Higher is better. Violations reduce score heavily."""
    sharpe = float(stats.get("sharpe") or 0.0)
    dd = float(stats.get("max_drawdown") or 0.0)  # expect positive fraction
    turnover = float(stats.get("turnover") or 0.0)
    ret = float(stats.get("total_return") or 0.0)

    violations: list[str] = []
    if round_ctx.max_drawdown is not None and dd > round_ctx.max_drawdown:
        violations.append(f"max_drawdown {dd:.3f} > limit {round_ctx.max_drawdown:.3f}")
    if round_ctx.min_sharpe is not None and sharpe < round_ctx.min_sharpe:
        violations.append(f"sharpe {sharpe:.3f} < limit {round_ctx.min_sharpe:.3f}")
    if round_ctx.max_turnover is not None and turnover > round_ctx.max_turnover:
        violations.append(f"turnover {turnover:.3f} > limit {round_ctx.max_turnover:.3f}")

    objective = round_ctx.objective
    if objective == "sharpe":
        base = sharpe
    elif objective == "calmar":
        base = sharpe / max(dd, 0.01)
    elif objective == "total_return":
        base = ret
    else:
        base = sharpe

    if not math.isfinite(base):
        base = -1e9
    penalty = 5.0 * len(violations)
    return base - penalty, violations


def _log_family_outcome(candidate: dict, round_ctx: RoundContext, result: "BacktestResult") -> None:
    family_performance.log_result(
        round_type=round_ctx.competition,
        mode="algo",
        strategy_family=candidate.get("strategy_family", "other"),
        asset_class=candidate.get("asset_class", "unknown"),
        timeframe=candidate.get("timeframe", "multi"),
        sharpe=(result.stats or {}).get("sharpe"),
        drawdown=(result.stats or {}).get("max_drawdown"),
        final_rank=None,  # filled in by caller after ranking, optional
        success=bool(result.ok and not result.violations and (result.stats or {}).get("sharpe", 0) > 0),
    )


def evaluate(
    candidate: dict,
    code: str,
    round_ctx: RoundContext,
    data_path: Path,
    robustness_slices: list[tuple[str, str]] | None = None,
) -> BacktestResult:
    """Run primary backtest + optional robustness slices."""
    cash = round_ctx.starting_capital
    stdout, stderr, rc = _run_script(
        code, data_path, round_ctx.backtest_start, round_ctx.backtest_end, cash
    )
    stats = _parse_stats(stdout)
    ok = rc == 0 and stats is not None
    if not ok:
        res = BacktestResult(
            candidate_name=candidate.get("name", "unnamed"),
            ok=False,
            stats=stats or {},
            stdout=stdout,
            stderr=stderr,
            slice_stats=[],
            score=-1e9,
            violations=["backtest did not return STRATENGINE_STATS"],
        )
        _log_family_outcome(candidate, round_ctx, res)
        return res

    slice_results: list[dict] = []
    for s_start, s_end in robustness_slices or []:
        so, se, sr = _run_script(code, data_path, s_start, s_end, cash)
        ss = _parse_stats(so)
        slice_results.append({"start": s_start, "end": s_end, "stats": ss, "rc": sr})

    # Robustness penalty: if any slice Sharpe < 0 when primary > 0, penalize.
    robustness_penalty = 0.0
    primary_sharpe = float(stats.get("sharpe") or 0.0)
    for s in slice_results:
        ss = s.get("stats") or {}
        sh = float(ss.get("sharpe") or 0.0)
        if primary_sharpe > 0 and sh < 0:
            robustness_penalty += 1.0

    base_score, violations = _score(stats, round_ctx)
    res = BacktestResult(
        candidate_name=candidate.get("name", "unnamed"),
        ok=True,
        stats=stats,
        stdout=stdout,
        stderr=stderr,
        slice_stats=slice_results,
        score=base_score - robustness_penalty,
        violations=violations,
    )
    _log_family_outcome(candidate, round_ctx, res)
    return res


def rank(results: list[BacktestResult]) -> list[BacktestResult]:
    return sorted(results, key=lambda r: r.score, reverse=True)
