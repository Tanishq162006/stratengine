"""Unified LLM client supporting Claude (SDK + Code CLI) and OpenAI Codex CLI.

StratEngine treats the LLM as a "prompt-in, text-out" oracle. This module
hides which backend is actually serving the request:

  • Anthropic SDK (claude-sonnet-4-x / claude-opus-4-x) when ANTHROPIC_API_KEY is set
  • Claude Code CLI (`claude -p ...`) when only the user's claude.ai login is available
  • OpenAI Codex CLI (`codex exec ...`) for users on a ChatGPT plan / OpenAI auth
  • Raw OpenAI SDK (gpt-5-codex / gpt-5) when OPENAI_API_KEY is set

Backend selection:

  1. If `force` is passed, that wins.
  2. Else, env var `STRATENGINE_LLM_BACKEND` is honored:
       claude_sdk | claude_cli | codex_cli | openai_sdk | auto
     Default is `auto`.
  3. Auto resolution order:
       ANTHROPIC_API_KEY → claude_sdk
       OPENAI_API_KEY    → openai_sdk
       `claude` on PATH  → claude_cli
       `codex` on PATH   → codex_cli
       error otherwise

The Codex CLI command is parameterized by `STRATENGINE_CODEX_CMD` (a shell
template with `{model}` and `{prompt}` placeholders) so users can adapt to
codex-cli flag changes without touching code. Default:

    codex exec --quiet --model {model} {prompt}

System prompt parity:
- The JSON-only suffix is applied on every backend so callers always get
  bare structured output.
- Optional `system` blocks are sent as cache-eligible system blocks on the
  Anthropic SDK and prepended elsewhere.
"""
from __future__ import annotations

import os
import shutil
import shlex
import subprocess
from typing import Literal

from anthropic import Anthropic


# Tools that might otherwise execute on the host machine. Block them so the
# CLI behaves like a pure prompt-in-text-out completion API.
_DISALLOWED_TOOLS = [
    "Read", "Write", "Edit", "Bash", "Glob", "Grep", "Agent",
    "TaskCreate", "TaskUpdate", "TaskGet", "TaskList", "TaskStop", "TaskOutput",
    "WebFetch", "WebSearch", "NotebookEdit", "MultiEdit",
]

_SYSTEM_PROMPT_SUFFIX = (
    "You are responding to a structured data request from an automated "
    "pipeline. Return ONLY the exact output format the user prompt requests "
    "(JSON object, Python file, etc.), with NO preamble, NO commentary, NO "
    "markdown fences, and NO clarifying questions. Never call tools. Never "
    "refuse unless the request is unsafe."
)

Backend = Literal["claude_sdk", "claude_cli", "codex_cli", "openai_sdk", "auto"]


_LEGACY_FORCE_ALIASES = {"sdk": "claude_sdk", "cli": "claude_cli"}


def _resolve_backend(force) -> str:  # type: ignore[no-untyped-def]
    if force:
        f = _LEGACY_FORCE_ALIASES.get(force, force)
        if f != "auto":
            return f
    env = os.environ.get("STRATENGINE_LLM_BACKEND", "auto").lower()
    if env != "auto":
        return _LEGACY_FORCE_ALIASES.get(env, env)
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "claude_sdk"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai_sdk"
    if shutil.which("claude"):
        return "claude_cli"
    if shutil.which("codex"):
        return "codex_cli"
    raise RuntimeError(
        "No LLM backend available. Set ANTHROPIC_API_KEY or OPENAI_API_KEY, "
        "or install the `claude` or `codex` CLI."
    )


def using_cli() -> bool:
    """True when the resolved backend is one of the local CLIs."""
    try:
        return _resolve_backend(None) in {"claude_cli", "codex_cli"}
    except RuntimeError:
        return False


# ---------- Anthropic ----------

def _claude_sdk_complete(model: str, prompt: str, max_tokens: int, system: str | None) -> str:
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    blocks: list[dict] = []
    if system:
        blocks.append({"type": "text", "text": system, "cache_control": {"type": "ephemeral"}})
    blocks.append({"type": "text", "text": _SYSTEM_PROMPT_SUFFIX})
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=blocks,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")


