"""Extraction layer. Converts cleaned article text into StrategyCard JSON via
Claude."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from anthropic import Anthropic
from rich.console import Console

from config import CARDS_DIR, CLEAN_DIR, PROMPTS_DIR, ensure_dirs, load_settings
from schema import StrategyCard
import prompt_logger
import source_quality

console = Console()


def _load_prompt() -> str:
    return (PROMPTS_DIR / "extract.txt").read_text(encoding="utf-8")


def _render(template: str, **vars: str) -> str:
    out = template
    for k, v in vars.items():
        out = out.replace("{{" + k + "}}", v)
    return out


def _stable_card_id(url: str, title: str) -> str:
    return hashlib.sha1(f"{url}|{title}".encode("utf-8")).hexdigest()[:16]


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(text: str) -> dict:
    m = _JSON_RE.search(text)
    if not m:
        raise ValueError("No JSON object found in model output.")
    return json.loads(m.group(0))


def extract_card(article_text: str, source_name: str, url: str) -> StrategyCard | None:
    settings = load_settings()
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set.")
    client = Anthropic(api_key=settings.anthropic_api_key)
    prompt = _render(
        _load_prompt(),
        source_name=source_name,
        url=url,
        article_text=article_text[:40_000],
    )
    log_id = prompt_logger.log_call(
        "extract.txt", context={"url": url, "source": source_name}, input_obj={"len": len(article_text)}
    )
    try:
        resp = client.messages.create(
            model=settings.extract_model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
        data = _extract_json(text)
    except Exception as e:
        prompt_logger.finalize(log_id, "failure", notes=str(e))
        raise
    if data.get("skip"):
        console.log(f"[yellow]skip[/] {url}: {data.get('reason')}")
        prompt_logger.finalize(log_id, "failure", notes=f"skip: {data.get('reason')}")
        return None
    data.setdefault("card_id", _stable_card_id(url, data.get("title", "untitled")))
    data.setdefault("url", url)
    data.setdefault("source", source_name)
    card = StrategyCard.model_validate(data)
    prompt_logger.finalize(log_id, "success", metric=card.confidence, output_id=card.card_id)
    return card


def extract_all() -> list[dict]:
    ensure_dirs()
    results: list[dict] = []
    for meta_path in sorted(CLEAN_DIR.glob("*.json")):
        if meta_path.name.startswith("_"):
            continue
        meta = json.loads(meta_path.read_text())
        if not meta.get("clean"):
            continue
        text_path = CLEAN_DIR / f"{meta['id']}.txt"
        if not text_path.exists():
            continue
        out_path = CARDS_DIR / f"{meta['id']}.json"
        if out_path.exists():
            results.append({**meta, "status": "cached"})
            continue
        article_text = text_path.read_text(encoding="utf-8")
        try:
            card = extract_card(article_text, meta.get("source_name", "unknown"), meta["url"])
        except Exception as e:
            console.log(f"[red]extract error[/] {meta['url']}: {e}")
            source_quality.record_extraction(meta.get("source_name", "unknown"), success=False)
            results.append({**meta, "status": "error", "error": str(e)})
            continue
        src = meta.get("source_name", "unknown")
        if card is None:
            source_quality.record_extraction(src, success=False)
            results.append({**meta, "status": "skipped"})
            continue
        out_path.write_text(card.model_dump_json(indent=2))
        source_quality.record_extraction(src, success=True, card_confidence=card.confidence)
        console.log(f"[green]card[/] {meta['url']} -> {out_path.name}")
        results.append({**meta, "status": "ok", "card_id": card.card_id})
    summary = CARDS_DIR / "_extract_summary.json"
    summary.write_text(json.dumps(results, indent=2, default=str))
    return results


if __name__ == "__main__":
    extract_all()
