"""Manual-mode critic. Attacks discretionary playbooks before a human acts on them."""
from __future__ import annotations

import json
import re

from anthropic import Anthropic
from rich.console import Console

from config import PROMPTS_DIR, load_settings
from schema import TradingContext
import prompt_logger

console = Console()

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _render(tpl: str, **vars: str) -> str:
    out = tpl
    for k, v in vars.items():
        out = out.replace("{{" + k + "}}", v)
    return out


def critique_playbooks(ctx: TradingContext, playbooks: list[dict]) -> dict:
    """Return {'reviews': [{name, issues, verdict, revision_notes}, ...]}."""
    s = load_settings()
    if not s.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set.")
    client = Anthropic(api_key=s.anthropic_api_key)
    tpl = (PROMPTS_DIR / "manual_critic.txt").read_text(encoding="utf-8")
    prompt = _render(
        tpl,
        trading_context_json=ctx.model_dump_json(indent=2),
        playbooks_json=json.dumps(playbooks, indent=2),
    )
    log_id = prompt_logger.log_call(
        "manual_critic.txt",
        context=ctx.model_dump(mode="json"),
        input_obj={"n_playbooks": len(playbooks)},
    )
    try:
        resp = client.messages.create(
            model=s.critic_model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
        m = _JSON_RE.search(text)
        if not m:
            raise ValueError("No JSON in manual_critic output.")
        data = json.loads(m.group(0))
    except Exception as e:
        prompt_logger.finalize(log_id, "failure", notes=str(e))
        raise
    prompt_logger.finalize(
        log_id, "success", metric=float(len(data.get("reviews", [])))
    )
    return data


def attach_critiques(playbooks: list[dict], reviews: list[dict]) -> list[dict]:
    by_name = {r.get("name"): r for r in reviews}
    out: list[dict] = []
    for pb in playbooks:
        rev = by_name.get(pb.get("name"), {"verdict": "accept", "issues": [], "revision_notes": ""})
        out.append({**pb, "_critique": rev})
    return out


def filter_by_verdict(playbooks_with_critique: list[dict], drop_rejected: bool = True) -> list[dict]:
    if not drop_rejected:
        return playbooks_with_critique
    kept: list[dict] = []
    for pb in playbooks_with_critique:
        verdict = (pb.get("_critique") or {}).get("verdict", "accept")
        if verdict == "reject":
            console.log(f"[red]reject[/] playbook: {pb.get('name')}")
            continue
        kept.append(pb)
    return kept
