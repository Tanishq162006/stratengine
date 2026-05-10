"""StratEngine CLI. End-to-end pipeline wiring."""
from __future__ import annotations

import asyncio
import json
import os
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
from manual_critic import attach_critiques, critique_playbooks, filter_by_verdict
from playbook_generator import generate_playbooks
from retriever import retrieve
from schema import RoundContext, TradingContext
import dashboard as dashboard_mod
import dedup as dedup_mod
import family_analyzer
import prompt_analyzer
import report_generator
import source_discoverer
import source_quality as sq_mod
import competitions
from source_refresher import refresh_all
from template_loader import load_template, merge_defaults, prompt_addendum
from knowledge_loader import build_prefix

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
    template: Optional[str] = typer.Option(
        None, help="Competition template to fill defaults: imc_prosperity | worldquant_iqc | quantconnect."
    ),
) -> None:
    """Retrieve + generate + evaluate for a single round."""
    ensure_dirs()
    raw = json.loads(context.read_text())
    prefix: str | None = None
    if template:
        tpl = load_template(template)
        raw = merge_defaults(raw, tpl)
        addendum = prompt_addendum(tpl)
        console.print(f"[cyan]template {template}:[/] {addendum[:120]}...")
        knowledge_prefix = build_prefix(
            template,
            addendum,
            query_text=json.dumps(raw, indent=2),
        )
        prefix = knowledge_prefix if knowledge_prefix.strip() else None
    round_id = f"{int(time.time())}"

    if mode == "algo":
        ctx = RoundContext.model_validate(raw)
        cards = retrieve(ctx, top_k=top_k)
        console.print(f"[bold]Retrieved {len(cards)} cards[/]")
        result = generate(ctx, cards, prefix=prefix)

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
        output_ext = competitions.output_ext_for(ctx.competition)
        for i, item in enumerate(result["candidates"]):
            (CANDIDATES_DIR / f"{round_id}_cand_{i:02d}{output_ext}").write_text(item["code"])

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
        gen = generate_playbooks(tctx, cards, prefix=prefix)
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


@app.command("refresh")
def refresh_cmd(
    seeds: Path = Path("sources/seeds.json"),
    quiet: bool = typer.Option(False, help="Cron-friendly: suppress interactive output."),
) -> None:
    """Detect new content on known sources and fetch it."""
    summaries = asyncio.run(refresh_all(seeds, quiet=quiet))
    total_new = sum(len(s.new_fetched) for s in summaries)
    total_exist = sum(len(s.skipped_existing) for s in summaries)
    console.print(f"[bold green]Refresh:[/] new={total_new}  existing={total_exist}")


@app.command("report")
def report_cmd(
    context: Path = typer.Option(..., help="Path to RoundContext or TradingContext JSON."),
    mode: str = typer.Option("algo", help="'algo' or 'manual'."),
    top_k: int = 10,
    data: Optional[Path] = None,
    prices_dir: Optional[Path] = None,
    skip_scenarios: bool = False,
) -> None:
    """Zero-touch: context in, markdown report out."""
    out = report_generator.generate_report(
        context, mode=mode, top_k=top_k, data=data, prices_dir=prices_dir, skip_scenarios=skip_scenarios
    )
    console.print(f"[green]Report:[/] {out}")


@app.command("optimize-weights")
def optimize_weights_cmd() -> None:
    """Fit retrieval weights on >=10 rounds of memory."""
    import weight_optimizer

    rows_path = Path("memory/retrieval_features.jsonl")
    if not rows_path.exists():
        console.print(
            "[yellow]No retrieval_features.jsonl found at memory/retrieval_features.jsonl. "
            "Run rounds to populate it.[/]"
        )
        raise typer.Exit(code=1)
    rows = [json.loads(line) for line in rows_path.read_text().splitlines() if line.strip()]
    fitted = weight_optimizer.fit(rows)
    console.print(f"[green]Fitted[/] on {fitted.n_rounds} rounds: {fitted.weights}")


