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
from decision_scorer import ScorerWeights, score_playbook
from evaluator import evaluate, rank
from generator import generate
from manual_critic import attach_critiques, critique_playbooks, filter_by_verdict
from playbook_generator import generate_playbooks
from retriever import retrieve
from schema import RoundContext, TradingContext
import dedup as dedup_mod
import source_quality as sq_mod

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


def _render_playbook_markdown(pb: dict, score: dict, critique: dict | None) -> str:
    lines: list[str] = []
    lines.append(f"## {pb.get('name', 'Unnamed playbook')}")
    if pb.get("thesis"):
        lines.append(f"\n**Thesis:** {pb['thesis']}\n")
    lines.append(f"**Composite score:** {score['composite']:.3f}")
    lines.append(
        f"(clarity {score['signal_clarity']:.2f} · risk {score['risk_completeness']:.2f} · "
        f"load {score['cognitive_load']:.2f} · regime {score['regime_specificity']:.2f} · "
        f"history {score['historical_scenarios']:.2f})\n"
    )

    def _bullets(items):
        if isinstance(items, dict):
            chunks: list[str] = []
            for k, v in items.items():
                chunks.append(f"- **{k}:**")
                if isinstance(v, list):
                    chunks.extend(f"  - {x}" for x in v)
                else:
                    chunks.append(f"  - {v}")
            return "\n".join(chunks)
        if isinstance(items, list):
            return "\n".join(f"- {x}" for x in items)
        return f"- {items}"

    lines.append("### Entry checklist")
    lines.append(_bullets(pb.get("entry_checklist", [])))
    lines.append("\n### Exit checklist")
    lines.append(_bullets(pb.get("exit_checklist", [])))
    lines.append("\n### Sizing framework")
    lines.append(_bullets(pb.get("sizing_framework", {})))
    lines.append("\n### Regime detection")
    lines.append(_bullets(pb.get("regime_detection", {})))
    lines.append("\n### Risk protocol")
    lines.append(_bullets(pb.get("risk_protocol", {})))

    if critique and critique.get("issues"):
        lines.append("\n### Critic review")
        lines.append(f"- verdict: **{critique.get('verdict', 'accept')}**")
        for issue in critique["issues"]:
            lines.append(
                f"- [{issue.get('severity', '?')}] {issue.get('category', '?')}: "
                f"{issue.get('explanation', '')}"
            )
    if pb.get("source_card_ids"):
        lines.append("\n### Source cards")
        lines.append(", ".join(pb["source_card_ids"]))
    return "\n".join(lines)


