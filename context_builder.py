"""Context builder: parse a free-text prompt into a RoundContext or TradingContext.

Uses an LLM call to extract structured fields so users can write natural-language
prompts like "IMC Round 3 KELP market making, position limit 50" instead of
hand-crafting JSON.
"""
from __future__ import annotations

import json
import re

from config import PROMPTS_DIR, load_settings
from schema import RoundContext, TradingContext
import llm_client
import prompt_logger

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)

_TEMPLATE_DEFAULTS: dict[str, dict] = {
    "imc_prosperity": {
        "competition": "imc_prosperity",
        "round_name": "Round 1",
        "asset_classes": ["multi_asset"],
        "timeframe": "1m",
        "backtest_start": "2026-04-14",
        "backtest_end": "2026-04-17",
        "starting_capital": 0.0,
        "max_leverage": 1.0,
        "transaction_cost_bps": 0.0,
        "slippage_bps": 0.0,
        "objective": "total_return",
        "preferred_strategy_families": ["market_making", "mean_reversion", "arbitrage"],
    },
    "worldquant_iqc": {
        "competition": "worldquant_iqc",
        "round_name": "Round 1",
        "asset_classes": ["equity"],
        "timeframe": "1d",
        "backtest_start": "2020-01-01",
        "backtest_end": "2024-12-31",
        "starting_capital": 0.0,
        "max_leverage": 1.0,
        "transaction_cost_bps": 5.0,
        "slippage_bps": 2.0,
        "objective": "sharpe",
        "preferred_strategy_families": ["factor", "mean_reversion", "momentum"],
    },
    "quantconnect": {
        "competition": "quantconnect",
        "round_name": "Round 1",
        "asset_classes": ["equity"],
        "timeframe": "1d",
        "backtest_start": "2018-01-01",
        "backtest_end": "2023-12-31",
        "starting_capital": 100000.0,
        "max_leverage": 1.0,
        "transaction_cost_bps": 5.0,
        "slippage_bps": 2.0,
        "objective": "sharpe",
        "preferred_strategy_families": ["momentum", "mean_reversion", "trend_following"],
    },
}


def _render(tpl: str, **vars: str) -> str:
    out = tpl
    for k, v in vars.items():
        out = out.replace("{{" + k + "}}", v)
    return out


def _extract_json(text: str) -> dict:
    m = _JSON_RE.search(text)
    if not m:
        raise ValueError(f"No JSON found in context builder output: {text[:300]}")
    return json.loads(m.group(0))


def build_context(
    user_prompt: str,
    template_name: str | None = None,
) -> tuple[str, RoundContext | TradingContext]:
    """Parse `user_prompt` into (mode, context).

    Returns:
        mode: "algo" | "manual"
        context: RoundContext (algo) or TradingContext (manual)
    """
    s = load_settings()
    tpl_txt = (PROMPTS_DIR / "context_builder.txt").read_text(encoding="utf-8")

    template_defaults = _TEMPLATE_DEFAULTS.get(template_name or "", {})
    prompt = _render(
        tpl_txt,
        user_prompt=user_prompt,
        template_json=json.dumps(template_defaults, indent=2) if template_defaults else "{}",
    )

    log_id = prompt_logger.log_call(
        "context_builder.txt",
        context={"user_prompt": user_prompt[:200], "template": template_name},
        input_obj={"template_name": template_name},
    )

    try:
        raw_text = llm_client.complete(model=s.synth_model, prompt=prompt, max_tokens=1500)
        data = _extract_json(raw_text)
    except Exception as e:
        prompt_logger.finalize(log_id, "failure", notes=str(e))
        raise

    mode = data.get("mode", "algo")
    ctx_raw = data.get("context", {})

    # Coerce LLM typos: singular → plural field names
    if "asset_class" in ctx_raw and "asset_classes" not in ctx_raw:
        val = ctx_raw.pop("asset_class")
        ctx_raw["asset_classes"] = [val] if isinstance(val, str) else val
    if "symbol" in ctx_raw and "symbols" not in ctx_raw:
        val = ctx_raw.pop("symbol")
        ctx_raw["symbols"] = [val] if isinstance(val, str) else val

    # Fill in template defaults for any missing fields
    for k, v in template_defaults.items():
        ctx_raw.setdefault(k, v)

    try:
        if mode == "manual":
            ctx: RoundContext | TradingContext = TradingContext.model_validate(ctx_raw)
        else:
            ctx = RoundContext.model_validate(ctx_raw)
    except Exception as e:
        prompt_logger.finalize(log_id, "failure", notes=f"Schema validation: {e}")
        raise ValueError(f"Context builder produced invalid context: {e}\nRaw: {ctx_raw}") from e

    prompt_logger.finalize(log_id, "success", metric=1.0)
    return mode, ctx
