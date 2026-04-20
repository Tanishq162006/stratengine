"""Idea-to-report pipeline. One command: context in, markdown report out."""
from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from rich.console import Console

from config import ensure_dirs
from decision_scorer import score_playbook
from evaluator import evaluate, rank as rank_results
from generator import generate
from manual_critic import attach_critiques, critique_playbooks, filter_by_verdict
from playbook_generator import generate_playbooks
from retriever import retrieve
from schema import RoundContext, TradingContext

console = Console()


def _render_algo_report(round_id: str, ctx: RoundContext, cards, result, scored_results) -> str:
    lines = [f"# StratEngine Report — algo round {round_id}", ""]
    lines.append("## RoundContext summary")
    lines.append("```json")
    lines.append(ctx.model_dump_json(indent=2))
    lines.append("```")
    lines.append(f"\n## Retrieved cards ({len(cards)})")
    for c in cards[:10]:
        lines.append(
            f"- **{c.title}** — {c.strategy_family.value}/{c.asset_class.value}/"
            f"{c.timeframe.value} (conf {c.confidence:.2f}) — {c.source}"
        )
    lines.append(f"\n## Candidates ({len(result['candidates'])})")
    for i, item in enumerate(result["candidates"]):
        cand = item["candidate"]
        lines.append(f"\n### {i+1}. {cand.get('name')}")
        lines.append(f"- **Thesis:** {cand.get('thesis', '')}")
        lines.append(f"- **Family:** {cand.get('strategy_family')}")
        lines.append(f"- **Source cards:** {', '.join(cand.get('source_card_ids', []))}")
        review = cand.get("_review") or {}
        if review:
            lines.append(f"- **Critic verdict:** {review.get('verdict', 'accept')}")
            for issue in review.get("issues", []):
                lines.append(
                    f"  - [{issue.get('severity','?')}] {issue.get('category','?')}: "
                    f"{issue.get('explanation','')}"
                )
    if scored_results is not None:
        lines.append(f"\n## Ranked backtest results")
        lines.append("| Rank | Candidate | Score | Sharpe | MaxDD | Violations |")
        lines.append("|---:|---|---:|---:|---:|---|")
        for i, r in enumerate(scored_results):
            stats = r.stats or {}
            lines.append(
                f"| {i+1} | {r.candidate_name} | {r.score:.3f} | "
                f"{stats.get('sharpe', 0):.3f} | {stats.get('max_drawdown', 0):.3f} | "
                f"{', '.join(r.violations) or '-'} |"
            )
    lines.append("\n## Postmortem (fill after round)")
    lines.append("- Actual round result:")
    lines.append("- What surprised us:")
    lines.append("- What the system got right / wrong:")
    lines.append("- Card(s) that proved most useful:")
    lines.append("- Update source quality? family performance? prompt versions?")
    return "\n".join(lines)


def _render_manual_report(round_id: str, ctx: TradingContext, cards, scored) -> str:
    lines = [f"# StratEngine Report — manual round {round_id}", ""]
    lines.append("## TradingContext summary")
    lines.append("```json")
    lines.append(ctx.model_dump_json(indent=2))
    lines.append("```")
    lines.append(f"\n## Retrieved cards ({len(cards)})")
    for c in cards[:10]:
        lines.append(
            f"- **{c.title}** — {c.strategy_family.value}/{c.asset_class.value}/"
            f"{c.timeframe.value} (conf {c.confidence:.2f}) — {c.source}"
        )
    lines.append(f"\n## Ranked playbooks ({len(scored)})")
    lines.append("| Rank | Name | Composite | Clarity | Risk | Load | Regime | History |")
    lines.append("|---:|---|---:|---:|---:|---:|---:|---:|")
    for i, item in enumerate(scored):
        s = item["score"]
        lines.append(
            f"| {i+1} | {item['playbook'].get('name','?')} | {s['composite']:.3f} | "
            f"{s['signal_clarity']:.2f} | {s['risk_completeness']:.2f} | "
            f"{s['cognitive_load']:.2f} | {s['regime_specificity']:.2f} | "
            f"{s['historical_scenarios']:.2f} |"
        )
    lines.append("\n## Postmortem (fill after trading)")
    lines.append("- Did you take any of these trades?")
    lines.append("- Which playbook survived contact with the market?")
    lines.append("- What broke under pressure?")
    lines.append("- Update source quality / family performance / prompt versions?")
    return "\n".join(lines)


def generate_report(
    context_path: Path,
    mode: str = "algo",
    *,
    top_k: int = 10,
    data: Optional[Path] = None,
    prices_dir: Optional[Path] = None,
    skip_scenarios: bool = False,
) -> Path:
    ensure_dirs()
    raw = json.loads(Path(context_path).read_text())
    round_id = str(int(time.time()))
    from config import MEMORY_DIR

    reports_dir = MEMORY_DIR / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    if mode == "algo":
        ctx = RoundContext.model_validate(raw)
        cards = retrieve(ctx, top_k=top_k)
        result = generate(ctx, cards)
        scored_results = None
        if data is not None:
            rs = [evaluate(item["candidate"], item["code"], ctx, data) for item in result["candidates"]]
            scored_results = rank_results(rs)
        md = _render_algo_report(round_id, ctx, cards, result, scored_results)
    elif mode == "manual":
        tctx = TradingContext.model_validate(raw)
        cards = retrieve(tctx, top_k=top_k)
        gen = generate_playbooks(tctx, cards)
        if not gen["playbooks"]:
            raise RuntimeError("No valid playbooks generated.")
        reviews = critique_playbooks(tctx, gen["playbooks"]).get("reviews", [])
        with_crit = attach_critiques(gen["playbooks"], reviews)
        kept = filter_by_verdict(with_crit)
        scored = []
        for pb in kept:
            ps = score_playbook(
                pb,
                data_dir=prices_dir or Path("data/prices"),
                skip_scenarios=skip_scenarios,
            )
            scored.append({"playbook": pb, "score": asdict(ps)})
        scored.sort(key=lambda x: x["score"]["composite"], reverse=True)
        md = _render_manual_report(round_id, tctx, cards, scored)
    else:
        raise ValueError("mode must be 'algo' or 'manual'")

    out = reports_dir / f"{round_id}_{mode}.md"
    out.write_text(md)
    return out
