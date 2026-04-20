"""Playbook Generator (manual mode). Produces 3-5 structured discretionary
playbooks from a TradingContext + retrieved StrategyCards."""
from __future__ import annotations

import json
import re

from anthropic import Anthropic
from rich.console import Console

from config import PROMPTS_DIR, load_settings
from schema import StrategyCard, TradingContext

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


def generate_playbooks(ctx: TradingContext, cards: list[StrategyCard]) -> dict:
    """Return {playbooks: [...], warnings: [...]}."""
    s = load_settings()
    if not s.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set.")
    client = Anthropic(api_key=s.anthropic_api_key)
    tpl = (PROMPTS_DIR / "playbook.txt").read_text(encoding="utf-8")
    prompt = _render(
        tpl,
        trading_context_json=ctx.model_dump_json(indent=2),
        cards_json=json.dumps([json.loads(c.model_dump_json()) for c in cards], indent=2),
    )
    resp = client.messages.create(
        model=s.synth_model,
        max_tokens=6000,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    data = _extract_json(text)

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
