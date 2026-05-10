# WorldQuant BRAIN — Submission Standard (canonical)

Single source of truth for the 8 BRAIN submission criteria, syntax invariants,
and diagnostic playbook. Every BRAIN-targeted prompt (synthesize_brain,
code_brain, refine_brain, critic) must satisfy this standard before output.

## The 8 Submission Criteria

| # | Criterion | Threshold | Common cause when failed |
|---|---|---|---|
| 1 | Sharpe | > 1.25 | Signal too weak / too noisy. Shorten lookback or combine with a confirming signal. |
| 2 | Turnover (lower) | > 1% | Signal too smooth — windows too long, decay too heavy. Shorten or drop decay. |
| 3 | Turnover (upper) | < 70% | Signal too jittery — windows too short. Lengthen or add ts_decay_linear. |
| 4 | Weight distribution | well distributed | Missing scale() or missing group_neutralize. Always end pipeline with scale(group_neutralize(...)). |
| 5 | Competitions match | Challenge / IQC 2026 Stage 1 | Pipeline targets a universe/neutralization the competition doesn't allow. |
| 6 | Fitness | > 1.0 | rank() at the cross-sectional step compresses magnitude. Use zscore() instead, or shorten ts_zscore window (252 → 63 → 20). |
| 7 | Sub-universe Sharpe | > 0.45 | Signal captures industry beta, not stock alpha. Add group_neutralize(x, subindustry); use universal liquid fields (returns, volume, close, vwap, open, high, low). |
| 8 | Self-correlation | < 0.7 vs prior submissions | Reuses an existing alpha shape. Combine with a novel field or operator family. |

## Hard Syntax Invariants

These are compile-time failures on the BRAIN platform. The
`competitions/worldquant_iqc/plugin.py` validator rejects them locally so
violations bounce back to the model.

1. **Single nested expression.** No variable assignment (`x = ...`).
2. **Outermost is `scale(...)`.** Required for sum(|w|) == 1.
3. **`scale` wraps `group_neutralize(..., subindustry)`** (or `industry` if
   subindustry is too sparse). Without this, Sub-universe Sharpe collapses.
4. **`winsorize(x)` takes exactly one argument.** No std parameter.
5. **No bare integer added to typed fields.** `volume + 1` ❌, use a ratio
   instead: `volume / (ts_mean(volume, 20) + 0.0001)` ✅.
6. **No divide-by-zero.** Always offset typed-field denominators by `+ 0.0001`.
7. **Operators and fields must come from the catalog** in
   `knowledge/worldquant_iqc/brain_operators.md` and `data_fields.md`. No
   invented names.
8. **Fundamental fields require `ts_backfill(x, 120)`** — they are quarterly
   and cause >70% NaN coverage otherwise.

## Canonical Pipeline (always)

```
scale(
  group_neutralize(
    zscore(                          # cross-sectional (use zscore, not rank, for Fitness>1)
      ts_zscore(                     # time-series normalize, d in {20, 63, 252}
        winsorize(<your_signal>),    # 1 arg only
        d
      )
    ),
    subindustry
  )
)
```

## Diagnostic Playbook (apply during refine)

| Failure | Most-likely root cause | Targeted mutation |
|---|---|---|
| Sharpe < 1.25 | weak signal | shorten ts window 50%; add confirming factor (`* rank(volume / ts_mean(volume, 20))`) |
| Fitness < 1.0 | rank() compressed magnitude | swap rank → zscore at cross-sectional step; or shrink ts_zscore window (252→63) |
| Sub-Sharpe < 0.45 | industry beta | confirm `group_neutralize(..., subindustry)` is present; switch to universal field |
| Turnover > 70% | too jittery | wrap signal with `ts_decay_linear(x, 5)` or lengthen ts window |
| Turnover < 1% | over-smoothed | shorten ts window; remove decay |
| Unit warning | bare constant added to typed field | replace with ratio over `ts_mean(field, d)` |
| Self-corr fail | duplicate of prior alpha | combine with a different field family (price ↔ volume ↔ fundamental) |

## Pre-Output Checklist (required for every BRAIN expression)

Before emitting an expression, walk through:

1. Outermost call is `scale(...)`. ✓/✗
2. Inside `scale` is `group_neutralize(..., subindustry)` (or `industry`). ✓/✗
3. Cross-sectional step uses `zscore` (not `rank`) when Fitness must clear 1.0. ✓/✗
4. `winsorize` (if used) has exactly one argument. ✓/✗
5. No `field + integer` for typed fields (volume, close, vwap, cap, etc.). ✓/✗
6. Every divisor that could be zero has a `+ 0.0001` offset. ✓/✗
7. Every operator and field appears in the BRAIN catalog. ✓/✗
8. Expression is one nested line — no `=`, no semicolons, no Python. ✓/✗

If any check is ✗, repair the expression before emitting.
