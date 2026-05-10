# WorldQuant IQC — Scoring Rules and Submission Mechanics

Distilled from public seminar notes. These are the meta-rules that decide
whether two alphas with identical syntax/Sharpe will score very differently
on the leaderboard. Keep this card on hand alongside `wq_standard.md`.

## Daily Score

- **Cap = 2000 points/day.** Achievable with 1–2 strong alphas.
- Score depends on **quantity × average alpha quality**.
- Quality boosters: smaller universe, lower self-correlation, higher
  fitness, **longer delay** (delay-1 > delay-0).
- Score is normalised across all users with ≥1 submission that day.

## IQC Final Scoring (Stage 1 + Stage 2)

- IQC final score uses **Merged PnL** across all team members and all alphas.
- **Equal weighting** across submitted alphas — diversity matters more than
  one extra-strong alpha.
- Considers Sharpe, returns/drawdown, and turnover jointly.
- **Always check the "before/after" score in the Performance Comparison tab
  before clicking submit.** A weak alpha can drag your merged PnL.
- Stage 1 = in-sample only. Stage 2 = out-of-sample.
- **Delay-0 contributions divided by 3** in the final score → a delay-1
  alpha is worth 3× a delay-0 alpha of equal quality. Default to delay 1.

## Tier Thresholds

| Tier | Cumulative score |
|---|---|
| Bronze | > 1,000 |
| Silver | > 5,000 |
| Gold | > 10,000 (interview-eligible) |

## Self-Correlation

- Computed from the **PnL graph**, not alpha weights.
- 2-year rolling window. Inner correlation uses the intersection of the
  two alphas' PnL time periods.
- Alphas with high self-correlation can still be submitted **if Sharpe is
  improved by ≥10%** over the prior submission.

## Sub-Universe Sharpe

- Threshold **scales with sub-universe size**. The 0.45 figure on
  `wq_standard.md` is the floor for TOP3000-scale universes; smaller
  universes face stricter thresholds.

## In-Sample / Out-of-Sample Windows

- **In-sample window**: 7 years ago → 2 years ago (rolls daily).
- **OOS window**: the past 1 year. Used for Stage-2 scoring and OS testing.
- Overfitting in-sample destroys OOS Sharpe — favour fewer parameters and
  shorter windows.

## Turnover Definition

- Reported turnover = **average daily turnover**.
- Daily turnover = % of portfolio bought/sold between today and yesterday,
  by dollar value.

## Free Points

- Run every alpha against **USA D0, USA D1, CHN D0, CHN D1** — region
  alphas are highly uncorrelated and these often submit independently.
- Re-use Round-1 alphas in Round 2 (subject to self-correlation gate).
- Submit **every day** — consistency compounds via daily-score quantity term.

## Practical Submission Heuristics

1. **Diversity beats incremental Sharpe.** Two uncorrelated 1.4-Sharpe
   alphas merge to a higher PnL than one 1.6-Sharpe alpha plus its near-clone.
2. **Delay-1 first.** Build the delay-1 version before the delay-0 version.
3. **Default to TOP3000.** Move to TOP1000 / TOP200 only when
   sub-universe Sharpe is the bottleneck.
4. **Truncation 0.05–0.10** is the recommended band. `0.01` is only for
   `rank()`-based outputs where the ranking already prevents over-weighting.
5. **Decay reduces turnover but attenuates signal** — avoid using decay as
   a turnover dial when the underlying signal is weak; fix the signal first.
6. **NaN handling** is built-in: 0 for time-series data, group
   mean/median/count for group data.
7. **Unit handling** raises a warning if mismatched units are combined
   (e.g. price + volume). The local validator already rejects bare
   integer + typed-field; rely on it instead of relying on BRAIN's warning.
