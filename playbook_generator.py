"""Playbook Generator agent (manual mode)."""
from __future__ import annotations

import json
import re

from anthropic import Anthropic
from rich.console import Console

from config import PROMPTS_DIR, load_settings
from schema import StrategyCard, TradingContext

console = Console()

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _render(tpl: str, **vars: str) -> str:
    out = tpl
    for k, v in vars.items():
        out = out.replace("{{" + k + "}}", v)
    return out


def generate_playbook(ctx: TradingContext, cards: list[StrategyCard]) -> dict:
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
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    m = _JSON_RE.search(text)
    if not m:
        raise ValueError("No JSON in playbook output.")
    return json.loads(m.group(0))
