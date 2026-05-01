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
from template_loader import load_template
import llm_client
import prompt_logger

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)

_ASSET_CLASS_ALIASES = {
    "forex": "fx",
}

_TIMEFRAME_ALIASES = {
    "1mo": "1M",
    "1month": "1M",
    "monthly": "1M",
    "daily": "1d",
    "weekly": "1w",
}

_COMPETITION_ALIASES = {
    "worldquant": "worldquant_iqc",
    "worldquant_brain": "worldquant_iqc",
    "brain": "worldquant_iqc",
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


def _template_defaults(template_name: str | None) -> dict:
    if not template_name:
        return {}
    try:
        template = load_template(template_name)
    except FileNotFoundError:
        return {}
    return dict(template.get("round_context_defaults", {}))


def _normalize_list_field(
    value: object,
    aliases: dict[str, str],
) -> list[str] | object:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return value

    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str):
            normalized.append(item)
            continue
        key = item.strip().lower()
        normalized.append(aliases.get(key, item.strip()))
    return normalized


def _normalize_scalar_field(value: object, aliases: dict[str, str]) -> object:
    if not isinstance(value, str):
        return value
    key = value.strip().lower()
    return aliases.get(key, value.strip())


def _normalize_context(ctx_raw: dict) -> dict:
    normalized = dict(ctx_raw)

    if "asset_classes" in normalized:
        normalized["asset_classes"] = _normalize_list_field(
            normalized["asset_classes"],
            _ASSET_CLASS_ALIASES,
        )
    if "timeframe" in normalized:
        normalized["timeframe"] = _normalize_scalar_field(
            normalized["timeframe"],
            _TIMEFRAME_ALIASES,
        )
    if "competition" in normalized:
        normalized["competition"] = _normalize_scalar_field(
            normalized["competition"],
            _COMPETITION_ALIASES,
        )

    if "preferred_strategy_families" in normalized and isinstance(
        normalized["preferred_strategy_families"], str
    ):
        normalized["preferred_strategy_families"] = [
            normalized["preferred_strategy_families"]
        ]
    if "excluded_strategy_families" in normalized and isinstance(
        normalized["excluded_strategy_families"], str
    ):
        normalized["excluded_strategy_families"] = [
            normalized["excluded_strategy_families"]
        ]

    return normalized


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

    template_defaults = _template_defaults(template_name)
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

    ctx_raw = _normalize_context(ctx_raw)

    # Fill in template defaults for any missing fields
    if mode == "algo":
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