def _claude_cli_complete(model: str, prompt: str, timeout: int, system: str | None) -> str:
    if not shutil.which("claude"):
        raise RuntimeError("`claude` CLI not on PATH. Install Claude Code and run `claude login`.")
    full_system = _SYSTEM_PROMPT_SUFFIX if not system else f"{system}\n\n{_SYSTEM_PROMPT_SUFFIX}"
    args = [
        "claude", "-p",
        "--model", model,
        "--disable-slash-commands",
        "--disallowedTools", " ".join(_DISALLOWED_TOOLS),
        "--append-system-prompt", full_system,
        "--exclude-dynamic-system-prompt-sections",
        prompt,
    ]
    return _run(args, timeout=timeout, label=f"claude CLI ({model})")


# ---------- OpenAI ----------

def _openai_sdk_complete(model: str, prompt: str, max_tokens: int, system: str | None) -> str:
    try:
        from openai import OpenAI  # local import keeps this module importable without openai installed
    except ImportError as e:
        raise RuntimeError(
            "openai SDK not installed. Run `pip install openai` or set "
            "STRATENGINE_LLM_BACKEND=codex_cli to use the codex CLI instead."
        ) from e
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    full_system = _SYSTEM_PROMPT_SUFFIX if not system else f"{system}\n\n{_SYSTEM_PROMPT_SUFFIX}"
    resp = client.chat.completions.create(
        model=model,
        max_completion_tokens=max_tokens,
        messages=[
            {"role": "system", "content": full_system},
            {"role": "user", "content": prompt},
        ],
    )
    choice = resp.choices[0]
    return (choice.message.content or "").strip()


def _codex_cli_complete(model: str, prompt: str, timeout: int, system: str | None) -> str:
    if not shutil.which("codex"):
        raise RuntimeError("`codex` CLI not on PATH. Install via `npm install -g @openai/codex`.")
    full_system = _SYSTEM_PROMPT_SUFFIX if not system else f"{system}\n\n{_SYSTEM_PROMPT_SUFFIX}"
    full_prompt = f"{full_system}\n\n{prompt}"

    template = os.environ.get(
        "STRATENGINE_CODEX_CMD",
        "codex exec --quiet --model {model} {prompt}",
    )
    if "{prompt}" not in template or "{model}" not in template:
        raise RuntimeError(
            "STRATENGINE_CODEX_CMD must include both {model} and {prompt} placeholders."
        )
    cmd_str = template.replace("{model}", shlex.quote(model)).replace(
        "{prompt}", shlex.quote(full_prompt)
    )
    args = ["bash", "-lc", cmd_str]
    return _run(args, timeout=timeout, label=f"codex CLI ({model})")


# ---------- Shared ----------

def _run(args: list[str], *, timeout: int, label: str) -> str:
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd="/tmp",
            env={**os.environ, "TOKENIZERS_PARALLELISM": "false"},
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"{label} timed out after {timeout}s") from e
    if proc.returncode != 0:
        raise RuntimeError(
            f"{label} exited {proc.returncode}: {proc.stderr.strip()[:500]}"
        )
    return proc.stdout


def complete(
    *,
    model: str,
    prompt: str,
    max_tokens: int = 4096,
    timeout: int = 300,
    system: str | None = None,
    force: Backend | None = None,
) -> str:
    """Single entry point. Returns assistant text for the given prompt.

    `model` is the backend-specific model name (e.g. claude-sonnet-4-6 or
    gpt-5-codex). The caller is expected to set the right model for the
    backend they target.
    """
    backend = _resolve_backend(force)
    # Route through `_sdk_complete` / `_cli_complete` so existing tests that
    # monkeypatch those symbols continue to work.
    if backend == "claude_sdk":
        return _sdk_complete(model, prompt, max_tokens, system=system)
    if backend == "claude_cli":
        return _cli_complete(model, prompt, timeout, system=system)
    if backend == "openai_sdk":
        return _openai_sdk_complete(model, prompt, max_tokens, system)
    if backend == "codex_cli":
        return _codex_cli_complete(model, prompt, timeout, system)
    raise RuntimeError(f"Unknown backend: {backend}")


def _sdk_complete(model: str, prompt: str, max_tokens: int, system: str | None = None) -> str:
    return _claude_sdk_complete(model, prompt, max_tokens, system)


def _cli_complete(model: str, prompt: str, timeout: int, system: str | None = None) -> str:
    return _claude_cli_complete(model, prompt, timeout, system)