@app.command("discover-sources")
def discover_cmd(min_count: int = 3, max_gaps: int = 10) -> None:
    """Propose new sources to fill coverage gaps."""
    new = source_discoverer.propose(min_count=min_count, max_gaps=max_gaps)
    console.print(f"[green]Proposed[/] {len(new)} gaps -> sources/proposed.json")
    for p in new[:5]:
        console.print(f"  - {p.gap.asset_class}/{p.gap.strategy_family} (count={p.gap.count})")


@app.command("dashboard")
def dashboard_cmd() -> None:
    """Full system status."""
    dashboard_mod.render()


@app.command("prompt-report")
def prompt_report_cmd() -> None:
    """Per-prompt success rates."""
    stats = prompt_analyzer.per_template_stats()
    if not stats:
        console.print("[yellow]No prompt log entries yet.[/]")
        return
    table = Table(title="Prompt performance")
    for col in ("Template", "Version", "n", "Success", "Failure", "Pending", "Mean metric"):
        table.add_column(col)
    for s in stats:
        table.add_row(
            s.template,
            s.version,
            str(s.n_total),
            str(s.n_success),
            str(s.n_failure),
            str(s.n_pending),
            f"{s.mean_metric:.3f}" if s.mean_metric is not None else "-",
        )
    console.print(table)


@app.command("family-report")
def family_report_cmd(round_type: Optional[str] = None) -> None:
    """Per-family win rates."""
    rows = family_analyzer.ranked_win_rates(round_type=round_type)
    if not rows:
        console.print("[yellow]No family performance data yet.[/]")
        return
    table = Table(title=f"Family win rates {'(all)' if not round_type else f'({round_type})'}")
    for col in ("Family", "n", "Wins", "Rate"):
        table.add_column(col)
    for r in rows:
        table.add_row(r.family, str(r.n), str(r.wins), f"{r.rate:.3f}")
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


@app.command("setup")
def setup_cmd() -> None:
    """Interactive first-time setup: choose your competition plugin, then bootstrap."""
    ensure_dirs()
    from template_loader import TEMPLATES_DIR

    available = sorted(p.stem for p in TEMPLATES_DIR.glob("*.json"))
    console.print("\n[bold cyan]StratEngine — First-Time Setup[/]\n")
    console.print("Which competition are you preparing for?\n")
    for i, name in enumerate(available, 1):
        console.print(f"  [{i}] {name}")
    console.print()

    choice = typer.prompt("Enter number or template name", default="imc_prosperity")
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(available):
            template_name = available[idx]
        else:
            console.print("[red]Invalid choice.[/]")
            raise typer.Exit(1)
    elif choice in available:
        template_name = choice
    else:
        console.print(f"[red]Unknown template '{choice}'. Available: {available}[/]")
        raise typer.Exit(1)

    console.print(f"\n[green]Selected:[/] {template_name}\n")
    console.print(
        f"[dim]Tip: use --template {template_name} with every 'play' command.[/]\n"
    )

    if template_name.startswith("worldquant"):
        console.print(
            "[cyan]WorldQuant BRAIN plugin selected.[/] "
            "Output files will be .txt alpha expressions (not .py scripts).\n"
            "Paste them directly into the BRAIN IDE.\n"
        )

    run_bootstrap = typer.confirm("Run bootstrap now (crawl + extract + index)?", default=True)
    if run_bootstrap:
        bootstrap_cmd(seeds=Path("sources/seeds.json"), skip_crawl=False, skip_prices=True, prices="")


