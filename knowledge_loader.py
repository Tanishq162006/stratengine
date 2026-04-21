"""Load knowledge-base markdown files for a given template and build the
prefix string injected into every LLM call during that template's round."""
from __future__ import annotations

from pathlib import Path

KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"


def load_knowledge(template_name: str) -> str:
    """Return concatenated markdown from knowledge/<template_name>/*.md.

    Returns empty string if the folder doesn't exist (graceful — no template
    is required to have a knowledge folder).
    """
    folder = KNOWLEDGE_DIR / template_name
    if not folder.is_dir():
        return ""

    parts: list[str] = []
    for md_file in sorted(folder.glob("*.md")):
        header = f"## [{md_file.stem}]"
        parts.append(f"{header}\n\n{md_file.read_text(encoding='utf-8')}")

    return "\n\n---\n\n".join(parts)


def build_prefix(template_name: str, prompt_addendum: str = "") -> str:
    """Combine template prompt_addendum + competition knowledge + shared knowledge.

    Always includes knowledge/shared/ (market microstructure, alpha research etc.)
    so every LLM call has advanced quant context regardless of competition.
    """
    competition_knowledge = load_knowledge(template_name)
    shared_knowledge = load_knowledge("shared")

    sections: list[str] = []

    if prompt_addendum.strip():
        sections.append(f"# Competition Instructions\n\n{prompt_addendum.strip()}")

    if competition_knowledge.strip():
        sections.append(f"# Competition Knowledge Base\n\n{competition_knowledge.strip()}")

    if shared_knowledge.strip():
        sections.append(f"# Advanced Quant Knowledge\n\n{shared_knowledge.strip()}")

    return "\n\n===\n\n".join(sections)
