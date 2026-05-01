"""Code patching loop. When a generated strategy fails evaluation, the patcher
sends the code + error back to the Coder for a targeted fix. Max 3 attempts.
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
from dataclasses import dataclass
from typing import Callable

from rich.console import Console

from config import PROMPTS_DIR, load_settings
from schema import RoundContext
import llm_client
import prompt_logger

console = Console()

MAX_ATTEMPTS = 3

_SCHEMA = """
CREATE TABLE IF NOT EXISTS patch_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_name TEXT,
    attempt INTEGER NOT NULL,
    error_category TEXT,
    error_message TEXT,
    success INTEGER NOT NULL,
    created_at REAL NOT NULL
);
"""


def _conn() -> sqlite3.Connection:
    s = load_settings()
    con = sqlite3.connect(s.db_path)
    con.executescript(_SCHEMA)
    return con


def _render(tpl: str, **vars: str) -> str:
    out = tpl
    for k, v in vars.items():
        out = out.replace("{{" + k + "}}", v)
    return out


def _categorize(err: str) -> str:
    e = err.lower()
    if "syntaxerror" in e:
        return "syntax"
    if "importerror" in e or "modulenotfounderror" in e:
        return "import"
    if "stratengine_stats" in e or "no stats" in e:
        return "missing_stats"
    if "traceback" in e:
        return "runtime"
    if "timeout" in e:
        return "timeout"
    return "other"


def _strip_fences(text: str) -> str:
    return re.sub(r"^```(?:python)?\s*\n|\n```\s*$", "", text.strip(), flags=re.MULTILINE)


@dataclass
class PatchResult:
    code: str
    attempts: int
    error_history: list[str]
    success: bool


def patch(
    code: str,
    error: str,
    candidate: dict,
    round_ctx: RoundContext,
    *,
    max_attempts: int = MAX_ATTEMPTS,
    evaluate_fn: Callable[[str], tuple[bool, str]] | None = None,
) -> PatchResult:
    """Iterate: ask Coder to fix, re-evaluate, repeat up to max_attempts.

    `evaluate_fn(code) -> (ok, new_error)` is injected so the caller controls
    how re-evaluation happens (subprocess, mock, etc).
    """
    s = load_settings()
    tpl = (PROMPTS_DIR / "patch.txt").read_text(encoding="utf-8")

    history: list[str] = [error]
    current_code = code
    last_error = error

    for attempt in range(1, max_attempts + 1):
        category = _categorize(last_error)
        prompt = _render(
            tpl,
            round_context_json=round_ctx.model_dump_json(indent=2),
            candidate_json=json.dumps(candidate, indent=2),
            code=current_code,
            error=last_error,
            attempt=str(attempt),
            max_attempts=str(max_attempts),
        )
        log_id = prompt_logger.log_call(
            "patch.txt",
            context={"candidate": candidate.get("name"), "attempt": attempt},
            input_obj={"category": category, "error_len": len(last_error)},
        )
        try:
            text = llm_client.complete(model=s.coder_model, prompt=prompt, max_tokens=6000)
            current_code = _strip_fences(text)
        except Exception as e:
            prompt_logger.finalize(log_id, "failure", notes=str(e))
            history.append(f"patch LLM error: {e}")
            break

        if evaluate_fn is None:
            prompt_logger.finalize(log_id, "success", metric=float(len(current_code)))
            with _conn() as con:
                con.execute(
                    """INSERT INTO patch_log
                       (candidate_name, attempt, error_category, error_message, success, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (candidate.get("name"), attempt, category, last_error[:2000], 1, time.time()),
                )
            return PatchResult(code=current_code, attempts=attempt, error_history=history, success=True)

        ok, new_err = evaluate_fn(current_code)
        with _conn() as con:
            con.execute(
                """INSERT INTO patch_log
                   (candidate_name, attempt, error_category, error_message, success, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (candidate.get("name"), attempt, category, last_error[:2000], 1 if ok else 0, time.time()),
            )
        prompt_logger.finalize(
            log_id,
            "success" if ok else "failure",
            metric=1.0 if ok else 0.0,
            notes=new_err[:500] if new_err else None,
        )
        if ok:
            return PatchResult(code=current_code, attempts=attempt, error_history=history, success=True)
        history.append(new_err)
        last_error = new_err

    return PatchResult(code=current_code, attempts=max_attempts, error_history=history, success=False)