@app.command("refine")
def refine_cmd(
    expression: str = typer.Option(..., help="Current BRAIN alpha expression to improve."),
    sharpe: float = typer.Option(..., help="BRAIN IS Sharpe from test results."),
    fitness: float = typer.Option(..., help="BRAIN Fitness score from test results."),
    sub_sharpe: float = typer.Option(..., help="BRAIN Sub-universe Sharpe from test results."),
    turnover: float = typer.Option(..., help="BRAIN Turnover % from test results."),
    ic: float = typer.Option(0.0, help="Information Coefficient if shown by BRAIN."),
    notes: str = typer.Option("", help="Any extra notes or warnings from BRAIN."),
) -> None:
    """Search Enhancement: feed BRAIN results back → get 3 improved alpha mutations.

    Run after each BRAIN test to diagnose failures and generate targeted mutations.

    Example:
        stratengine refine \\
          --expression "scale(group_neutralize(...))" \\
          --sharpe 1.04 --fitness 0.50 --sub-sharpe 0.35 --turnover 33.72
    """
    ensure_dirs()
    from config import PROMPTS_DIR, load_settings
    import llm_client

    s = load_settings()
    tpl = (PROMPTS_DIR / "refine_brain.txt").read_text(encoding="utf-8")

    passed = sum([sharpe >= 1.25, fitness >= 1.0, sub_sharpe >= 0.45, 1 <= turnover <= 70])
    is_sota = sharpe >= 1.25 and fitness >= 1.0 and sub_sharpe >= 0.45
    brain_results = (
        f"Sharpe: {sharpe} ({'PASS' if sharpe >= 1.25 else 'FAIL – below 1.25'})\n"
        f"Fitness: {fitness} ({'PASS' if fitness >= 1.0 else 'FAIL – below 1.0'})\n"
        f"Sub-universe Sharpe: {sub_sharpe} ({'PASS' if sub_sharpe >= 0.45 else 'FAIL – below 0.45'})\n"
        f"Turnover: {turnover}% ({'PASS' if 1 <= turnover <= 70 else 'FAIL'})\n"
        f"IC: {ic if ic else 'not provided'}\n"
        f"Overall: {passed}/4 core metrics passing. {'SOTA CANDIDATE' if is_sota else 'Not yet qualifying.'}\n"
    )
    if notes:
        brain_results += f"Warnings/Notes: {notes}\n"

    # Auto-append to alpha history (RAG#0)
    history_path = Path("knowledge/worldquant_iqc/alpha_history.md")
    if history_path.exists():
        entry = (
            f"\n\n### alpha_{int(time.time())} {'[SOTA]' if is_sota else ''}\n"
            f"**Expression:** `{expression}`\n"
            f"**Results:** Sharpe {sharpe} | Fitness {fitness} | Sub-Sharpe {sub_sharpe} | "
            f"Turnover {turnover}% | IC {ic or 'N/A'}\n"
            f"**Status:** {'ALL PASS' if is_sota else f'{passed}/4 passing'}\n"
        )
        with open(history_path, "a", encoding="utf-8") as f:
            f.write(entry)
        console.print(f"[dim]Logged to alpha_history.md{' [SOTA]' if is_sota else ''}[/]")

    # Load alpha history as examples for RAG#0
    history_path = Path("knowledge/worldquant_iqc/alpha_history.md")
    examples = history_path.read_text(encoding="utf-8") if history_path.exists() else "No history yet."

    prompt = tpl.replace("{{current_expression}}", expression)
    prompt = prompt.replace("{{brain_results}}", brain_results)
    prompt = prompt.replace("{{examples}}", examples[:2000])

    console.rule("[bold cyan]BRAIN Alpha Refinement[/]")
    console.print("[dim]Diagnosing failures and generating 3 mutations...[/]\n")

    text = llm_client.complete(model=s.coder_model, prompt=prompt, max_tokens=3000)

    import re as _re
    m = _re.search(r"\{.*\}", text, _re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(0))
            console.print(f"[bold]Diagnosis:[/] {data.get('diagnosis', '')}\n")
            for i, mut in enumerate(data.get("mutations", []), 1):
                console.rule(f"Mutation {i}: {mut.get('name', '')}")
                console.print(f"[cyan]Change:[/] {mut.get('change', '')}")
                console.print(f"\n[bold green]{mut.get('expression', '')}[/]\n")
            # Save mutations to candidates dir
            round_id = f"{int(time.time())}"
            for i, mut in enumerate(data.get("mutations", []), 0):
                (CANDIDATES_DIR / f"{round_id}_refined_{i:02d}.txt").write_text(
                    mut.get("expression", "")
                )
            console.print(f"[green]Saved to memory/candidates/{round_id}_refined_*.txt[/]")
        except json.JSONDecodeError:
            console.print(text)
    else:
        console.print(text)


