# WorldQuant BRAIN — Operator Notes

Original StratEngine notes for common BRAIN-style operators and expression
patterns. Verify exact availability and signatures in the BRAIN IDE before
submission.

## Cross-Sectional Operators (operate across all stocks at one time)

| Operator | Description |
|---|---|
| `rank(x)` | [0,1] rank across universe — most universality-friendly transform |
| `zscore(x)` | (x - mean) / std across universe |
| `zscore_scale(x)` | zscore then rescale to [-1, 1] |
| `scale(x)` | rescale so sum(|x|) == 1 — apply at output |
| `normalize(x)` | subtract universe mean |
| `winsorize(x)` | clip outliers — exactly 1 argument, no std parameter |
| `winsorize_scale(x)` | winsorize then scale |
| `normed_rank(x)` | rank normalized to [-1, 1] |
| `normed_rank_diff(x, y)` | normed_rank(x) - normed_rank(y) |
| `cwise_max(x, y)` | element-wise max across two fields |
| `cwise_min(x, y)` | element-wise min across two fields |
| `power(x, n)` | x^n, preserves sign |
| `signed_power(x, n)` | sign(x) * |x|^n — concave/convex transforms |
| `truncate(x, pct)` | winsorize at given percentile |
| `vector_neut(x)` | full vector neutralization |
| `quantile(x, q)` | map to quantile bucket |
| `bucket(x, range)` | convert to bucket index; range: "0,1,0.1" |
| `neutralize(x, g)` | subtract group mean; g = market, sector, industry, subindustry |
| `group_neutralize(x, g)` | alias for neutralize |

## Time-Series Operators (per-instrument rolling window)

| Operator | Description |
|---|---|
| `ts_mean(x, d)` | rolling mean, d-day window |
| `ts_median(x, d)` | rolling median |
| `ts_std_dev(x, d)` | rolling standard deviation |
| `ts_zscore(x, d)` | (x - ts_mean) / ts_std_dev over d days |
| `ts_zscore_scale(x, d)` | ts_zscore then scale to [-1,1] |
| `ts_maxmin_scale(x, d)` | (x - ts_min) / (ts_max - ts_min) over d days |
| `ts_rank(x, d)` | rank of today's x within last d values (0-1) |
| `ts_delta(x, d)` / `delta(x, d)` | x - ts_delay(x, d) |
| `ts_delta_ratio(x, d)` | (x - ts_delay(x,d)) / (ts_delay(x,d) + 0.0001) |
| `ts_delay(x, d)` / `shift(x, d)` | lag by d days |
| `ts_sum(x, d)` | rolling sum |
| `ts_product(x, d)` | rolling product |
| `ts_min(x, d)` | rolling minimum |
| `ts_max(x, d)` | rolling maximum |
| `ts_max_diff(x, d)` | ts_max(x,d) - x |
| `ts_min_diff(x, d)` | x - ts_min(x,d) |
| `ts_arg_max(x, d)` / `ts_argmax(x, d)` | days-ago index of max in window |
| `ts_arg_min(x, d)` / `ts_argmin(x, d)` | days-ago index of min in window |
| `ts_argmaxmin_diff(x, d)` | ts_argmax - ts_argmin |
| `ts_corr(x, y, d)` / `ts_cov(x, y, d)` | rolling Pearson correlation / covariance |
| `ts_regression(y, x, d)` | rolling OLS beta of y on x |
| `ts_linear_reg(x, d)` | linear regression slope of x over d days |
| `ts_decay_linear(x, d)` / `ts_decayed_linear(x, d)` | linearly-weighted avg (weight d → 1) |
| `ts_decay_exp_window(x, d)` | exponential decay weighting |
| `ts_ema(x, d)` | exponential moving average, span d |
| `ts_skew(x, d)` | rolling skewness |
| `ts_kurt(x, d)` | rolling kurtosis |
| `ts_percentile(x, q, d)` | rolling q-th percentile |
| `ts_backfill(x, d)` | forward-fill NaN up to d days |

## Group-Wise Operators

| Operator | Description |
|---|---|
| `grouped_demean(x, g)` | subtract group mean (same as group_neutralize) |
| `grouped_mean(x, g)` | mean within group |
| `grouped_std(x, g)` | std within group |
| `grouped_max(x, g)` / `grouped_min(x, g)` | max/min within group |
| `grouped_sum(x, g)` | sum within group |
| `grouped_zscore_scale(x, g)` | zscore_scale within group |
| `grouped_winsorize_scale(x, g, std)` | winsorize then scale within group |
| `group_rank(x, g)` | rank within group |
| `group_zscore(x, g)` | zscore within group |
| `group_scale(x, g)` | scale within group |
| `group_backfill(x, g, d)` | backfill within group |
| `group_vector_neut(x, g)` | vector neutralization within group |

## Element-Wise Operators