@app.command()
def round(
    context: Path = typer.Option(..., help="Path to RoundContext or TradingContext JSON."),
    mode: str = typer.Option("algo", help="'algo' or 'manual'."),
    top_k: int = 10,
    data: Optional[Path] = typer.Option(
        None, help="Price CSV for algo-mode backtests."
    ),
    prices_dir: Optional[Path] = typer.Option(
        None, help="Dir of per-symbol OHLC CSVs for manual-mode scenario scoring."
    ),
    skip_scenarios: bool = typer.Option(
        False, help="Skip historical scenario scoring (manual mode)."
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
                    "candidates": [{"candidate": c["candidate"]} for c in result["candidates"]],
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

        table = Table(title="Algo candidates")
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
        gen = generate_playbooks(tctx, cards)
        playbooks = gen["playbooks"]
        if not playbooks:
            raise typer.BadParameter("Generator produced no valid playbooks.")

        reviews = critique_playbooks(tctx, playbooks).get("reviews", [])
        with_critique = attach_critiques(playbooks, reviews)
        kept = filter_by_verdict(with_critique, drop_rejected=True)

        scored: list[dict] = []
        for pb in kept:
            ps = score_playbook(
                pb,
                data_dir=prices_dir or Path("data/prices"),
                skip_scenarios=skip_scenarios,
            )
            scored.append({"playbook": pb, "score": asdict(ps)})
        scored.sort(key=lambda x: x["score"]["composite"], reverse=True)

        # JSON
        (ROUNDS_DIR / f"{round_id}_playbook.json").write_text(
            json.dumps(
                {
                    "round_id": round_id,
                    "trading_context": raw,
                    "retrieved_card_ids": [c.card_id for c in cards],
                    "playbooks": scored,
                    "warnings": gen.get("warnings", []),
                },
                indent=2,
            )
        )

        # Markdown
        md_lines = [f"# Manual Playbooks — round {round_id}", ""]
        md_lines.append(f"Retrieved {len(cards)} cards. Ranked {len(scored)} playbooks.\n")
        for item in scored:
            md_lines.append(
                _render_playbook_markdown(
                    item["playbook"], item["score"], item["playbook"].get("_critique")
                )
            )
            md_lines.append("\n---\n")
        (CANDIDATES_DIR / f"{round_id}_playbooks.md").write_text("\n".join(md_lines))

        table = Table(title="Manual playbooks")
        table.add_column("Rank")
        table.add_column("Name")
        table.add_column("Composite")
        table.add_column("Verdict")
        for i, item in enumerate(scored):
            table.add_row(
                str(i + 1),
                item["playbook"].get("name", "?"),
                f"{item['score']['composite']:.3f}",
                (item["playbook"].get("_critique") or {}).get("verdict", "accept"),
            )
        console.print(table)

    else:
        raise typer.BadParameter("mode must be 'algo' or 'manual'")


@app.command()
def dedup(threshold: float = 0.92) -> None:
    """Merge near-duplicate strategy cards."""
    report = dedup_mod.merge_duplicates(threshold=threshold)
    console.print(
        f"groups examined: {report.groups_examined}  merges: {report.merges}  "
        f"removed: {len(report.removed_card_ids)}"
    )


@app.command()
def clusters() -> None:
    """Print strategy cluster landscape."""
    groups = dedup_mod.clusters()
    if not groups:
        console.print("[yellow]No cards indexed yet.[/]")
        return
    table = Table(title="Strategy clusters")
    for col in ("Family", "Asset", "Timeframe", "Count", "Representative"):
        table.add_column(col)
    for g in groups:
        fam, asset, tf = g.key
        table.add_row(fam, asset, tf, str(len(g.card_ids)), g.representative_id)
    console.print(table)


@app.command("source-report")
def source_report() -> None:
    """Print per-source quality scores."""
    rows = sq_mod.all_scores()
    if not rows:
        console.print("[yellow]No sources tracked yet.[/]")
        return
    rows.sort(key=lambda r: r.composite, reverse=True)
    table = Table(title="Source quality")
    for col in ("Source", "Composite", "Extract", "Quality", "Survival", "Clarity", "Samples"):
        table.add_column(col)
    for r in rows:
        samples = f"ext={r.n_extraction} cards={r.n_cards} bt={r.n_backtests} pb={r.n_playbooks}"
        table.add_row(
            r.source_name,
            f"{r.composite:.3f}",
            f"{r.extraction_success_rate:.2f}",
            f"{r.card_quality_score:.2f}",
            f"{r.backtest_survival_rate:.2f}",
            f"{r.playbook_clarity_score:.2f}",
            samples,
        )
    console.print(table)


@app.command("retrieve-cmd")
def retrieve_cmd(
    context: Path = typer.Argument(..., help="Round or Trading context JSON."),
    mode: str = "algo",
    top_k: int = 10,
) -> None:
    """Debug: show retrieved cards for a context."""
    raw = json.loads(context.read_text())
    ctx = (
        RoundContext.model_validate(raw) if mode == "algo" else TradingContext.model_validate(raw)
    )
    cards = retrieve(ctx, top_k=top_k)
    for c in cards:
        console.print(
            f"[cyan]{c.card_id}[/] {c.title} — {c.strategy_family.value}/{c.timeframe.value}"
        )


if __name__ == "__main__":
    app()
