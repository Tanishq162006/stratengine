# StratEngine

StratEngine is a quant strategy research pipeline that combines a curated knowledge base with Claude LLM power to generate competition-ready trading algorithms from a single natural-language prompt.

You describe what you want in plain English — "Round 1: PEPPER_ROOT market making, OSMIUM Bollinger mean-reversion" — and the system outputs working Python `.py` files ready to submit.

It was built specifically for **IMC Prosperity 4** but the engine is competition-agnostic. Any competition can be added as a plugin.

---

## What it does

```
Your prompt (plain English)
    → context_builder     parse into structured round context
    → retriever           pull relevant strategy cards from knowledge base
    → synthesizer         propose 5 candidate strategy designs
    → critic              score and filter each design
    → coder               write competition-ready Python for each accepted design
    → evaluator           backtest + robustness check (if price data provided)
    → memory/candidates/  ready-to-submit .py files
```

Every LLM call is injected with **59k chars of expert quant context**: Avellaneda-Stoikov market making, Kalman/EMA fair value estimation, order book reading, pattern detection, Kelly sizing, end-of-round inventory management, and more — all hand-crafted for IMC Prosperity 4.

---

## Requirements

- Python 3.11+
- [Claude Code CLI](https://claude.ai/code) installed and logged in (`claude login`)
- No Anthropic API key needed — uses your claude.ai subscription

---

## Setup

```bash
# 1. Clone the repo
git clone https://github.com/Tanishq162006/stratengine.git
cd stratengine

# 2. Install dependencies (globally recommended)
pip install -r requirements.txt

# 3. Log into Claude Code (one-time)
claude login

# 4. Bootstrap the knowledge base (crawl + extract + index)
python run.py bootstrap
```

The bootstrap step fetches ~100 articles from QuantStart, arXiv, Quantpedia, and other quant sources, extracts them into Strategy Cards, and indexes them into SQLite + ChromaDB. This takes about 10–15 minutes and requires internet access.

---

## Usage

### Zero-touch: prompt to algorithm

```bash
python run.py play \
  --prompt "Round 1: INTARIAN_PEPPER_ROOT stable value market making, ASH_COATED_OSMIUM Bollinger mean-reversion" \
  --template imc_prosperity
```

Output: `memory/candidates/<timestamp>_cand_00.py` through `_cand_04.py`

The critic scores each candidate. Files marked `accept` in the run log are the best picks. Use them directly as your IMC Prosperity trader submission.

### With backtesting

```bash
# Download price data first
python run.py fetch-prices SPY,QQQ,TLT

# Then play — will automatically evaluate each candidate
python run.py play \
  --prompt "momentum + mean reversion on SPY" \
  --template quantconnect \
  --data data/prices/SPY.csv
```

### Check the knowledge base

```bash
python run.py dashboard
```

### Step-by-step pipeline (advanced)

```bash
python run.py crawl        # fetch raw HTML from seed URLs
python run.py clean        # extract readable text
python run.py extract      # convert articles → Strategy Cards via Claude
python run.py index        # index cards into SQLite + ChromaDB
python run.py dedup        # merge near-duplicate cards
```

---

## IMC Prosperity 4 — Quick Start

Round 1 products: `INTARIAN_PEPPER_ROOT` (stable value, limit 80), `ASH_COATED_OSMIUM` (patterned, limit 80)

```bash
python run.py play \
  --prompt "Round 1: INTARIAN_PEPPER_ROOT stable value market making with inventory skew, ASH_COATED_OSMIUM Bollinger z-score mean reversion with regime detection, maximize PnL" \
  --template imc_prosperity
```

The system knows:
- Prosperity 4 product names, position limits, traderData 50k limit
- Round 2 `bid()` MAF mechanics and Invest&Expand math
- Avellaneda-Stoikov reservation price and optimal spread formulas
- How to detect trending vs mean-reverting regimes
- End-of-round inventory unwind urgency
- Micro-price, order imbalance, informed flow detection

---

## Project structure

```
stratengine/
├── run.py                   # CLI entry point (all commands)
├── knowledge/
│   ├── imc_prosperity/      # Expert knowledge injected into every IMC LLM call
│   │   ├── avellaneda_stoikov.md
│   │   ├── fair_value_estimation.md
│   │   ├── multi_product_strategy.md
│   │   ├── order_book_reading.md
│   │   ├── pattern_detection.md
│   │   ├── round2_mechanics.md
│   │   ├── state_and_sizing.md
│   │   └── timing_and_urgency.md
│   └── shared/              # General quant knowledge for all competitions
│       ├── alpha_research.md
│       ├── execution_and_risk.md
│       ├── kelly_and_sizing.md
│       └── market_microstructure.md
├── competitions/
│   └── imc_prosperity/      # IMC plugin (simulator + plugin interface)
│       ├── plugin.py
│       └── simulator.py
├── schema/                  # Pydantic v2 models
├── prompts/                 # All LLM prompt templates (.txt)
├── templates/               # Competition config (products, rules, dates)
├── sources/seeds.json       # Seed URLs for the crawler
├── data/                    # raw/, clean/, cards/ — auto-generated
└── memory/                  # Round results, candidates, postmortems
```

---

## Adding a new competition

1. Create `competitions/<name>/plugin.py` implementing the `CompetitionPlugin` protocol
2. Create `templates/<name>.json` with products, limits, and prompt instructions
3. Create `knowledge/<name>/` with expert `.md` files for that competition
4. Run `python run.py play --template <name> --prompt "..."`

---

## Commands reference

| Command | What it does |
|---|---|
| `bootstrap` | Full first-run setup: crawl + clean + extract + index + fetch prices |
| `play` | Zero-touch: natural-language prompt → algorithm files |
| `crawl` | Fetch raw HTML from all seed URLs |
| `clean` | Extract readable text from raw HTML |
| `extract` | Convert cleaned articles into Strategy Cards via Claude |
| `index` | Index Strategy Cards into SQLite + ChromaDB |
| `dedup` | Merge near-duplicate strategy cards |
| `dashboard` | Full system status: card counts, source quality, prompt performance |
| `fetch-prices` | Download free daily OHLCV from Stooq |
| `clusters` | Print strategy cluster landscape |
| `source-report` | Per-source quality scores |
| `prompt-report` | Per-prompt template success rates |

---

## Tech stack

| Component | Library |
|---|---|
| LLM calls | Claude Code CLI (claude.ai subscription) |
| Vector search | ChromaDB |
| Metadata store | SQLite |
| Backtesting | Backtrader |
| Data models | Pydantic v2 |
| CLI | Typer + Rich |
| Web crawling | httpx + trafilatura |

---

## License

Private. Not for redistribution.
