# WorldQuant BRAIN — Simulation Settings (decay, delay, truncation, neutralization)

Settings the BRAIN simulator applies on top of the alpha expression. The
right combination is candidate-specific and directly drives whether the 8
gates pass. Pair this with `regions_and_universes.md` and `wq_standard.md`.

## Decay (smoothing weight on signal history)

Decay is how many days of past signal are blended into today's position.
0 = use today's signal only; higher = smoother positions.

| Decay | Effect on turnover | When to use |
|---|---|---|
| 0   | highest turnover | Strong, low-noise signals only — rare to clear all gates. |
| 1-3 | high turnover | Short-horizon reversal alphas (1-5d holding). |
| 4-6 | DEFAULT — balanced | Most price-volume alphas. Start here. |
| 8-12 | lower turnover | Medium-horizon momentum / fundamental signals. |
| 20-32 | low turnover | Slow factor sleeves, value, quality. |
| 64-128 | very low turnover | Fundamental-only alphas, multi-month holds. |
| 256-512 | near-static | Quasi-buy-and-hold; rarely passes Turnover>1% gate. |

**Decay-tuning loop:** if turnover too high → raise decay; if too low →
lower decay. Decay is the cheapest control variable — change it before
mutating the expression itself.

## Delay (lag between signal and position)

| Delay | Meaning | When to use |
|---|---|---|
| 0 | trade on signal day | Backtests look great but unrealistic — use only if signal uses prior-day data internally (`ts_delay(returns, 1)` etc.). Self-corr gate often stricter. |
| 1 | DEFAULT — trade next day on close | Standard. Required for most IQC submissions. |
| 2+ | trade after extra delay | Slower information signals (analyst revisions, earnings). |

**Always use delay=1** unless you have a specific reason. Delay=0 alphas
are flagged for self-correlation and look-ahead more aggressively.

## Truncation (max single-stock weight cap)

Truncation caps `|w_i|` so no single stock dominates the book.

| Truncation | Meaning | When to use |
|---|---|---|
| 0.005 | 0.5% per stock | Most concentrated allowed; rare. |
| 0.01  | 1% per stock | Tight. Use for narrow universes (TOP500). |
| 0.05  | 5% per stock | Moderate. |
| 0.08  | DEFAULT | Common IQC default for TOP3000. |
| 0.10  | 10% per stock | Loose. Use only for narrow universes where 158 subindustries can't host enough breadth. |

If "Weight well distributed" gate (#4) fails, **lower** truncation (e.g.
0.08 → 0.05). If single-stock weights are vanishing, raise it.

## Neutralization

(See `regions_and_universes.md`.) Default `subindustry`. If the simulator
warns "subindustry too sparse," step up to `industry`.

## Pasteurization (NaN handling)

| Setting | Behavior |
|---|---|
| `ON` (default) | Replace NaN with 0 before scoring. |
| `OFF` | NaN propagates — useful only for diagnostic runs. |

Keep `ON` for submission. The expression-level `ts_backfill` is still
required for sparse fields — pasteurization is a coarse safety net only.

## Recommended Defaults by Signal Family

| Family | Universe | Decay | Delay | Truncation | Neutralization |
|---|---|---|---|---|---|
| Short-term reversal (1-5d) | TOP3000 | 3-5 | 1 | 0.08 | subindustry |
| Volume-confirmed reversal | TOP3000 | 4-6 | 1 | 0.08 | subindustry |
| Cross-sectional momentum | TOP3000 | 8-12 | 1 | 0.08 | subindustry |
| Volatility-adjusted momentum | TOP3000 | 6-10 | 1 | 0.08 | subindustry |
| Fundamental value | TOPSP500 | 32-64 | 1 | 0.05 | subindustry |
| Quality | TOPSP500 | 32-64 | 1 | 0.05 | subindustry |
| Earnings revision | TOPSP500 | 8-12 | 1 | 0.05 | subindustry |
| Liquidity-driven | TOP1000 | 6-10 | 1 | 0.08 | subindustry |
| Global universal | GLB1 | 6-10 | 1 | 0.10 | subindustry → industry |

## Self-Correlation Mitigation

The "Self-correlation < 0.7" gate (#8) compares to your prior submitted
alphas. If a candidate is too similar to something you've already submitted:

1. Swap the field family (price-volume → fundamental, or vice versa).
2. Change neutralization tier (subindustry → industry).
3. Switch decay window family (short ↔ long).
4. Add a confirming factor from a different domain (volume × return → 
   add `* sign(operating_income)` etc.).

Bumping decay alone almost never clears self-corr — the underlying signal
shape stays the same.

## Submission Config JSON (used by code_brain.txt output)

```
{
  "decay": 4,
  "delay": 1,
  "truncation": 0.08,
  "neutralization": "subindustry",
  "universe": "TOP3000",
  "region": "USA",
  "pasteurization": "ON",
  "config_reason": "<short why>"
}
```
