"""Playbook Generator (manual mode). Produces 3-5 structured discretionary
playbooks from a TradingContext + retrieved StrategyCards."""
from __future__ import annotations

import json
import re

from rich.console import Console

from config import PROMPTS_DIR, load_settings
from schema import StrategyCard, TradingContext
import llm_client
import prompt_logger

console = Console()

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)

REQUIRED_PLAYBOOK_FIELDS = (
    "name",
    "entry_checklist",
    "exit_checklist",
    "sizing_framework",
    "regime_detection",
    "risk_protocol",
    "source_card_ids",
)


def _render(tpl: str, **vars: str) -> str:
    out = tpl
    for k, v in vars.items():
        out = out.replace("{{" + k + "}}", v)
    return out


def _extract_json(text: str) -> dict:
    m = _JSON_RE.search(text)
    if not m:
        raise ValueError("No JSON in playbook output.")
    return json.loads(m.group(0))


def _validate_playbook(pb: dict) -> list[str]:
    missing = [f for f in REQUIRED_PLAYBOOK_FIELDS if f not in pb]
    return missing


def generate_playbooks(
    ctx: TradingContext,
    cards: list[StrategyCard],
    *,
    prefix: str | None = None,
) -> dict:
    """Return {playbooks: [...], warnings: [...]}. `prefix` prepends context
    (e.g. trader's firm mandate, asset universe notes) to the LLM call."""
    s = load_settings()
    tpl = (PROMPTS_DIR / "playbook.txt").read_text(encoding="utf-8")
    base_prompt = _render(
        tpl,
        trading_context_json=ctx.model_dump_json(indent=2),
        cards_json=json.dumps([json.loads(c.model_dump_json()) for c in cards], indent=2),
    )
    prompt = (
        f"CONTEXT (read first):\n{prefix.strip()}\n\n---\n\n{base_prompt}"
        if prefix
        else base_prompt
    )
    log_id = prompt_logger.log_call(
        "playbook.txt",
        context=ctx.model_dump(mode="json"),
        input_obj={"n_cards": len(cards)},
    )
    try:
        text = llm_client.complete(model=s.synth_model, prompt=prompt, max_tokens=6000)
        data = _extract_json(text)
    except Exception as e:
        prompt_logger.finalize(log_id, "failure", notes=str(e))
        raise
    prompt_logger.finalize(
        log_id, "success", metric=float(len(data.get("playbooks", [])))
    )

    playbooks = data.get("playbooks", [])
    warnings: list[str] = []
    valid: list[dict] = []
    for i, pb in enumerate(playbooks):
        missing = _validate_playbook(pb)
        if missing:
            warnings.append(f"playbook[{i}] name={pb.get('name')!r} missing {missing}")
            continue
        valid.append(pb)

    if len(valid) < 3:
        warnings.append(f"Only {len(valid)} valid playbooks produced; expected >=3.")

    return {"playbooks": valid, "warnings": warnings, "raw": data}


# Back-compat shim for any caller that imported the old name.
def generate_playbook(ctx: TradingContext, cards: list[StrategyCard]) -> dict:
    return generate_playbooks(ctx, cards)
