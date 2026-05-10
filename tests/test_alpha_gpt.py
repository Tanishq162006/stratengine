"""alpha_gpt loop — llm_client mocked. Exercises seed/mutate/preflight."""
from __future__ import annotations

import json
from pathlib import Path

import alpha_gpt


GOOD_EXPR = (
    "scale(group_neutralize(zscore(ts_zscore(winsorize("
    "(-ts_mean(returns, 5)) * rank(volume / (ts_mean(volume, 20) + 0.0001))"
    "), 252)), subindustry))"
)


def _seed_payload(n: int) -> str:
    return json.dumps({
        "candidates": [
            {
                "name": f"cand_{i}",
                "thesis": f"Test candidate {i}",
                "fields_used": ["returns", "volume"],
                "horizon_days": 5,
                "expression": GOOD_EXPR if i == 0 else GOOD_EXPR.replace("returns, 5", f"returns, {5+i}"),
                "config": {"decay": 4, "delay": 1, "truncation": 0.08, "neutralization": "subindustry", "universe": "TOP3000", "region": "USA"},
                "why_8_gates_clear": "All gates plausible.",
            }
            for i in range(n)
        ]
    })


def _mutation_payload(parent_expr: str, k: int) -> str:
    return json.dumps({
        "diagnosis": "Score is fine; vary window.",
        "mutations": [
            {
                "name": f"mut_{i}",
                "change": f"shorten ts window by {i+1}",
                "expression": parent_expr.replace("returns, 5", f"returns, {3+i}"),
            }
            for i in range(k)
        ],
    })


def test_preflight_scores_clean_expression(monkeypatch):
    cand = alpha_gpt.Candidate(
        name="x", thesis="t", expression=GOOD_EXPR,
        fields_used=["returns"], horizon_days=5,
        config={}, why_gates="",
    )
    alpha_gpt.preflight(cand, priors=[])
    assert cand.blockers == []
    assert cand.score > 2.0


def test_preflight_flags_variable_assignment():
    cand = alpha_gpt.Candidate(
        name="bad", thesis="t",
        expression="x = volume / ts_mean(volume, 20); scale(rank(x))",
        fields_used=[], horizon_days=5, config={}, why_gates="",
    )
    alpha_gpt.preflight(cand, priors=[])
    assert any("ERROR" in b for b in cand.blockers)


def test_seed_candidates_parses_llm_output(monkeypatch):
    monkeypatch.setattr("llm_client.complete", lambda **kw: _seed_payload(3))
    seeds = alpha_gpt.seed_candidates("test hypothesis", n=3, priors=[])
    assert len(seeds) == 3
    assert seeds[0].expression.startswith("scale(")


def test_run_loop_end_to_end(monkeypatch, tmp_path):
    """Seed → 1 round of mutation → final. All clean expressions, no real LLM."""
    call_count = {"seed": 0, "mut": 0}

    def fake_complete(**kw):
        prompt = kw.get("prompt", "")
        if "alpha researcher" in prompt or "{{hypothesis}}" not in prompt and "candidates" in prompt[:500] and "current expression" not in prompt.lower():
            # heuristic: seed prompt includes "alpha researcher" header
            pass
        if "current expression" in prompt.lower() or "Current expression:" in prompt:
            call_count["mut"] += 1
            return _mutation_payload(GOOD_EXPR, k=2)
        call_count["seed"] += 1
        return _seed_payload(3)

    monkeypatch.setattr("llm_client.complete", fake_complete)
    # Avoid touching real history
    monkeypatch.setattr(alpha_gpt, "_prior_alphas", lambda: [])

    res = alpha_gpt.run_loop(
        hypothesis="short-term reversal in liquid US equities",
        rounds=1, n_seed=3, beam=2, mutations_per_parent=2,
    )
    assert res.rounds == 1
    assert len(res.final) <= 2
    assert all(not c.blockers for c in res.final)
    # Seeded once; mutated for each surviving parent
    assert call_count["seed"] == 1
    assert call_count["mut"] >= 1