| Operator | Description |
|---|---|
| `abs(x)` | absolute value |
| `log(x)` | natural log (add offset: log(x + 1)) |
| `sqrt(x)` | square root |
| `neg(x)` / `-x` | negate |
| `relu(x)` | max(x, 0) — keep only positive signal |
| `sign(x)` | -1, 0, or +1 |
| `pow(x, n)` / `pow_sign(x, n)` | x^n / sign(x)*|x|^n |
| `round(x)` | round to nearest integer |
| `add(x, y)` | x + y |
| `minus(x, y)` | x - y |
| `cwise_mul(x, y)` | x * y |
| `div(x, y)` | x / y (always add offset to denominator) |
| `greater(x, y)` | 1 if x > y else 0 |
| `less(x, y)` | 1 if x < y else 0 |
| `if(cond, a, b)` | a where cond > 0, else b |
| `trade_when(cond, a, b)` | conditional trading signal |

## Vector / Risk-Factor Operators (advanced)

| Operator | Description |
|---|---|
| `vector_neut(a, b)` | Orthogonalize `a` against `b`: returns `a - (a·b̂)b̂`. Use to neutralize an alpha against a risk factor (e.g. cap, momentum). |
| `group_vector_neut(a, b, g)` | Same as `vector_neut(a, b)` but applied within group `g`. Standard tool in China universes. |
| `keep(x)` | Hold `x`'s value across days (combine with `trade_when` to lower turnover). |
| `vec_avg(x)` / `vec_sum(x)` / `vec_max(x)` / `vec_min(x)` | REQUIRED reduction over a vector-valued field (e.g. `nws*_*`, `scl*_*`, `*_vec`). Forgetting this fails compilation. |

## Specialty / Conditional Operators

| Operator | Description |
|---|---|
| `pasteurize(x)` | replace NaN with 0 — use sparingly; usually `ts_backfill` is safer |
| `densify(x)` | densify a sparse signal so more rows are non-NaN |
| `humpdecay(x, p)` / `hump(x, p)` | decay-style smoothing controlled by hump parameter p |
| `jump_decay(x, d, n)` | reset decay window when the signal jumps by > n stddevs |
| `last_diff_value(x, d)` | last value of x that changed within d days |
| `convert_unit(x, "rate")` | unit-convert (e.g. count → rate per share) |
| `ts_returns(x, d)` | simple return: (x - ts_delay(x,d)) / ts_delay(x,d) |
| `ts_step(d)` | linearly-increasing 1..d window (used for weighting) |
| `ts_partial_corr(y, x, z, d)` | partial correlation of y on x, controlling for z |
| `ts_kendall(x, y, d)` | rolling Kendall rank correlation |
| `ts_co_skewness(x, y, d)` / `ts_co_kurtosis(x, y, d)` | rolling co-moments |
| `ts_quantile(x, q, d)` | rolling q-th quantile (alias of ts_percentile) |
| `ts_av_diff(x, d)` | x minus rolling-average |
| `kth_element(x, k)` | k-th element of a vector field |
| `vec_avg(x)` / `vec_sum(x)` | aggregate over vector-valued data fields |
| `vec_max(x)` / `vec_min(x)` | element-wise max/min over a vector field |
| `if_else(cond, a, b)` | alias of if(cond, a, b) |
| `nan_mask(x, y)` | NaN-mask x where y is NaN |

## Common Data Fields

| Field | Description |
|---|---|
| `close` | adjusted close price |
| `open`, `high`, `low` | OHLC |
| `volume` | shares traded |
| `vwap` | volume-weighted average price |
| `returns` | daily total return (adj for dividends/splits) |
| `cap` | market capitalization |
| `adv20` | 20-day avg daily dollar volume |
| `beta` | market beta |
| `fnd13` | book value per share |
| `fnd1`…`fndN` | Compustat fundamentals (revenues, earnings, debt, etc.) |
| `equity`, `debt`, `ebitda` | balance sheet items |
| `revenues`, `sales`, `operating_income` | income statement items |
| `assets`, `retained_earnings`, `inventory` | additional balance sheet |
| `enterprise_value`, `sharesout` | market structure |

## Canonical Alpha Pipeline

```
raw_signal
  → winsorize(x, 4)                    # 1. clip outliers
  → ts_zscore(x, d)  OR  ts_rank(x, d) # 2. time-series normalize
  → rank(x)  OR  zscore(x)             # 3. cross-sectional normalize
  → group_neutralize(x, subindustry)   # 4. remove sector beta
  → scale(x)                           # 5. sum(|w|) == 1 for submission
```

Always apply all five steps. Skipping neutralization or scale causes universality failure.

## Output Requirements

1. End with `scale(...)` so weights sum to 1 in absolute value.
2. Be `group_neutralize`d before scaling.
3. No division by zero — always add small constant (`+ 0.0001`).
4. Produce valid (non-NaN) values for ≥70% of the universe on any given day.
5. Turnover 1–70%. Below 1% = inactive; above 70% = excessive transaction costs. (See `wq_standard.md` for the canonical IQC 2026 gate.)

## Quick Reference: Common Combinations

```
# Relative volume
rel_vol = volume / (ts_mean(volume, 20) + 1)

# Overnight gap reversal
gap = (open - ts_delay(close, 1)) / (ts_delay(close, 1) + 0.01)
alpha = -rank(gap)

# ATR-normalized momentum
atr = ts_mean(high - low, 14)
mom = (close - ts_delay(close, 20)) / (atr + 0.01)
alpha = scale(group_neutralize(rank(mom), subindustry))

# Price-to-book value factor
ptb = cap / (fnd13 * cap + 1)
alpha = scale(group_neutralize(-rank(ptb), sector))
```