@app.command("bootstrap")
def bootstrap_cmd(
    seeds: Path = typer.Option(Path("sources/seeds.json"), help="Seeds file."),
    skip_crawl: bool = typer.Option(False, help="Skip crawl (use existing raw HTML)."),
    skip_prices: bool = typer.Option(False, help="Skip fetching default price data."),
    prices: str = typer.Option(
        "SPY,QQQ,TLT,GLD,IWM",
        help="Comma-separated tickers to pre-fetch for scenario scoring.",
    ),
) -> None:
    """First-run setup: crawl → clean → extract → index + fetch default prices.

    Run this once after cloning the repo to build the strategy card database.
    """
    ensure_dirs()

    if not skip_crawl:
        console.rule("[bold]Step 1/4 — Crawl[/]")
        fetched = asyncio.run(crawler_mod.crawl(seeds))
        console.print(f"  Crawled {len(fetched)} pages")

    console.rule("[bold]Step 2/4 — Clean[/]")
    cleaned = cleaner_mod.clean_all()
    console.print(f"  Cleaned {len(cleaned)} articles")

    console.rule("[bold]Step 3/4 — Extract strategy cards[/]")
    extracted = extractor_mod.extract_all()
    console.print(f"  Extracted {len(extracted)} cards")

    console.rule("[bold]Step 4/4 — Index[/]")
    indexed = indexer_mod.index_all()
    console.print(f"  Indexed {indexed} cards into ChromaDB + SQLite")

    if not skip_prices:
        console.rule("[bold]Bonus — Fetch price data[/]")
        import price_fetcher as pf
        sym_list = [s.strip().upper() for s in prices.split(",") if s.strip()]
        results = pf.fetch_many(sym_list, start="2015-01-01")
        for sym, rows in results.items():
            status = f"{len(rows)} rows" if rows else "[red]FAILED[/]"
            console.print(f"  {sym}: {status}")

    console.print("\n[bold green]Bootstrap complete.[/] Run `stratengine dashboard` to inspect.")


@app.command("fetch-prices")
def fetch_prices_cmd(
    symbols: str = typer.Argument(..., help="Comma-separated tickers, e.g. SPY,QQQ,TLT"),
    start: str = typer.Option("2015-01-01", help="Start date YYYY-MM-DD"),
    end: Optional[str] = typer.Option(None, help="End date YYYY-MM-DD (default: today)"),
) -> None:
    """Download free daily OHLCV from Stooq and save to data/prices/."""
    import price_fetcher

    sym_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    results = price_fetcher.fetch_many(sym_list, start=start, end=end)
    for sym, rows in results.items():
        status = f"{len(rows)} rows" if rows else "[red]FAILED[/]"
        console.print(f"  {sym}: {status}")


