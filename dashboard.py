"""CLI dashboard: everything at a glance."""
from __future__ import annotations

import sqlite3
from collections import Counter

from rich.console import Console
from rich.table import Table

from config import MEMORY_DIR, load_settings
from family_analyzer import ranked_win_rates
from prompt_analyzer import per_template_stats
from schema import StrategyCard
from source_quality import all_scores

console = Console()


def _all_cards() -> list[StrategyCard]:
    s = load_settings()
    if not s.db_path.exists():
        return []
    con = sqlite3.connect(s.db_path)
    try:
        rows = con.execute("SELECT card_json FROM cards").fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        con.close()
    return [StrategyCard.model_validate_json(r[0]) for r in rows]


def render() -> None:
    cards = _all_cards()
    console.print(f"[bold]Knowledge base:[/] {len(cards)} strategy cards")

    if cards:
        by_source = Counter(c.source for c in cards)
        by_family = Counter(c.strategy_family.value for c in cards)
        by_asset = Counter(c.asset_class.value for c in cards)
        table = Table(title="Cards by dimension (top 8 each)")
        for col in ("Source", "Count", "Family", "Count", "Asset", "Count"):
            table.add_column(col)
        pairs = list(zip(by_source.most_common(8), by_family.most_common(8), by_asset.most_common(8)))
        for (s, sc), (f, fc), (a, ac) in pairs:
            table.add_row(s, str(sc), f, str(fc), a, str(ac))
        console.print(table)

    # Source quality
    scores = all_scores()
    if scores:
        table = Table(title="Source quality")
        for col in ("Source", "Composite", "Extract", "Quality", "Survival", "Clarity"):
            table.add_column(col)
        scores.sort(key=lambda r: r.composite, reverse=True)
        for r in scores[:10]:
            table.add_row(
                r.source_name,
                f"{r.composite:.3f}",
                f"{r.extraction_success_rate:.2f}",
                f"{r.card_quality_score:.2f}",
                f"{r.backtest_survival_rate:.2f}",
                f"{r.playbook_clarity_score:.2f}",
            )
        console.print(table)

    # Family win rates
    rates = ranked_win_rates()
    if rates:
        table = Table(title="Family win rates (all round types)")
        for col in ("Family", "n", "Wins", "Rate"):
            table.add_column(col)
        for r in rates[:12]:
            table.add_row(r.family, str(r.n), str(r.wins), f"{r.rate:.3f}")
        console.print(table)

    # Prompt stats
    prompts = per_template_stats()
    if prompts:
        table = Table(title="Prompt template performance")
        for col in ("Template", "Version", "n", "Success", "Failure", "Mean metric"):
            table.add_column(col)
        for p in prompts:
            table.add_row(
                p.template,
                p.version,
                str(p.n_total),
                str(p.n_success),
                str(p.n_failure),
                f"{p.mean_metric:.3f}" if p.mean_metric is not None else "-",
            )
        console.print(table)

    # Recent rounds
    reports_dir = MEMORY_DIR / "reports"
    if reports_dir.exists():
        reports = sorted(reports_dir.glob("*.md"))[-5:]
        if reports:
            console.print("[bold]Recent reports:[/]")
            for r in reports:
                console.print(f"  - {r.name}")
