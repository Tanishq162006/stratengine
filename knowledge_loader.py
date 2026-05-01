"""Load knowledge-base markdown files for a given template and build the
prefix string injected into every LLM call during that template's round."""
from __future__ import annotations

import re
from pathlib import Path

KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"

_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}


def _tokens(text: str) -> set[str]:
    return {
        tok
        for tok in re.findall(r"[a-z0-9_]+", text.lower())
        if len(tok) > 2 and tok not in _STOPWORDS
    }


def _score_doc(path: Path, text: str, query_tokens: set[str]) -> tuple[int, str]:
    stem_tokens = _tokens(path.stem.replace("_", " "))
    body_tokens = _tokens(text)
    score = 3 * len(stem_tokens & query_tokens) + len(body_tokens & query_tokens)
    return score, text


def load_knowledge(
    template_name: str,
    *,
    query_text: str = "",
    max_files: int | None = None,
) -> str:
    """Return concatenated markdown from knowledge/<template_name>/*.md.

    Returns empty string if the folder doesn't exist (graceful — no template
    is required to have a knowledge folder).
    """
    folder = KNOWLEDGE_DIR / template_name
    if not folder.is_dir():
        return ""

    docs: list[tuple[int, str, str]] = []
    query_tokens = _tokens(query_text)
    for md_file in sorted(folder.glob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        score, body = _score_doc(md_file, text, query_tokens)
        docs.append((score, md_file.stem, body))

    if query_tokens and max_files is not None and len(docs) > max_files:
        docs.sort(key=lambda item: (-item[0], item[1]))
        selected = docs[:max_files]
    else:
        selected = docs

    parts: list[str] = []
    for _, stem, body in selected:
        header = f"## [{stem}]"
        parts.append(f"{header}\n\n{body}")

    return "\n\n---\n\n".join(parts)


def build_prefix(
    template_name: str,
    prompt_addendum: str = "",
    *,
    query_text: str = "",
    competition_max_files: int = 4,
    shared_max_files: int = 2,
) -> str:
    """Combine template prompt_addendum + competition knowledge + shared knowledge.

    Always includes knowledge/shared/ (market microstructure, alpha research etc.)
    so every LLM call has advanced quant context regardless of competition.
    """
    competition_knowledge = load_knowledge(
        template_name,
        query_text=query_text,
        max_files=competition_max_files,
    )
    shared_knowledge = load_knowledge(
        "shared",
        query_text=query_text,
        max_files=shared_max_files,
    )

    sections: list[str] = []

    if prompt_addendum.strip():
        sections.append(f"# Competition Instructions\n\n{prompt_addendum.strip()}")

    if competition_knowledge.strip():
        sections.append(f"# Competition Knowledge Base\n\n{competition_knowledge.strip()}")

    if shared_knowledge.strip():
        sections.append(f"# Advanced Quant Knowledge\n\n{shared_knowledge.strip()}")

    return "\n\n===\n\n".join(sections)
