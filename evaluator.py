"""Evaluation layer. Runs generated code and scores results.

Competition-agnostic: all competition-specific execution is delegated to
plugins via the competitions registry. The evaluator never imports
competition code directly.

Contract:
- Plugin or default script MUST print a STRATENGINE_STATS: {...} line.
- Non-zero return code or missing stats line = hard failure.
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

from schema import RoundContext
import family_performance
import competitions

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


def _run_default(
    code: str,
    data_path: Path,
    start: str,
    end: str,
    cash: float,
    timeout: int = 600,
) -> tuple[str, str, int]:
    """Default: run code as a Backtrader script receiving CLI args."""
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(code)
        script_path = Path(f.name)
    try:
        cmd = [
            sys.executable, str(script_path),
            "--data", str(data_path),
            "--start", start,
            "--end", end,
            "--cash", str(cash),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return proc.stdout, proc.stderr, proc.returncode
    finally:
        script_path.unlink(missing_ok=True)


def _dispatch(
    code: str,
    data_path: Path,
    ctx: RoundContext,
    start: str,
    end: str,
    timeout: int = 600,
) -> tuple[str, str, int]:
    """Route to the competition plugin if one exists, else default Backtrader."""
    plugin = competitions.load_plugin(ctx.competition)
    if plugin is not None:
        # Build a shallow ctx copy with the slice dates so the plugin uses them.
        slice_ctx = ctx.model_copy(update={"backtest_start": start, "backtest_end": end})
        return plugin.run_backtest(code, data_path, slice_ctx, timeout=timeout)
    return _run_default(code, data_path, start, end, ctx.starting_capital, timeout)


def _score(stats: dict, round_ctx: RoundContext) -> tuple[float, list[str]]:
    sharpe = float(stats.get("sharpe") or 0.0)
    dd = float(stats.get("max_drawdown") or 0.0)
    turnover = float(stats.get("turnover") or 0.0)
    ret = float(stats.get("total_return") or 0.0)

    violations: list[str] = []
    if round_ctx.max_drawdown is not None and dd > round_ctx.max_drawdown:
        violations.append(f"max_drawdown {dd:.3f} > limit {round_ctx.max_drawdown:.3f}")
    if round_ctx.min_sharpe is not None and sharpe < round_ctx.min_sharpe:
        violations.append(f"sharpe {sharpe:.3f} < limit {round_ctx.min_sharpe:.3f}")
    if round_ctx.max_turnover is not None and turnover > round_ctx.max_turnover:
        violations.append(f"turnover {turnover:.3f} > limit {round_ctx.max_turnover:.3f}")

    if round_ctx.objective == "sharpe":
        base = sharpe
    elif round_ctx.objective == "calmar":
        base = sharpe / max(dd, 0.01)
    elif round_ctx.objective == "total_return":
        base = ret
    else:
        base = sharpe

    if not math.isfinite(base):
        base = -1e9
    return base - 5.0 * len(violations), violations


def _log_family(candidate: dict, round_ctx: RoundContext, result: BacktestResult) -> None:
    family_performance.log_result(
        round_type=round_ctx.competition,
        mode="algo",
        strategy_family=candidate.get("strategy_family", "other"),
        asset_class=candidate.get("asset_class", "unknown"),
        timeframe=candidate.get("timeframe", "multi"),
        sharpe=(result.stats or {}).get("sharpe"),
        drawdown=(result.stats or {}).get("max_drawdown"),
        final_rank=None,
        success=bool(
            result.ok
            and not result.violations
            and (result.stats or {}).get("sharpe", 0) > 0
        ),
    )


def evaluate(
    candidate: dict,
    code: str,
    round_ctx: RoundContext,
    data_path: Path,
    robustness_slices: list[tuple[str, str]] | None = None,
) -> BacktestResult:
    stdout, stderr, rc = _dispatch(
        code, data_path, round_ctx,
        round_ctx.backtest_start, round_ctx.backtest_end,
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
        _log_family(candidate, round_ctx, res)
        return res

    slice_results: list[dict] = []
    for s_start, s_end in robustness_slices or []:
        so, se, sr = _dispatch(code, data_path, round_ctx, s_start, s_end)
        ss = _parse_stats(so)
        slice_results.append({"start": s_start, "end": s_end, "stats": ss, "rc": sr})

    primary_sharpe = float(stats.get("sharpe") or 0.0)
    robustness_penalty = sum(
        1.0
        for s in slice_results
        if primary_sharpe > 0 and float((s.get("stats") or {}).get("sharpe") or 0.0) < 0
    )

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
    _log_family(candidate, round_ctx, res)
    return res


def rank(results: list[BacktestResult]) -> list[BacktestResult]:
    return sorted(results, key=lambda r: r.score, reverse=True)
