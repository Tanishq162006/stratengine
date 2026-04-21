# WorldQuant IQC — BRAIN Operator Reference

## Cross-sectional operators

| Operator | Effect |
|---|---|
| `rank(x)` | [0,1] rank across universe — most universality-friendly transform |
| `zscore(x)` | (x - mean) / std across universe — preserves relative magnitude |
| `scale(x)` | rescale so sum(|x|) == 1 — required at output stage |
| `neutralize(x, group)` | subtract group mean (groups: market, sector, industry, subindustry) |
| `group_neutralize(x, g)` | alias for `neutralize` with group label |
| `winsorize(x, std=4)` | clip outliers at ±4 sigma — always apply before regression inputs |
| `power(x, n)` | x^n, preserves sign |
| `signed_power(x, n)` | sign(x) * |x|^n — useful for concave/convex transforms |
| `truncate(x, pct)` | winsorize at percentile (alternative to std-based winsorize) |

## Time-series operators

| Operator | Description |
|---|---|
| `ts_mean(x, d)` | rolling mean, d-day window |
| `ts_std_dev(x, d)` | rolling std |
| `ts_rank(x, d)` | rolling rank (position of today's x in last d values) |
| `ts_arg_max(x, d)` | number of days ago the max occurred |
| `ts_arg_min(x, d)` | number of days ago the min occurred |
| `ts_corr(x, y, d)` | rolling pairwise correlation |
| `ts_covariance(x, y, d)` | rolling covariance |
| `ts_regression(y, x, d)` | rolling OLS beta of y on x |
| `ts_decay_linear(x, d)` | linearly-weighted average (most recent = weight d, oldest = 1) |
| `delta(x, d)` | x - ts_delay(x, d) |
| `ts_delay(x, d)` | lag by d days |
| `ts_backfill(x, d)` | forward-fill NaN, up to d days |
| `ts_min(x, d)` / `ts_max(x, d)` | rolling min/max |
| `ts_sum(x, d)` | rolling sum |
| `ts_product(x, d)` | rolling product |

## Common fields

| Field | Description |
|---|---|
| `close` | adjusted close price |
| `open`, `high`, `low` | OHLC |
| `volume` | shares traded |
| `vwap` | volume-weighted average price |
| `returns` | daily total return (close-to-close, adj for dividends/splits) |
| `cap` | market capitalization |
| `adv20` | 20-day average daily dollar volume |
| `fnd13` | book value per share |
| `fnd1` … `fndN` | broad range of Compustat fundamentals |

## Combinations to know

```
# Relative volume (how much busier today vs normal)
rel_vol = volume / (ts_mean(volume, 20) + 1)

# Price-to-book cross-sectional rank
ptb = cap / (fnd13 * cap + 1)
alpha = -rank(ptb)   # value: prefer low P/B

# Earnings yield (inverse PE proxy)
ey = fnd13 / (close + 1)
alpha = rank(ey)

# Overnight gap (open vs prior close) — captures news reaction
gap = (open - ts_delay(close, 1)) / (ts_delay(close, 1) + 0.01)
alpha = -rank(gap)   # reversal: big gaps mean-revert

# ATR-normalized momentum
atr = ts_mean(high - low, 14)
mom = (close - ts_delay(close, 20)) / (atr + 0.01)
alpha = rank(mom)
```

## Output requirements

Final alpha expression MUST:
1. End with `scale(...)` so weights sum to 1 in absolute value.
2. Be group-neutralized before scaling.
3. Not contain division by zero (always add small constant: `+ 0.0001`).
4. Produce valid (non-NaN) values for ≥70% of the universe on any given day.