@app.command("play")
def play_cmd(
    prompt: str = typer.Option(..., help="Natural-language strategy prompt."),
    template: Optional[str] = typer.Option(
        None, help="Competition template: imc_prosperity | worldquant_iqc | quantconnect."
    ),
    mode: Optional[str] = typer.Option(
        None, help="'algo' or 'manual'. Auto-detected from prompt if omitted."
    ),
    top_k: int = typer.Option(10, help="Cards to retrieve."),
    data: Optional[Path] = typer.Option(None, help="Price CSV for algo-mode backtests."),
    prices_dir: Optional[Path] = typer.Option(None, help="Dir of per-symbol OHLC CSVs."),
    skip_scenarios: bool = typer.Option(False, help="Skip historical scenario scoring."),
) -> None:
    """Zero-touch: natural-language prompt → full round report.

    Example:
        stratengine play --prompt "IMC Round 3, KELP market making, position limit 50" --template imc_prosperity
    """
    ensure_dirs()
    from context_builder import build_context

    console.print("[bold cyan]Building context from prompt...[/]")
    detected_mode, ctx = build_context(prompt, template_name=template)
    resolved_mode = mode or detected_mode
    console.print(f"[cyan]Mode:[/] {resolved_mode}  [cyan]Context:[/] {type(ctx).__name__}")

    # Build prefix from template knowledge (same logic as round_cmd)
    prefix: str | None = None
    if template:
        from template_loader import load_template
        from knowledge_loader import build_prefix
        tpl = load_template(template)
        addendum = prompt_addendum(tpl)
        knowledge_prefix = build_prefix(
            template,
            addendum,
            query_text=f"{prompt}\n\n{ctx.model_dump_json(indent=2)}",
        )
        prefix = knowledge_prefix if knowledge_prefix.strip() else None

    round_id = f"{int(time.time())}"

    if resolved_mode == "algo":
        from schema import RoundContext as RC
        if not isinstance(ctx, RC):
            raise typer.BadParameter("Context parsed as manual but mode is algo.")

        cards = retrieve(ctx, top_k=top_k)
        console.print(f"[bold]Retrieved {len(cards)} cards[/]")
        result = generate(ctx, cards, prefix=prefix)

        (CANDIDATES_DIR / f"{round_id}_candidates.json").write_text(
            json.dumps(
                {
                    "round_id": round_id,
                    "prompt": prompt,
                    "template": template,
                    "round_context": ctx.model_dump(mode="json"),
                    "synthesis": result["synthesis"],
                    "candidates": [{"candidate": c["candidate"]} for c in result["candidates"]],
                },
                indent=2,
            )
        )
        _ext = competitions.output_ext_for(ctx.competition)
        for i, item in enumerate(result["candidates"]):
            (CANDIDATES_DIR / f"{round_id}_cand_{i:02d}{_ext}").write_text(item["code"])

        if data is None:
            _fmt = "BRAIN .txt expression files" if _ext == ".txt" else "Python .py candidates"
            console.print(
                f"[green]Done.[/] {len(result['candidates'])} {_fmt} in memory/candidates/ "
                f"(pass --data CSV to also evaluate)."
            )
            return

        results = []
        for item in result["candidates"]:
            br = evaluate(item["candidate"], item["code"], ctx, data)
            results.append(br)
        ranked_results = rank(results)

        table = Table(title="Algo candidates")
        table.add_column("Rank")
        table.add_column("Candidate")
        table.add_column("Score")
        table.add_column("Sharpe")
        table.add_column("MaxDD")
        for i, r in enumerate(ranked_results):
            table.add_row(
                str(i + 1), r.candidate_name, f"{r.score:.3f}",
                f"{r.stats.get('sharpe', 0):.3f}" if r.stats else "-",
                f"{r.stats.get('max_drawdown', 0):.3f}" if r.stats else "-",
            )
        console.print(table)

        out_path = RESULTS_DIR / f"{round_id}_results.json"
        out_path.write_text(json.dumps([asdict(r) for r in ranked_results], indent=2, default=str))
        console.print(f"[green]Report:[/] {out_path}")

    elif resolved_mode == "manual":
        from schema import TradingContext as TC
        if not isinstance(ctx, TC):
            raise typer.BadParameter("Context parsed as algo but mode is manual.")

        cards = retrieve(ctx, top_k=top_k)
        gen = generate_playbooks(ctx, cards, prefix=prefix)
        playbooks = gen["playbooks"]
        if not playbooks:
            raise typer.BadParameter("Generator produced no valid playbooks.")

        reviews = critique_playbooks(ctx, playbooks).get("reviews", [])
        with_critique = attach_critiques(playbooks, reviews)
        kept = filter_by_verdict(with_critique, drop_rejected=True)

        scored: list[dict] = []
        for pb in kept:
            ps = score_playbook(pb, data_dir=prices_dir or Path("data/prices"), skip_scenarios=skip_scenarios)
            scored.append({"playbook": pb, "score": asdict(ps)})
        scored.sort(key=lambda x: x["score"]["composite"], reverse=True)

        out_path = ROUNDS_DIR / f"{round_id}_playbook.json"
        out_path.write_text(
            json.dumps({"round_id": round_id, "prompt": prompt, "playbooks": scored}, indent=2)
        )
        console.print(f"[green]Report:[/] {out_path}  ({len(scored)} playbooks ranked)")

    else:
        raise typer.BadParameter("mode must be 'algo' or 'manual'")


