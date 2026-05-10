# WorldQuant BRAIN — Neutralization Choice by Dataset

Picking the right `neutralization` setting is one of the cheapest ways to
move Sharpe and Fitness. This card is the per-data-family lookup. Use it
during synth and refine.

## Lookup Table

| Data family | Default neutralization | Why |
|---|---|---|
| Fundamentals (`equity`, `ebitda`, `assets`, `mdf_*`, …) | **industry** | Fundamental ratios behave differently across industries; same-industry comparison is the meaningful baseline. |
| Analyst data (`est_eps`, `target_price`, revisions, `fam_est_eps_rank`) | **industry** | Estimates project fundamentals — same neutralization logic applies. |
| Model datasets (`mdf_*`, `mdl*_*`) | **try multiple** | Behaviour is model-specific; sweep across subindustry / industry / sector / market. |
| News (`nws*_*`) | **subindustry** | News impacts companies differently within a subindustry. |
| Options (IV, breakeven, PCR) | **market or sector** | Implied-vol effects are broadly consistent across industries — neutralize wider. |
| Price-volume (returns, close, vwap, volume, etc.) | **market or none** | Reversion / momentum signals can be hurt by industry-neutralization; market-neutralization or none often beats subindustry on PV alphas. |
| Social media (`scl*_*`) | **subindustry or industry** | Social-media impact is company-dependent. |
| Sentiment (`snt_*`) | **industry or subindustry** | Sentiment impact is company-dependent. |
| Institutional / 13-F | **sector or industry** | Holder behaviour clusters by sector. |
| Short interest | **industry** (then experiment) | Short interest baselines differ by industry. |
| Insider trading | **industry or subindustry** | Per-company event with sector-relative signal. |
| Earnings data | **industry** | Fundamental cousin. |
| Sector / market / macro events | **macro groups (NOT subindustry)** | The signal IS the macro factor; neutralizing by subindustry destroys it. |

## Quick Heuristics

- **Big universe → small group, small universe → big group.**
  - TOP3000 → `subindustry` (fine grouping has enough members per bucket).
  - TOP500 → `industry` (subindustry leaves <5 names per bucket → noisy mean).
  - TOP200 / region universes → `sector` or `market`.

- **Pure price-reversion**: try **no neutralization first**. Long-or-short
  the whole market often outperforms subindustry-neutralized variants on
  fitness (less so on Sharpe — pick by goal).

- **Group neutralize via `densify`** when combining multiple group keys:
  `group_neutralize(x, densify((industry+1)*10 + exchange))`. This builds
  custom finer groupings without sparsity issues.

- **Pasteurization** auto-removes non-universe stocks before scoring. Only
  manual `pasteurize(...)` matters when:
  - Using group operators (`group_rank`, `group_mean`, …) AND
  - Universe is small (TOP200 / region) where in-universe member counts
    drop sharply.

## Synthesizer Recipe

When proposing the synth-step config block:

1. Read the candidate's `fields_used`.
2. Look up the dominant family (highest count).
3. Set `neutralization` from the table above.
4. Set `universe` based on field availability (Compustat-heavy → TOPSP500;
   price-volume only → TOP3000; multi-region → GLB1).
5. Justify in `config_reason` with one phrase from this card.
