# Alpha History — WorldQuant IQC 2026

RAG#0 database: past submitted alphas with results. Used by the Search Enhancement agent
to learn what works and avoid repeating failures.

Pattern inspired by:
- Modi, P. (2024). alpha-gpt. GitHub. https://github.com/parthmodi152/alpha-gpt
  (`sota_alphas` + `hypothesis_history` + `BacktestResult` state tracking)
- Wang et al. (2025). Alpha-GPT. arXiv:2308.00016v2. (RAG#0 concept)

## Format
Each entry: expression, BRAIN settings, test results (Sharpe, Fitness, Sub-Sharpe, Turnover, IC if known), lessons.
`sota` = state-of-the-art: best result so far on any metric.

---

## Submitted Alphas

### alpha_001 — Volume-Confirmed Reversal v1
**Expression:**
```
scale(group_neutralize(rank(ts_zscore(winsorize((-ts_mean(returns, 5)) * rank(volume / (ts_mean(volume, 20) + 1))), 252)), subindustry))
```
**Results:** Sharpe 1.47 PASS | Turnover 41.84% PASS | Fitness 0.78 FAIL | Sub-Sharpe 0.94 PASS
**Issues:** Unit warning (added 1 to TSShare field). Fitness below 1.0 (rank at cross-sectional step killed magnitude).
**Lesson:** Never add dimensionless constant to typed field. Use zscore not rank for fitness.

---

### alpha_002 — Volume-Confirmed Reversal v2
**Expression:**
```
scale(group_neutralize(rank(ts_zscore(winsorize((-ts_mean(returns, 10)) * ts_rank(volume, 20)), 252)), subindustry))
```
**Results:** Sharpe 1.04 FAIL | Turnover 33.72% PASS | Fitness 0.50 FAIL | Sub-Sharpe 0.35 FAIL
**Issues:** 10-day returns too slow — killed the reversal edge. ts_rank(volume) changed signal character.
**Lesson:** 5-day reversal is the core alpha. Do NOT change returns window to fix other issues.

---

## Patterns That Work
- 5-day return reversal has genuine alpha in USA TOP3000
- Volume amplification confirms reversal strength
- zscore > rank at cross-sectional step for Fitness

## Patterns That Failed
- 10-day returns: too slow, loses reversal edge
- Adding `+1` to TSShare fields: unit warning
- rank() at cross-sectional: kills magnitude, hurts Fitness
- ts_rank(volume, 20) replacing rank(volume/ts_mean(volume,20)): different signal, worse results
