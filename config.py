from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent

DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
CLEAN_DIR = DATA_DIR / "clean"
CARDS_DIR = DATA_DIR / "cards"

MEMORY_DIR = ROOT / "memory"
ROUNDS_DIR = MEMORY_DIR / "rounds"
CANDIDATES_DIR = MEMORY_DIR / "candidates"
RESULTS_DIR = MEMORY_DIR / "results"
POSTMORTEMS_DIR = MEMORY_DIR / "postmortems"

PROMPTS_DIR = ROOT / "prompts"
SOURCES_DIR = ROOT / "sources"


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str
    extract_model: str
    synth_model: str
    critic_model: str
    coder_model: str
    db_path: Path
    chroma_path: Path
    user_agent: str
    rate_limit_per_host: float
    max_concurrency: int


def load_settings() -> Settings:
    return Settings(
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        extract_model=os.environ.get("STRATENGINE_EXTRACT_MODEL", "claude-sonnet-4-6"),
        synth_model=os.environ.get("STRATENGINE_SYNTH_MODEL", "claude-sonnet-4-6"),
        critic_model=os.environ.get("STRATENGINE_CRITIC_MODEL", "claude-sonnet-4-6"),
        coder_model=os.environ.get("STRATENGINE_CODER_MODEL", "claude-sonnet-4-6"),
        db_path=Path(os.environ.get("STRATENGINE_DB_PATH", str(ROOT / "stratengine.db"))),
        chroma_path=Path(os.environ.get("STRATENGINE_CHROMA_PATH", str(ROOT / ".chroma"))),
        user_agent=os.environ.get(
            "STRATENGINE_USER_AGENT",
            "StratEngineBot/0.1 (+https://github.com/Tanishq162006/stratengine)",
        ),
        rate_limit_per_host=float(os.environ.get("STRATENGINE_RATE_LIMIT_PER_HOST", "1.0")),
        max_concurrency=int(os.environ.get("STRATENGINE_MAX_CONCURRENCY", "4")),
    )


def ensure_dirs() -> None:
    for d in (RAW_DIR, CLEAN_DIR, CARDS_DIR, ROUNDS_DIR, CANDIDATES_DIR, RESULTS_DIR, POSTMORTEMS_DIR):
        d.mkdir(parents=True, exist_ok=True)
