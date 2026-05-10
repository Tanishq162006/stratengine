"""WorldQuant BRAIN competition plugin.

No local simulator — BRAIN expressions are evaluated on the WQ platform.
This plugin validates alpha expression syntax against the WorldQuant Fast
Expression standard and rejects expressions that would be guaranteed to fail
the platform compiler or violate the 8 BRAIN submission criteria. Anything
caught here bounces back to the model instead of wasting a manual paste.
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
    "vec_avg", "vec_sum", "vec_max", "vec_min", "kth_element",
    "quantile", "densify", "humpdecay", "hump", "jump_decay",
    "pasteurize", "bucket",
    # Time-series
    "ts_mean", "ts_std_dev", "ts_rank", "ts_delta", "ts_delay",
    "ts_sum", "ts_min", "ts_max", "ts_corr", "ts_covariance",
    "ts_regression", "ts_decay_linear", "ts_decay_exp_window",
    "ts_arg_max", "ts_arg_min", "ts_product", "ts_backfill", "ts_zscore",
    "ts_cov", "ts_decayed_linear", "ts_argmax", "ts_argmin",
    "ts_argmaxmin_diff", "ts_max_diff", "ts_min_diff", "ts_median",
    "ts_zscore_scale", "ts_maxmin_scale", "ts_skew", "ts_kurt",
    "ts_delta_ratio", "ts_ema", "ts_percentile", "ts_linear_reg",
    "ts_returns", "ts_step", "ts_partial_corr", "ts_kendall",
    "ts_co_skewness", "ts_co_kurtosis", "ts_quantile", "ts_av_diff",
    "last_diff_value", "convert_unit",
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
    "greater", "less", "normed_rank_diff", "if", "if_else", "trade_when",
    "nan_mask", "keep",
}

_KNOWN_FIELDS = {
    # Price-volume (universal)
    "close", "open", "high", "low", "volume", "vwap", "returns",
    "cap", "adv20", "beta", "split", "dividend",
    # Named fundamentals (sparse — require ts_backfill)
    "equity", "debt", "ebitda", "revenues", "sales", "operating_income",
    "assets", "retained_earnings", "inventory", "enterprise_value",
    "sharesout",
    # Compustat fnd1..fnd28
    *{f"fnd{i}" for i in range(1, 29)},
    # IBES / estimates (subscription-dependent)
    "eps_est_curr_qtr", "eps_est_curr_yr", "eps_est_next_yr",
    "sales_est_curr_qtr", "eps_actual", "eps_surprise",
    "analyst_rating", "target_price", "revisions_up", "revisions_down",
    # Group keys
    "market", "sector", "industry", "subindustry", "country", "exchange",
    # Derived helpers commonly used in seminar examples
    "rel_ret_comp",
}

# Field-family prefixes that BRAIN exposes through subscribed datasets.
# Match-by-prefix so we don't false-positive on legit fields the catalog
# doesn't enumerate (model fundamentals, news vectors, sentiment, options,
# PV-grouping models, etc.). These are genuine BRAIN dataset families
# documented in the WQ seminar materials.
_KNOWN_FIELD_PREFIXES = (
    "mdf_",        # Model Data Fundamentals (mdf_oey, mdf_gry, mdf_nps, mdf_pbk, ...)
    "mdl",         # China model variants (mdl175_volatility, mdl175_revenuettm, ...)
    "nws",         # News (nws12_afterhsz_sl, nws12_afterhsz_maxupamt, ...)
    "snt_",        # Sentiment (snt_buzz_ret, ...)
    "scl",         # Social/buzz (scl12_alltype_buzzvec, ...)
    "pcr_",        # Put/Call ratios (pcr_vol_10, ...)
    "pv",          # PV grouping models (pv13_r2_min20_3000_sector, ...)
    "implied_volatility",  # implied_volatility_call_60, implied_volatility_put_720, ...
    "call_breakeven",
    "put_breakeven",
    "fnd",         # already covered by enumerated fnd1..fnd28 but keep prefix as fallback
    "eps_",
    "sales_",
    "analyst_",
    "target_",
    "revisions_",
)


def _is_known_field(ident: str) -> bool:
    if ident in _KNOWN_FIELDS:
        return True
    return any(ident.startswith(p) for p in _KNOWN_FIELD_PREFIXES)

_PYTHON_PATTERNS = ["def ", "class ", "import ", "from ", "print(", "return ", "__"]

# Adding a bare integer/float to a typed field produces a unit warning on
# BRAIN. Caught here so refine/code passes can self-correct.
_TYPED_UNIT_FIELDS = ("volume", "close", "open", "high", "low", "vwap",
                      "cap", "adv20", "sharesout")
_UNIT_OFFENDER = re.compile(
    r"\b(" + "|".join(_TYPED_UNIT_FIELDS) + r")\s*\+\s*\d+(?:\.\d+)?\b"
)
_BARE_DIVIDE = re.compile(
    r"/\s*\(?(close|open|high|low|volume|cap|vwap|adv20)\b(?!\s*[+\-])"
)
_VAR_ASSIGN = re.compile(r"^\s*[A-Za-z_]\w*\s*=\s*[^=]")
_WINSORIZE_BAD = re.compile(r"\bwinsorize\s*\(\s*[^,()]*?,\s*[^)]+\)")


def _strip_outer(name: str, expr: str) -> str | None:
    """If expr is `name(...)`, return inner; else None."""
    pat = re.compile(rf"^\s*{name}\s*\((.*)\)\s*$", re.DOTALL)
    m = pat.match(expr)
    return m.group(1) if m else None


def _validate(code: str) -> list[str]:
    warnings: list[str] = []
    if not code.strip():
        warnings.append("ERROR: empty expression.")
        return warnings

    for pat in _PYTHON_PATTERNS:
        if pat in code:
            warnings.append(
                f"ERROR: expression contains Python (found '{pat.strip()}'). "
                "BRAIN takes a single nested DSL expression, not Python code."
            )

    raw_lines = [
        line for line in code.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    # BRAIN Fast Expression must be ONE nested expression. Multiple
    # statements with semicolons or assignments break the compiler.
    for line in raw_lines:
        if _VAR_ASSIGN.match(line):
            warnings.append(
                "ERROR: variable assignment detected. BRAIN Fast Expression "
                "must be a single nested expression — no `x = ...` allowed."
            )
            break
    if len(raw_lines) > 1 and not all(
        line.rstrip().endswith(("(", ",", "+", "-", "*", "/")) or
        line.lstrip().startswith((")", ","))
        for line in raw_lines[:-1]
    ):
        warnings.append(
            "WARN: expression spans multiple statements. BRAIN expects a "
            "single nested expression on one logical line."
        )

    expr = " ".join(line.strip() for line in raw_lines)

    # Outermost MUST be scale(...) — sum(|w|) == 1 requirement.
    inside_scale = _strip_outer("scale", expr)
    if inside_scale is None:
        warnings.append(
            "ERROR: expression must end with scale(...) so weights sum to 1 "
            "in absolute value. Wrap the outermost call in scale()."
        )
    else:
        # Inside scale() should be group_neutralize / neutralize for
        # Sub-universe Sharpe > 0.45.
        if not re.search(r"\b(group_neutralize|neutralize|group_zscore|grouped_zscore_scale)\s*\(",
                         inside_scale):
            warnings.append(
                "WARN: no group_neutralize(..., subindustry) inside scale(). "
                "Sub-universe Sharpe (>0.45) usually fails without sector neutralization."
            )

    # winsorize must take exactly 1 argument.
    for m in _WINSORIZE_BAD.finditer(code):
        warnings.append(
            f"ERROR: winsorize() takes exactly 1 argument in BRAIN: "
            f"`{m.group(0)}` has extra args. Use `winsorize(x)` only."
        )

    # Adding bare integer to typed field — unit warning on BRAIN.
    for m in _UNIT_OFFENDER.finditer(code):
        warnings.append(
            f"ERROR: unit mismatch — `{m.group(0)}` adds a dimensionless "
            "constant to a typed field. Use ratios or a same-unit term instead."
        )

    # Divide-by-potentially-zero without offset.
    if _BARE_DIVIDE.search(code):
        warnings.append(
            "WARN: division by a typed field without offset detected. "
            "Always use `/ (field + 0.0001)` to avoid divide-by-zero."
        )

    # Operator and field whitelist check (catches hallucinated names).
    tokens = re.findall(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b", code)
    func_calls = set(re.findall(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", code))
    for fn in sorted(func_calls):
        if fn not in _KNOWN_OPERATORS and fn not in {"if", "and", "or", "not"}:
            warnings.append(
                f"ERROR: unknown operator `{fn}`. Not in the BRAIN operator "
                "catalog — check spelling or use a documented equivalent."
            )
    bare_ids = [
        t for t in tokens
        if t not in func_calls
        and t not in _KNOWN_OPERATORS
        and not t.isdigit()
        and t not in {"True", "False", "None", "and", "or", "not", "if", "else"}
    ]
    for ident in sorted(set(bare_ids)):
        if _is_known_field(ident):
            continue
        # Skip purely numeric or constant-style.
        if re.fullmatch(r"[A-Z_]+", ident) or len(ident) <= 1:
            continue
        warnings.append(
            f"WARN: identifier `{ident}` is not in the BRAIN field catalog. "
            "Verify it exists in your subscribed datasets."
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
            "  Universe: TOP3000  Neutralization: subindustry  Decay: 0-5  Delay: 1\n"
            "\nWorldQuant submission gate (all 8 must pass):\n"
            "  Sharpe > 1.25 | Turnover 1-70% | Fitness > 1.0 | Sub-Sharpe > 0.45\n"
            "  Weight distributed | Self-corr pass | Competitions match | Syntax clean"
        )
        stderr = "\n".join(warnings) if warnings else ""
        return stdout, stderr, 1 if has_error else 0


plugin = WorldQuantBrainPlugin()
