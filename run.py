"""StratEngine CLI. End-to-end pipeline wiring."""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

import cleaner as cleaner_mod
import crawler as crawler_mod
import extractor as extractor_mod
import indexer as indexer_mod
from config import CANDIDATES_DIR, RESULTS_DIR, ROUNDS_DIR, ensure_dirs
from decision_scorer import score_playbook
from evaluator import evaluate, rank
from generator import generate
from playbook_generator import generate_playbook
from retriever import retrieve
from schema import RoundContext, TradingContext

app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console()


@app.command()
def crawl(seeds: Path = Path("sources/seeds.json")) -> None:
    """Fetch raw HTML for every seed URL."""
    asyncio.run(crawler_mod.crawl(seeds))


@app.command()
def clean() -> None:
    """Extract clean article text from raw HTML."""
    cleaner_mod.clean_all()


@app.command()
def extract() -> None:
    """Convert cleaned articles into Strategy Cards via Claude."""
    extractor_mod.extract_all()


@app.command()
def index() -> None:
    """Index Strategy Cards into SQLite + Chroma."""
    indexer_mod.index_all()


@app.command()
def round(
    context: Path = typer.Option(..., help="Path to RoundContext or TradingContext JSON."),
    mode: str = typer.Option("algo", help="'algo' or 'manual'."),
    top_k: int = 10,
    data: Optional[Path] = typer.Option(
        None, help="Price CSV for algo-mode backtests."
    ),
) -> None:
    """Retrieve + generate + evaluate for a single round."""
    ensure_dirs()
    raw = json.loads(context.read_text())
    round_id = f"{int(time.time())}"

    if mode == "algo":
        ctx = RoundContext.model_validate(raw)
        cards = retrieve(ctx, top_k=top_k)
        console.print(f"[bold]Retrieved {len(cards)} cards[/]")
        result = generate(ctx, cards)

        (CANDIDATES_DIR / f"{round_id}_candidates.json").write_text(
            json.dumps(
                {
                    "round_id": round_id,
                    "round_context": raw,
                    "synthesis": result["synthesis"],
                    "reviews": result["reviews"],
                    "candidates": [
                        {"candidate": c["candidate"]} for c in result["candidates"]
                    ],
                },
                indent=2,
            )
        )
        for i, item in enumerate(result["candidates"]):
            (CANDIDATES_DIR / f"{round_id}_cand_{i:02d}.py").write_text(item["code"])

        if data is None:
            console.print(
                "[yellow]No --data CSV provided; skipping evaluation. "
                "Candidates saved to memory/candidates/.[/]"
            )
            return

        results = []
        for item in result["candidates"]:
            br = evaluate(item["candidate"], item["code"], ctx, data)
            results.append(br)
        ranked = rank(results)

        table = Table(title="Candidate ranking")
        table.add_column("Rank")
        table.add_column("Candidate")
        table.add_column("Score")
        table.add_column("Sharpe")
        table.add_column("MaxDD")
        table.add_column("Violations")
        for i, r in enumerate(ranked):
            table.add_row(
                str(i + 1),
                r.candidate_name,
                f"{r.score:.3f}",
                f"{r.stats.get('sharpe', 0):.3f}" if r.stats else "-",
                f"{r.stats.get('max_drawdown', 0):.3f}" if r.stats else "-",
                ", ".join(r.violations) or "-",
            )
        console.print(table)

        (RESULTS_DIR / f"{round_id}_results.json").write_text(
            json.dumps([asdict(r) for r in ranked], indent=2, default=str)
        )

    elif mode == "manual":
        tctx = TradingContext.model_validate(raw)
        cards = retrieve(tctx, top_k=top_k)
        playbook = generate_playbook(tctx, cards)
        score = score_playbook(playbook)
        out = {
            "round_id": round_id,
            "trading_context": raw,
            "playbook": playbook,
            "score": asdict(score),
            "retrieved_card_ids": [c.card_id for c in cards],
        }
        (ROUNDS_DIR / f"{round_id}_playbook.json").write_text(json.dumps(out, indent=2))
        console.print_json(data=out)
    else:
        raise typer.BadParameter("mode must be 'algo' or 'manual'")


@app.command()
def retrieve_cmd(
    context: Path = typer.Argument(..., help="Round or Trading context JSON."),
    mode: str = "algo",
    top_k: int = 10,
) -> None:
    """Debug: show retrieved cards for a context."""
    raw = json.loads(context.read_text())
    ctx = RoundContext.model_validate(raw) if mode == "algo" else TradingContext.model_validate(raw)
    cards = retrieve(ctx, top_k=top_k)
    for c in cards:
        console.print(f"[cyan]{c.card_id}[/] {c.title} — {c.strategy_family.value}/{c.timeframe.value}")


if __name__ == "__main__":
    app()
