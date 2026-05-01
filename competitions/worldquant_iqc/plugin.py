"""WorldQuant BRAIN competition plugin.

No local simulator — BRAIN expressions are evaluated on the WQ platform.
This plugin validates alpha expression syntax and writes .txt output files
(not .py files) since BRAIN takes a DSL expression, not a Python script.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from schema import RoundContext

_KNOWN_OPERATORS = {
    # Cross-sectional
    "rank", "zscore", "scale", "normalize", "sign", "zscore_scale",
    "winsorize_scale", "normed_rank", "cwise_max", "cwise_min",
    "winsorize", "power", "signed_power", "truncate", "vector_neut",
    "vec_avg", "vec_sum", "quantile", "densify", "humpdecay", "bucket",
    # Time-series
    "ts_mean", "ts_std_dev", "ts_rank", "ts_delta", "ts_delay",
    "ts_sum", "ts_min", "ts_max", "ts_corr", "ts_covariance",
    "ts_regression", "ts_decay_linear", "ts_decay_exp_window",
    "ts_arg_max", "ts_arg_min", "ts_product", "ts_backfill", "ts_zscore",
    "ts_corr", "ts_cov", "ts_decayed_linear", "ts_argmax", "ts_argmin",
    "ts_argmaxmin_diff", "ts_max_diff", "ts_min_diff", "ts_median",
    "ts_zscore_scale", "ts_maxmin_scale", "ts_skew", "ts_kurt",
    "ts_delta_ratio", "ts_ema", "ts_percentile", "ts_linear_reg",
    "shift", "delta",
    # Group-wise
    "group_rank", "group_zscore", "group_scale", "group_neutralize",
    "group_mean", "group_backfill", "group_vector_neut", "neutralize",
    "grouped_demean", "grouped_max", "grouped_min", "grouped_sum",
    "grouped_mean", "grouped_std", "grouped_zscore_scale",
    "grouped_winsorize_scale",
    # Element-wise
    "relu", "neg", "abs", "log", "sqrt", "min", "max", "sign",
    "pow", "pow_sign", "round", "add", "minus", "cwise_mul", "div",
    "greater", "less", "normed_rank_diff", "if", "trade_when",
}

_PYTHON_PATTERNS = ["def ", "class ", "import ", "from ", "print(", "return ", "__"]


def _validate(code: str) -> list[str]:
    warnings: list[str] = []
    if not code.strip():
        warnings.append("ERROR: empty expression.")
        return warnings
    for pat in _PYTHON_PATTERNS:
        if pat in code:
            warnings.append(
                f"WARN: expression looks like Python code (found '{pat.strip()}') — "
                "submit only BRAIN DSL expressions to the WQ platform."
            )
    if re.search(r"/\s*\(?(close|open|high|low|volume|cap|vwap)\b(?!\s*\+)", code):
        warnings.append("WARN: possible divide-by-zero — add a small constant (+ 0.0001).")
    lines = [
        line.strip()
        for line in code.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    if lines:
        last = lines[-1]
        if not any(last.startswith(op + "(") for op in ("scale", "rank", "zscore", "group_neutralize", "neutralize")):
            warnings.append(
                "INFO: last line doesn't apply scale/rank/zscore/neutralize — "
                "normalize before submitting to BRAIN."
            )
    return warnings


class WorldQuantBrainPlugin:
    name = "worldquant_iqc"
    output_ext = ".txt"

    def run_backtest(
        self,
        code: str,
        data_path: Path,
        ctx: "RoundContext",
        timeout: int = 60,
        **kwargs,
    ) -> tuple[str, str, int]:
        warnings = _validate(code)
        has_error = any(w.startswith("ERROR") for w in warnings)
        lines = [
            line for line in code.splitlines() if line.strip() and not line.strip().startswith("#")
        ]
        stdout = (
            f"BRAIN alpha expression ready.\n"
            f"Lines: {len(lines)}\n"
            f"Preview: {lines[0][:120] if lines else '(empty)'}\n"
            "\nPaste this expression into the WorldQuant BRAIN IDE, set:\n"
            "  Universe: TOP3000  Neutralization: subindustry  Decay: 0-5  Delay: 1"
        )
        stderr = "\n".join(warnings) if warnings else ""
        return stdout, stderr, 1 if has_error else 0


plugin = WorldQuantBrainPlugin()
