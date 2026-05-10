# WorldQuant BRAIN — Regions, Universes, and Field Availability

Use this card to pick the right region + universe + neutralization
combination for a candidate before submission. Mismatches here are the
fastest way to fail the "Competitions match" gate (#5) or collapse the
Sub-universe Sharpe gate (#7).

## Regions

| Region | Description | Notable constraints |
|---|---|---|
| `USA` | US-listed equities, NYSE + NASDAQ | Largest field coverage. IQC 2026 Stage 1 default. |
| `GLB` / `Glb1` / `Glb3` | Global developed-market equities | Universal fields only (close, open, high, low, volume, vwap, returns, cap, adv20). Most fundamentals sparse. |
| `EUR` / `Eur1` | European-listed equities | UK + EU. FX-translated fields. Fundamentals less dense than USA. |
| `CHN` / `Chn1` | Chinese A-shares | Extremely region-specific. Different reporting standards. Use with care. |
| `ASI` / `Asi1` | Asia ex-Japan / Asia-Pacific | Mixed liquidity. Universal fields only. |
| `JPN` / `Jpn1` | Japan | Reasonably dense fundamentals. |

**Rule of thumb:** for any candidate that is not USA-only, restrict to the
universal price-volume fields and `ts_backfill` everything sparse.

## Universes (within USA)

| Universe | Members | When to use |
|---|---|---|
| `TOP3000` | 3000 most-liquid US stocks | DEFAULT for IQC 2026 Stage 1. Best liquidity-coverage tradeoff. |
| `TOP1000` | 1000 most-liquid US stocks | Higher-quality signals, less noise. Use when sub-universe Sharpe > 0.6 on TOP3000 — graduate up. |
| `TOP500`  | 500 most-liquid US stocks | Stricter still. Often used for low-turnover institutional-style alphas. |
| `TOPSP500` | S&P 500 universe | Best for fundamental signals where Compustat coverage is required. |
| `TOP200`  | 200 most-liquid | Very narrow; near-impossible to beat self-correlation gate here. |
| `TOPDIV3000` | TOP3000 with dividend filter | Dividend-aware strategies only. |
| `TOPVALUE` | Value-tilted subset | Pre-filtered by P/B etc — use for value sleeves. |

**Universe-pick heuristic:**

- New idea, unknown signal strength → `TOP3000` first.
- Sharpe survives but Sub-Sharpe < 0.45 → try `TOP1000` (less noise often clears Sub-Sharpe).
- Fundamental-heavy signal → `TOPSP500` (Compustat denser there).
- Turnover too high → narrower universe (TOP1000/500) — fewer thinly-traded names dampens churn.

## Neutralization Tiers

Neutralization is "subtract group mean before scale" — chosen separately from
the universe. Pick by group sparsity:

| Neutralization | Granularity | Use when |
|---|---|---|
| `subindustry` | ~158 buckets in TOP3000 | DEFAULT — clears Sub-universe Sharpe gate most reliably. |
| `industry` | ~25 buckets | When subindustry leaves <5 members in a group (rare in TOP3000, common in TOP500). |
| `sector` | ~11 buckets | Last resort if subindustry / industry both too sparse. |
| `market` | global | Almost never — kills cross-stock signal. |
| `none` | identity | Only for already-neutralized fields. |

**Always inside `scale(...)`**, never outside. The plugin validator warns if
`group_neutralize` is missing from the canonical pipeline.

## Field Availability Matrix

| Field group | USA TOP3000 | USA TOPSP500 | GLB | EUR | CHN |
|---|---|---|---|---|---|
| Price-volume + cap + adv20 | ✓ | ✓ | ✓ | ✓ | ✓ |
| `beta` | ✓ | ✓ | ✓ (vs region) | ✓ | ✓ |
| `equity`, `assets`, `revenues`, `ebitda` | ✓ | ✓ (densest) | sparse | ✓ | sparse |
| `fnd1`..`fnd28` (Compustat) | ✓ (sparse) | ✓ (densest) | ✗ mostly | partial | ✗ |
| IBES estimates | ✓ | ✓ | partial | partial | ✗ |
| Alternative data (news, sentiment) | varies | varies | ✗ | ✗ | ✗ |

## Region/Universe Selection Algorithm (apply at synthesize step)

```
if signal uses ONLY price/volume/returns/cap:
    region = USA, universe = TOP3000, neutralization = subindustry
elif signal uses Compustat fundamentals heavily:
    region = USA, universe = TOPSP500, neutralization = subindustry
    wrap every fundamental field with ts_backfill(x, 120)
elif signal must hold up globally:
    region = GLB,  universe = top liquidity bucket
    use ONLY universal fields (price, volume, returns, vwap, cap)
    neutralization = subindustry (if available) else industry
else:
    region = USA, universe = TOP3000, neutralization = subindustry  # safe default
```
