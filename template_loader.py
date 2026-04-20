"""Load competition templates and merge their defaults into a RoundContext."""
from __future__ import annotations

import json
from pathlib import Path

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def load_template(name: str) -> dict:
    path = TEMPLATES_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Template {name!r} not found. Available: "
            f"{sorted(p.stem for p in TEMPLATES_DIR.glob('*.json'))}"
        )
    return json.loads(path.read_text())


def merge_defaults(raw_context: dict, template: dict) -> dict:
    """Fill missing keys in raw_context from template['round_context_defaults'].
    Existing user values always win."""
    merged = dict(template.get("round_context_defaults", {}))
    merged.update({k: v for k, v in raw_context.items() if v is not None})
    return merged


def prompt_addendum(template: dict) -> str:
    return template.get("prompt_addendum", "")
