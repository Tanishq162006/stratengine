"""Cleaning layer. Extracts readable text from raw HTML using trafilatura."""
from __future__ import annotations

import json
from pathlib import Path

import trafilatura
from rich.console import Console

from config import CLEAN_DIR, RAW_DIR, ensure_dirs

console = Console()


def clean_html(html: str, url: str | None = None) -> str | None:
    """Return extracted main text, or None if extraction failed / text too short."""
    text = trafilatura.extract(
        html,
        url=url,
        favor_recall=True,
        include_comments=False,
        include_tables=True,
        with_metadata=False,
    )
    if not text:
        return None
    cleaned = text.strip()
    if len(cleaned) < 200:
        return None
    return cleaned


def clean_all() -> list[dict]:
    ensure_dirs()
    results: list[dict] = []
    for meta_path in sorted(RAW_DIR.glob("*.json")):
        if meta_path.name.startswith("_"):
            continue
        meta = json.loads(meta_path.read_text())
        html_path = RAW_DIR / f"{meta['id']}.html"
        if not html_path.exists():
            continue
        html = html_path.read_text(encoding="utf-8")
        text = clean_html(html, url=meta.get("url"))
        if not text:
            console.log(f"[yellow]skip (no text)[/] {meta['url']}")
            results.append({**meta, "clean": False})
            continue
        out_path = CLEAN_DIR / f"{meta['id']}.txt"
        out_path.write_text(text, encoding="utf-8")
        meta_out = CLEAN_DIR / f"{meta['id']}.json"
        meta_out.write_text(
            json.dumps({**meta, "clean_chars": len(text), "clean": True}, indent=2)
        )
        console.log(f"[green]cleaned[/] {meta['url']} ({len(text)} chars)")
        results.append({**meta, "clean": True, "chars": len(text)})

    summary = CLEAN_DIR / "_clean_summary.json"
    summary.write_text(json.dumps(results, indent=2))
    console.print(f"[bold green]Clean complete:[/] {sum(1 for r in results if r.get('clean'))}/{len(results)}")
    return results


if __name__ == "__main__":
    clean_all()