@app.command("wq-check")
def wq_check_cmd(
    expression: Optional[str] = typer.Argument(
        None, help="BRAIN expression as a string. Use --file to read from a file."
    ),
    file: Optional[Path] = typer.Option(
        None, "--file", "-f", help="Read the expression from a file (.txt)."
    ),
    history: Path = typer.Option(
        Path("knowledge/worldquant_iqc/alpha_history.md"),
        help="Path to alpha_history.md for self-correlation pre-check.",
    ),
) -> None:
    """Pre-flight a BRAIN alpha expression locally before pasting to BRAIN.

    Runs the WorldQuant BRAIN syntax validator + a token-level self-correlation
    heuristic against alpha_history.md. Prints any blockers, warnings, and
    near-duplicate prior submissions so you can repair the expression locally
    instead of burning a BRAIN submission slot.
    """
    if file is not None:
        if not file.exists():
            raise typer.BadParameter(f"file not found: {file}")
        text = file.read_text(encoding="utf-8")
    elif expression is not None:
        text = expression
    else:
        raise typer.BadParameter("Provide an expression argument or --file path.")

    expr = text.strip()
    if not expr:
        console.print("[red]ERROR:[/] empty expression.")
        raise typer.Exit(code=2)

    plugin = competitions.load_plugin("worldquant_iqc")
    if plugin is None:
        console.print("[red]ERROR:[/] worldquant_iqc plugin not loaded.")
        raise typer.Exit(code=2)

    # Re-use the plugin's _validate so wq-check stays consistent with what
    # the synthesis pipeline uses.
    from competitions.worldquant_iqc.plugin import _validate  # type: ignore

    warnings = _validate(expr)
    blockers = [w for w in warnings if w.startswith("ERROR")]
    advisories = [w for w in warnings if not w.startswith("ERROR")]

    console.print("\n[bold]Expression preview[/]")
    preview = expr.replace("\n", " ")
    console.print(f"  {preview[:200]}{'…' if len(preview) > 200 else ''}")

    if blockers:
        console.print(f"\n[bold red]Blockers ({len(blockers)})[/] — fix before submitting:")
        for w in blockers:
            console.print(f"  • {w}")
    else:
        console.print("\n[bold green]Syntax: clean[/] — no blocker issues.")

    if advisories:
        console.print(f"\n[bold yellow]Advisories ({len(advisories)})[/]")
        for w in advisories:
            console.print(f"  • {w}")

    # Self-correlation pre-check against prior submissions in alpha_history.md.
    near = _self_correlation_candidates(expr, history)
    if near:
        console.print(
            f"\n[bold yellow]Self-correlation risk ({len(near)} prior submissions)[/]"
        )
        for sim, name, snippet in near:
            console.print(f"  • [bold]{sim:.0%}[/] overlap with {name}")
            console.print(f"      {snippet}")
    else:
        console.print("\n[bold green]Self-correlation: looks novel[/] vs alpha_history.md.")

    console.print("\n[dim]Gate reminder: Sharpe>1.25 | Turnover 1-70% | Fitness>1.0 | "
                  "Sub-Sharpe>0.45 | Weight distributed | Self-corr<0.7 | "
                  "Competitions match | Syntax clean[/]")

    raise typer.Exit(code=1 if blockers else 0)


