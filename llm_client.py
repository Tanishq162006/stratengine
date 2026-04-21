"""Unified Claude client.

Prefers the Anthropic SDK (when `ANTHROPIC_API_KEY` is set). Falls back to the
local Claude Code CLI, which authenticates via the user's claude.ai session
(`claude login`) — no API key required. Both paths return a single text
completion string.

Why this exists:
- The user has a $100 claude.ai credit but no API-side credit. The CLI path
  lets StratEngine run against Claude without a separate API-side purchase.
- Existing call sites treat the SDK's Messages API as "prompt in, text out",
  so a unified `complete()` is a faithful drop-in.

The CLI path:
- Calls `claude -p <prompt>` with tools disabled + a terse system prompt so
  Claude returns only the requested payload (JSON / code).
- Runs from `/tmp` so it doesn't inherit any project CLAUDE.md or plugin dir.
- Uses a longer timeout than SDK calls since CLI start-up adds a few seconds.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from typing import Literal

from anthropic import Anthropic


# Tools that might otherwise execute on the host machine. Block them so the
# CLI behaves like a pure prompt-in-text-out completion API.
_DISALLOWED_TOOLS = [
    "Read",
    "Write",
    "Edit",
    "Bash",
    "Glob",
    "Grep",
    "Agent",
    "TaskCreate",
    "TaskUpdate",
    "TaskGet",
    "TaskList",
    "TaskStop",
    "TaskOutput",
    "WebFetch",
    "WebSearch",
    "NotebookEdit",
    "MultiEdit",
]

_SYSTEM_PROMPT_SUFFIX = (
    "You are responding to a structured data request from an automated "
    "pipeline. Return ONLY the exact output format the user prompt requests "
    "(JSON object, Python file, etc.), with NO preamble, NO commentary, NO "
    "markdown fences, and NO clarifying questions. Never call tools. Never "
    "refuse unless the request is unsafe."
)


def using_cli() -> bool:
    """True when we would go through the Claude Code CLI (no API key set)."""
    return not os.environ.get("ANTHROPIC_API_KEY") and shutil.which("claude") is not None


def _sdk_complete(model: str, prompt: str, max_tokens: int) -> str:
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")


def _cli_complete(model: str, prompt: str, timeout: int) -> str:
    if not shutil.which("claude"):
        raise RuntimeError(
            "Neither ANTHROPIC_API_KEY nor the 'claude' CLI is available. "
            "Either export ANTHROPIC_API_KEY or install Claude Code and run `claude login`."
        )
    args = [
        "claude",
        "-p",
        "--model",
        model,
        "--disable-slash-commands",
        "--disallowedTools",
        " ".join(_DISALLOWED_TOOLS),
        "--append-system-prompt",
        _SYSTEM_PROMPT_SUFFIX,
        "--exclude-dynamic-system-prompt-sections",
        prompt,
    ]
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd="/tmp",
            env={**__import__("os").environ, "TOKENIZERS_PARALLELISM": "false"},
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"claude CLI timed out after {timeout}s") from e
    if proc.returncode != 0:
        raise RuntimeError(
            f"claude CLI exited {proc.returncode}: {proc.stderr.strip()[:500]}"
        )
    return proc.stdout


def complete(
    *,
    model: str,
    prompt: str,
    max_tokens: int = 4096,
    timeout: int = 300,
    force: Literal["sdk", "cli"] | None = None,
) -> str:
    """Single entry point. Returns assistant text for the given prompt."""
    if force == "sdk" or (force is None and os.environ.get("ANTHROPIC_API_KEY")):
        return _sdk_complete(model, prompt, max_tokens)
    return _cli_complete(model, prompt, timeout)
