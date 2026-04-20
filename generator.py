"""LLM agent layer. Synthesizer / Critic / Coder for algo mode."""
from __future__ import annotations

import json
import re
from pathlib import Path

from anthropic import Anthropic
from rich.console import Console

from config import PROMPTS_DIR, load_settings
from schema import RoundContext, StrategyCard
import prompt_logger

console = Console()

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _load(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def _render(tpl: str, **vars: str) -> str:
    out = tpl
    for k, v in vars.items():
        out = out.replace("{{" + k + "}}", v)
    return out


def _client() -> Anthropic:
    s = load_settings()
    if not s.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set.")
    return Anthropic(api_key=s.anthropic_api_key)


def _extract_json(text: str) -> dict:
    m = _JSON_RE.search(text)
    if not m:
        raise ValueError("No JSON in model output.")
    return json.loads(m.group(0))


def _call(model: str, prompt: str, max_tokens: int = 4096) -> str:
    client = _client()
    resp = client.messages.create(
        model=model, max_tokens=max_tokens, messages=[{"role": "user", "content": prompt}]
    )
    return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")


def synthesize(round_ctx: RoundContext, cards: list[StrategyCard]) -> dict:
    s = load_settings()
    tpl = _load("synthesize.txt")
    prompt = _render(
        tpl,
        round_context_json=round_ctx.model_dump_json(indent=2),
        cards_json=json.dumps([json.loads(c.model_dump_json()) for c in cards], indent=2),
    )
    log_id = prompt_logger.log_call(
        "synthesize.txt",
        context=round_ctx.model_dump(mode="json"),
        input_obj={"n_cards": len(cards)},
    )
    try:
        text = _call(s.synth_model, prompt)
        data = _extract_json(text)
    except Exception as e:
        prompt_logger.finalize(log_id, "failure", notes=str(e))
        raise
    prompt_logger.finalize(log_id, "success", metric=float(len(data.get("candidates", []))))
    return data


def critique(round_ctx: RoundContext, candidates: list[dict]) -> dict:
    s = load_settings()
    tpl = _load("critic.txt")
    prompt = _render(
        tpl,
        round_context_json=round_ctx.model_dump_json(indent=2),
        candidates_json=json.dumps(candidates, indent=2),
    )
    log_id = prompt_logger.log_call(
        "critic.txt",
        context=round_ctx.model_dump(mode="json"),
        input_obj={"n_candidates": len(candidates)},
    )
    try:
        text = _call(s.critic_model, prompt)
        data = _extract_json(text)
    except Exception as e:
        prompt_logger.finalize(log_id, "failure", notes=str(e))
        raise
    prompt_logger.finalize(log_id, "success", metric=float(len(data.get("reviews", []))))
    return data


def code_for(round_ctx: RoundContext, candidate: dict) -> str:
    s = load_settings()
    tpl = _load("code.txt")
    prompt = _render(
        tpl,
        round_context_json=round_ctx.model_dump_json(indent=2),
        candidate_json=json.dumps(candidate, indent=2),
    )
    log_id = prompt_logger.log_call(
        "code.txt",
        context=round_ctx.model_dump(mode="json"),
        input_obj={"candidate": candidate.get("name")},
    )
    try:
        text = _call(s.coder_model, prompt, max_tokens=6000)
    except Exception as e:
        prompt_logger.finalize(log_id, "failure", notes=str(e))
        raise
    code = re.sub(r"^```(?:python)?\s*\n|\n```\s*$", "", text.strip(), flags=re.MULTILINE)
    prompt_logger.finalize(
        log_id, "success", metric=float(len(code)), output_id=candidate.get("name")
    )
    return code


def generate(round_ctx: RoundContext, cards: list[StrategyCard]) -> dict:
    """End-to-end: synthesize → critique → code accepted candidates."""
    synth = synthesize(round_ctx, cards)
    candidates = synth.get("candidates", [])
    reviews = critique(round_ctx, candidates).get("reviews", [])
    review_by_name = {r.get("name"): r for r in reviews}

    accepted: list[dict] = []
    for cand in candidates:
        rev = review_by_name.get(cand.get("name"), {"verdict": "accept"})
        if rev.get("verdict") == "reject":
            console.log(f"[red]reject[/] {cand.get('name')}")
            continue
        console.log(f"[green]{rev.get('verdict', 'accept')}[/] {cand.get('name')}")
        accepted.append({**cand, "_review": rev})

    generated: list[dict] = []
    for cand in accepted:
        try:
            code = code_for(round_ctx, cand)
        except Exception as e:
            console.log(f"[red]code error[/] {cand.get('name')}: {e}")
            continue
        generated.append({"candidate": cand, "code": code})

    return {
        "synthesis": synth,
        "reviews": reviews,
        "candidates": generated,
    }