def _self_correlation_candidates(
    expr: str, history_path: Path
) -> list[tuple[float, str, str]]:
    """Return prior submissions whose token signature overlaps >= 50% with expr."""
    if not history_path.exists():
        return []
    import re

    def tokens(s: str) -> set[str]:
        return {
            t for t in re.findall(r"[a-z_][a-z0-9_]*", s.lower())
            if len(t) > 2 and not t.isdigit()
        }

    expr_tokens = tokens(expr)
    if not expr_tokens:
        return []

    text = history_path.read_text(encoding="utf-8")
    sections = re.split(r"\n###\s+", text)
    matches: list[tuple[float, str, str]] = []
    for section in sections[1:]:
        head, *_ = section.split("\n", 1)
        name = head.strip()
        m = re.search(r"```\s*\n(.*?)\n```", section, re.DOTALL)
        if not m:
            continue
        prior_expr = m.group(1).strip()
        prior_tokens = tokens(prior_expr)
        if not prior_tokens:
            continue
        union = expr_tokens | prior_tokens
        inter = expr_tokens & prior_tokens
        sim = len(inter) / len(union) if union else 0.0
        if sim >= 0.5:
            matches.append((sim, name, prior_expr[:120].replace("\n", " ")))
    matches.sort(reverse=True)
    return matches


@app.command("alpha-gpt")
def alpha_gpt_cmd(
    prompt: str = typer.Option(..., "--prompt", "-p", help="Trader hypothesis (free-text)."),
    rounds: int = typer.Option(3, help="Refinement rounds after seeding."),
    n_seed: int = typer.Option(5, help="How many seed candidates to ask the LLM for."),
    beam: int = typer.Option(3, help="Beam width — top-N kept between rounds."),
    mutations_per_parent: int = typer.Option(3, help="Mutations to ask for per surviving parent."),
    backend: Optional[str] = typer.Option(
        None,
        help="Force LLM backend: claude_sdk | claude_cli | openai_sdk | codex_cli. "
             "Default honors STRATENGINE_LLM_BACKEND or auto-resolves.",
    ),
    out: Optional[Path] = typer.Option(None, help="Write the full LoopResult JSON here."),
) -> None:
    """Autonomous Alpha-GPT loop for WorldQuant BRAIN.

    Seeds N candidates from your hypothesis, then iteratively mutates the
    surviving best on every round using the local BRAIN syntax validator
    and self-correlation pre-check as the fitness signal. Final output is
    a small ranked list of distinct, syntactically-clean candidates ready
    for you to paste into the BRAIN IDE.

    Backend is pluggable: Claude CLI by default if you have `claude` on
    PATH; switch to Codex via `--backend codex_cli` or
    `STRATENGINE_LLM_BACKEND=codex_cli` if you prefer the OpenAI codex CLI.
    """
    import alpha_gpt

    if backend:
        os.environ["STRATENGINE_LLM_BACKEND"] = backend

    console.print(f"[bold cyan]Alpha-GPT loop[/] · rounds={rounds} · beam={beam} · seeds={n_seed}")
    console.print(f"[dim]backend = {os.environ.get('STRATENGINE_LLM_BACKEND', 'auto')}[/]")
    res = alpha_gpt.run_loop(
        hypothesis=prompt,
        rounds=rounds,
        n_seed=n_seed,
        beam=beam,
        mutations_per_parent=mutations_per_parent,
    )

    console.print(f"\n[bold green]Final {len(res.final)} candidates[/] (after {rounds} rounds)\n")
    for i, c in enumerate(res.final, 1):
        console.print(f"[bold]{i}. {c.name}[/]  score={c.score:.2f}  expr_id={c.expr_id}")
        console.print(f"   thesis: {c.thesis}")
        console.print(f"   expr  : {c.expression[:160]}{'…' if len(c.expression) > 160 else ''}")
        console.print(f"   config: {c.config}")
        if c.blockers:
            console.print(f"   [red]blockers[/]: {len(c.blockers)} — re-run or fix manually")
        if c.self_corr:
            top = c.self_corr[0]
            console.print(f"   [yellow]self-corr[/]: {top[0]:.0%} vs {top[1]}")
        console.print("")

    if out:
        import alpha_gpt as _ag
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(_ag.serialize_result(res), indent=2))
        console.print(f"[dim]Full history → {out}[/]")


if __name__ == "__main__":
    app()
