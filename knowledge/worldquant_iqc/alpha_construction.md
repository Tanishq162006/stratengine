# WorldQuant IQC — Alpha Construction Patterns

## The canonical alpha pipeline

```
raw_signal → time_series_smooth → cross_sectional_rank → neutralize → scale → submit
```

Every step matters. Skipping neutralization or scale kills universality scores.

## Short-term reversal (baseline)

```
# Classic 5-day reversal — works in most regions, all universes
alpha = -rank(ts_mean(returns, 5))
alpha = group_neutralize(alpha, subindustry)
alpha = scale(alpha)
```

**Why it works:** institutional rebalancing and liquidity provision create short-term price pressure
that reverts within 1-2 weeks.

## Momentum with volatility tilt

```
# 3-month momentum minus 1-week (avoid short-term reversal overlap)
mom   = ts_mean(returns, 63) - ts_mean(returns, 5)
# Prefer low-vol names (more stable momentum)
stab  = 1 / (ts_std_dev(returns, 20) + 0.0001)
alpha = rank(mom) * rank(stab)
alpha = group_neutralize(alpha, subindustry)
alpha = scale(alpha)
```

## Quality factor (fundamental-based)

```
# Book-to-market tilt toward value
btm   = fnd13 / (cap + 1)          # fnd13 = book value
alpha = rank(btm)
alpha = group_neutralize(alpha, sector)
alpha = scale(alpha)
```

## Combining two alphas (alpha blending)

```
# Rank-average of reversal and momentum — reduces correlation, improves Sharpe
rev  = -rank(ts_mean(returns, 5))
mom  = rank(ts_mean(returns, 63) - ts_mean(returns, 5))
alpha = rank(0.5 * rev + 0.5 * mom)
alpha = group_neutralize(alpha, subindustry)
alpha = scale(alpha)
```

## Volatility targeting

```
# Vol-scale to equalize contribution across instruments
vol_20 = ts_std_dev(returns, 20) + 0.0001
alpha  = rank(ts_mean(returns, 5)) / vol_20
alpha  = group_neutralize(alpha, subindustry)
alpha  = scale(alpha)
```

## Turnover management

BRAIN flags alphas with:
- Turnover < 3% (too static — effectively a buy-and-hold)
- Turnover > 60% (too costly — fees eat alpha)

To reduce turnover: increase smoothing window (`ts_mean(x, 10)` vs `ts_mean(x, 2)`).
To increase turnover: use `delta(x, 1)` (1-day change) instead of level.

## Avoiding look-ahead bias

- Never use `close` of day D to predict `returns` of day D — use `ts_delay(close, 1)`.
- Fundamental data: use `ts_delay(fnd13, 1)` to prevent same-day use of reported figures.
- Earnings dates: if a field updates on announcement day, delay by 1-2 days.

## Handling sparse fields

```
# ts_backfill fills forward up to d days; prevents NaN cascade
fnd_filled = ts_backfill(fnd13, 60)
alpha = rank(fnd_filled / (cap + 1))
```

## Universality recipe

A universally-passing alpha:
1. Uses `rank()` or `zscore()` cross-sectionally (not raw price levels).
2. Is neutralized by `subindustry` (or `industry` if subindustry is unavailable).
3. Has turnover 5-40%.
4. Works in at least 3 regions (USA, Europe, Asia).
5. Has positive OOS (out-of-sample) Sharpe and IR — BRAIN splits IS/OOS automatically.
