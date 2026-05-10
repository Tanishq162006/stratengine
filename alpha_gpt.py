"""Alpha-GPT autonomous loop for WorldQuant BRAIN.

Implements the iterative human-AI alpha-mining loop from
arXiv:2308.00016 ("Alpha-GPT: Human-AI Interactive Alpha Mining for
Quantitative Investment"), adapted to BRAIN's submission gates and to
StratEngine's existing prompts.

Loop shape:

    seed N candidates from a hypothesis
        ↓
    for round in 1..R:
        local pre-flight (BRAIN syntax validator + self-corr vs alpha_history)
        keep top-B by structural quality score
        for each survivor:
            ask LLM for K mutations (refine_brain prompt)
            pre-flight + score the mutations
        merge survivors + mutations, dedupe, keep top-B
    ↓
    output ranked list of final alphas with diagnostics

The "score" here is a structural heuristic (presence of canonical pipeline
elements, novelty vs prior submissions, operator diversity) — not a true
backtest. BRAIN itself is the only place that can produce real Sharpe /
Fitness numbers, so the loop's job is to feed the user a small number of
high-quality, distinct candidates ready to paste.

Backend-agnostic: routes through `llm_client.complete`, which honors
`STRATENGINE_LLM_BACKEND={claude_sdk,claude_cli,openai_sdk,codex_cli,auto}`.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path

import llm_client
from competitions.worldquant_iqc.plugin import _validate as wq_validate
from config import PROMPTS_DIR, ROOT, load_settings


HISTORY_PATH = ROOT / "knowledge" / "worldquant_iqc" / "alpha_history.md"


@dataclass
class Candidate:
    name: str
    thesis: str
    expression: str
    fields_used: list[str]
    horizon_days: int
    config: dict
    why_gates: str
    score: float = 0.0
    blockers: list[str] = field(default_factory=list)
    advisories: list[str] = field(default_factory=list)
    self_corr: list[tuple[float, str]] = field(default_factory=list)
    parent: str | None = None
    round_born: int = 0

    @property
    def expr_id(self) -> str:
        return hashlib.sha1(self.expression.strip().encode()).hexdigest()[:10]


# ---------- Local pre-flight ----------

def _tokens(s: str) -> set[str]:
    return {
        t for t in re.findall(r"[a-z_][a-z0-9_]*", s.lower())
        if len(t) > 2 and not t.isdigit()
    }


def _prior_alphas(history_path: Path = HISTORY_PATH) -> list[tuple[str, str]]:
    if not history_path.exists():
        return []
    text = history_path.read_text(encoding="utf-8")
    sections = re.split(r"\n###\s+", text)
    out: list[tuple[str, str]] = []
    for section in sections[1:]:
        head, *_ = section.split("\n", 1)
        m = re.search(r"```\s*\n(.*?)\n```", section, re.DOTALL)
        if m:
            out.append((head.strip(), m.group(1).strip()))
    return out


def _self_corr(expr: str, priors: list[tuple[str, str]]) -> list[tuple[float, str]]:
    et = _tokens(expr)
    if not et:
        return []
    matches: list[tuple[float, str]] = []
    for name, prior in priors:
        pt = _tokens(prior)
        if not pt:
            continue
        sim = len(et & pt) / max(len(et | pt), 1)
        if sim >= 0.5:
            matches.append((sim, name))
    matches.sort(reverse=True)
    return matches


# Heuristic structural score. Higher is better. Pure local — no LLM.
def _score_structure(c: Candidate) -> float:
    expr = c.expression
    s = 0.0
    # Canonical pipeline presence
    if expr.strip().startswith("scale("):
        s += 1.5
    if "group_neutralize" in expr or "neutralize" in expr:
        s += 1.5
    if "winsorize(" in expr:
        s += 0.5
    if re.search(r"\bzscore\s*\(", expr):
        s += 1.0  # cross-sectional zscore preserves Fitness
    elif re.search(r"\brank\s*\(", expr):
        s += 0.3  # rank works but compresses magnitude
    if re.search(r"\bts_zscore\s*\(", expr) or re.search(r"\bts_rank\s*\(", expr):
        s += 0.5
    # Operator diversity
    ops = set(re.findall(r"\b([a-z_][a-z0-9_]*)\s*\(", expr))
    s += min(len(ops), 8) * 0.15
    # Penalties
    s -= 4.0 * len(c.blockers)
    if c.self_corr:
        worst = c.self_corr[0][0]
        if worst >= 0.7:
            s -= 3.0
        elif worst >= 0.6:
            s -= 1.5
        elif worst >= 0.5:
            s -= 0.5
    return s


def preflight(c: Candidate, priors: list[tuple[str, str]]) -> Candidate:
    warns = wq_validate(c.expression)
    c.blockers = [w for w in warns if w.startswith("ERROR")]
    c.advisories = [w for w in warns if not w.startswith("ERROR")]
    c.self_corr = _self_corr(c.expression, priors)
    c.score = _score_structure(c)
    return c


# ---------- LLM seed + mutate ----------

def _load_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def _render(template: str, **kwargs) -> str:
    out = template
    for k, v in kwargs.items():
        out = out.replace("{{" + k + "}}", v)
    return out


def _parse_json_block(text: str) -> dict:
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        raise ValueError(f"no JSON in model output: {text[:200]}")
    return json.loads(m.group(0))


def seed_candidates(hypothesis: str, n: int, priors: list[tuple[str, str]]) -> list[Candidate]:
    settings = load_settings()
    prior_text = "\n".join(f"- {n}: {e[:120]}" for n, e in priors[-10:]) or "(none yet)"
    prompt = _render(
        _load_prompt("alpha_gpt_seed.txt"),
        hypothesis=hypothesis,
        prior_alphas=prior_text,
        n_candidates=str(n),
    )
    text = llm_client.complete(
        model=settings.synth_model, prompt=prompt, max_tokens=4096, timeout=600,
    )
    data = _parse_json_block(text)
    return [
        Candidate(
            name=item.get("name", f"cand_{i}"),
            thesis=item.get("thesis", ""),
            expression=item.get("expression", "").strip(),
            fields_used=item.get("fields_used", []),
            horizon_days=int(item.get("horizon_days", 5) or 5),
            config=item.get("config", {}),
            why_gates=item.get("why_8_gates_clear", ""),
        )
        for i, item in enumerate(data.get("candidates", []))
    ]


def mutate(parent: Candidate, k: int, priors: list[tuple[str, str]]) -> list[Candidate]:
    """Use the existing refine_brain prompt to mutate a parent expression."""
    settings = load_settings()
    fake_results = {
        "blockers": parent.blockers,
        "advisories": parent.advisories,
        "self_corr_top": parent.self_corr[0] if parent.self_corr else None,
        "structural_score": parent.score,
        "comment": (
            "Local pre-flight only — no real BRAIN backtest yet. "
            "Mutate to repair blockers, increase novelty vs prior alphas, "
            "and strengthen the canonical pipeline."
        ),
    }
    examples = "\n".join(f"- {n}: {e[:120]}" for n, e in priors[-5:]) or "(none yet)"
    prompt_tpl = _load_prompt("refine_brain.txt")
    prompt = (
        prompt_tpl
        .replace("{{current_expression}}", parent.expression)
        .replace("{{brain_results}}", json.dumps(fake_results, indent=2))
        .replace("{{examples}}", examples)
    )
    text = llm_client.complete(
        model=settings.critic_model, prompt=prompt, max_tokens=3000, timeout=600,
    )
    data = _parse_json_block(text)
    out: list[Candidate] = []
    for i, mut in enumerate((data.get("mutations") or [])[:k]):
        out.append(Candidate(
            name=f"{parent.name}/mut_{i}",
            thesis=mut.get("change", ""),
            expression=(mut.get("expression") or "").strip(),
            fields_used=parent.fields_used,
            horizon_days=parent.horizon_days,
            config=parent.config,
            why_gates="(mutation — diagnostic in thesis)",
            parent=parent.name,
        ))
    return out


# ---------- Loop ----------

@dataclass
class LoopResult:
    rounds: int
    final: list[Candidate]
    history: list[list[Candidate]]


def run_loop(
    hypothesis: str,
    rounds: int = 3,
    n_seed: int = 5,
    beam: int = 3,
    mutations_per_parent: int = 3,
) -> LoopResult:
    priors = _prior_alphas()
    history: list[list[Candidate]] = []

    seeds = seed_candidates(hypothesis, n=n_seed, priors=priors)
    for c in seeds:
        c.round_born = 0
        preflight(c, priors)
    seeds = sorted(seeds, key=lambda c: c.score, reverse=True)
    history.append(seeds)
    survivors = [c for c in seeds if not c.blockers][:beam] or seeds[:beam]

    for r in range(1, rounds + 1):
        next_pool: list[Candidate] = []
        for parent in survivors:
            try:
                muts = mutate(parent, k=mutations_per_parent, priors=priors)
            except Exception as e:  # noqa: BLE001 - keep loop alive on a single LLM failure
                muts = []
                parent.advisories.append(f"WARN: mutation step failed: {e}")
            for m in muts:
                m.round_born = r
                preflight(m, priors)
                next_pool.append(m)
        # combine survivors (de-deduplicated by expr_id) + new mutations
        seen: set[str] = set()
        merged: list[Candidate] = []
        for c in survivors + next_pool:
            if c.expr_id in seen:
                continue
            seen.add(c.expr_id)
            merged.append(c)
        merged.sort(key=lambda c: c.score, reverse=True)
        history.append(merged)
        clean = [c for c in merged if not c.blockers]
        survivors = (clean or merged)[:beam]

    return LoopResult(rounds=rounds, final=survivors, history=history)


def serialize_result(res: LoopResult) -> dict:
    def _c(c: Candidate) -> dict:
        d = asdict(c)
        d["expr_id"] = c.expr_id
        d["self_corr"] = [{"sim": s, "name": n} for s, n in c.self_corr]
        return d

    return {
        "rounds": res.rounds,
        "final": [_c(c) for c in res.final],
        "history": [[_c(c) for c in round_pool] for round_pool in res.history],
    }
