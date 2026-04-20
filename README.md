# StratEngine

A quant strategy research pipeline. Converts public trading articles/docs into a
structured strategy library, then uses LLM agents + automated backtesting to
generate competition-ready and live-trading-ready strategies.

Two output modes:

- **Algo Mode** — Competition + systematic trading. Output is working, backtested code.
- **Manual Mode** — Discretionary trading. Output is structured playbooks, checklists, and signal frameworks.

Both modes share the same knowledge base and retrieval layer. Divergence happens at the output layer.

## Pipeline

```
sources/seeds.json
    → crawler.py         (fetch raw HTML, respect robots.txt)
    → cleaner.py         (trafilatura → readable text)
    → extractor.py       (Claude → StrategyCard JSON)
    → indexer.py         (SQLite metadata + Chroma embeddings)
    → retriever.py       (constraint filter + semantic rank)
    → generator.py       (Synthesizer · Critic · Coder / Playbook)
    → evaluator.py       (Backtrader: Sharpe, drawdown, turnover, robustness)
    → memory/            (rounds, candidates, results, postmortems)
```

## Quickstart

```bash
# Python 3.11+
pip install -r requirements.txt

cp .env.example .env
# Either (a) add an ANTHROPIC_API_KEY, or
# (b) leave it blank and run `claude login` once — StratEngine will route LLM
#     calls through the Claude Code CLI using your claude.ai subscription auth.

# Fetch + clean seed articles
python run.py crawl
python run.py clean

# Extract Strategy Cards
python run.py extract

# Index into SQLite + Chroma
python run.py index

# Run a round (algo mode)
python run.py round --context path/to/round_context.json --mode algo

# Run a manual trading query
python run.py round --context path/to/trading_context.json --mode manual
```

## Project structure

See the `stratengine/` tree. Key points:

- `schema/` — Pydantic v2 models (StrategyCard, RoundContext, TradingContext)
- `prompts/` — All LLM prompts as .txt files, loaded at runtime
- `memory/` — Persistent round state, candidates, backtest results, postmortems
- `data/` — raw HTML, cleaned text, extracted cards

## Non-negotiables

- Evaluation is the most important component. Nothing ships without a backtest + robustness check.
- Never optimize on a single period.
- Never let future information leak into features.
- Never ignore transaction costs.
- LLM output is a hypothesis, not a result — everything flows through evaluation.
- Separate focused agents, not one giant prompt.

## License

Private. Not for redistribution.
