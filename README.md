# StratEngine

Competition-focused quant strategy research engine for turning market ideas into structured research, candidate strategies, and submission-ready artifacts.

StratEngine is built for fast strategy iteration under contest constraints. It combines curated domain knowledge, retrieval, LLM-assisted synthesis, validation, and lightweight evaluation tooling behind one CLI.

## Supported Competitions

| Competition | Output | Local support |
|---|---:|---|
| IMC Prosperity | Python `Trader` submissions | Plugin simulator and submission scaffolding |
| WorldQuant IQC / BRAIN | BRAIN DSL alpha expressions | Expression validation and refinement loop |
| QuantConnect | LEAN-style strategy scaffolds | Template and knowledge pack |

The repository intentionally does not include private competition datasets, copied winner submissions, generated candidates, prompt logs, local databases, or backtest dumps. See [docs/DATA_POLICY.md](docs/DATA_POLICY.md).

## Why This Exists

StratEngine is designed for competition work where speed is useful only if the process is disciplined:

- Convert a plain-English round brief into a typed strategy context.
- Retrieve relevant strategy cards from reusable quant knowledge.
- Generate and critique multiple candidate strategies.
- Save artifacts in a predictable format for review or submission.
- Track prompt performance, source quality, and retrieval behavior over time.
- Keep competition data and generated submissions outside the repo.

## Quick Start

```bash
git clone https://github.com/Tanishq162006/stratengine.git
cd stratengine

python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

# Either set an Anthropic API key or use Claude Code CLI.
cp .env.example .env
pytest -q
python run.py --help
```

LLM calls use `ANTHROPIC_API_KEY` when present. If no API key is configured, StratEngine can fall back to the local Claude Code CLI when `claude` is installed and authenticated.

## CLI Examples

Generate IMC Prosperity candidates:

```bash
python run.py play \
  --template imc_prosperity \
  --prompt "Round 1 market making with inventory skew and volatility-aware fair value"
```

Generate WorldQuant BRAIN alpha expressions:

```bash
python run.py play \
  --template worldquant_iqc \
  --prompt "short-horizon reversal amplified by volume and neutralized by subindustry"
```

Refine a tested BRAIN expression:

```bash
python run.py refine \
  --expression "scale(group_neutralize(rank(ts_delta(close, 5)), subindustry))" \
  --sharpe 1.04 \
  --fitness 0.50 \
  --sub-sharpe 0.35 \
  --turnover 33.72
```

Inspect system health:

```bash
python run.py dashboard
python run.py source-report
python run.py prompt-report
```

Generated candidates and run outputs are written under `memory/` and are ignored by git.

## Architecture

```text
prompt / round brief
  -> context_builder      structured competition context
  -> retriever            relevant strategy cards and knowledge
  -> generator            candidate strategy designs and code
  -> critic / scorer      review, rank, and filter
  -> competition plugin   output validation or backtest adapter
  -> memory/              local generated artifacts
```

Key directories:

```text
competitions/             Competition plugin registry and built-in plugins
knowledge/                Curated strategy and competition knowledge packs
prompts/                  Prompt templates for extraction, synthesis, code, review
schema/                   Pydantic models for contexts and strategy cards
templates/                Competition defaults and output conventions
tests/                    Unit tests and CLI smoke coverage
data/                     Local generated crawl/card data; git-ignored except .gitkeep
memory/                   Local candidates, results, postmortems; git-ignored except .gitkeep
```

## Commands

| Command | Purpose |
|---|---|
| `setup` | Interactive first-run setup |
| `bootstrap` | Crawl, clean, extract, index, and optionally fetch prices |
| `play` | Generate competition-ready candidates from a prompt |
| `refine` | Improve a WorldQuant BRAIN expression from test metrics |
| `round` | Run a full context-driven research round |
| `report` | Produce a markdown strategy report |
| `dashboard` | Show card counts, source quality, and prompt status |
| `source-report` | Rank research sources by quality |
| `prompt-report` | Summarize prompt template success rates |
| `clusters` | Inspect strategy-card clusters |

## Development

```bash
python -m pip install -e ".[dev]"
pytest -q
ruff check .
```

Before committing, verify that `git status --short` does not show raw CSV data, generated candidates, copied submissions, local databases, cache folders, or private analysis notes.

## Repository Hygiene

This repo should contain reusable engine code, prompts, schemas, tests, templates, and curated non-private knowledge. It should not contain:

- IMC or other contest CSV datasets.
- Round-specific trade logs or local backtest data.
- Generated `best_v*.py` submissions.
- Copied winner scripts or third-party private code.
- SQLite/Chroma databases, prompt logs, caches, or `.DS_Store` files.
- Private postmortems, feedback notes, or manual strategy dumps.

The `.gitignore` is set up to block these by default.

## License

Proprietary. Not for redistribution.
