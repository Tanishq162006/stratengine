# WorldQuant BRAIN — Working Alphas from the WQ Seminar (study reference)

> **Don't copy these — learn from them.** Each alpha is an instance of
> a technique catalogued in `alpha_techniques.md`. The reported metrics
> are useful as a sanity check that the technique works, not as a
> guarantee that the literal expression will pass self-correlation if
> you submit it.

Distilled from public seminar notes (jglazar/notes, quant_interview/worldquant_seminar.md).
Every alpha here was reported with concrete BRAIN simulation results. Use as
seed candidates for the synth step and as proof-by-example for the
canonical pipeline + operator usage.

Reported figures are platform-validated, not local heuristics.

## Price-Volume Alphas

### PV-1 · Volatility-Conditional Reversal Regression
```
trade_when(
  ts_rank(ts_std_dev(returns, 22), 252) > 0.55,
  -ts_regression(returns, ts_delay(returns, 1), 252),
  -1
)
```
Trade the regression-residual reversion only when realized vol is in the
top 45% of its 1y range; otherwise hold yesterday's position (`-1`).
**Why it works**: reversion dominates in high-volatility regimes; the
trade_when wrapper also keeps turnover sane.

### PV-2 · Candlestick Reversal, Subindustry-Neutral
```
group_zscore(-(close - open) / (high - low), subindustry)
```
Buy stocks that closed below open, scaled by the day's range. Simple,
robust, and good cross-sector neutralization.

### PV-3 · VWAP Reversion
```
group_rank(ts_zscore(vwap / close, 250), subindustry)
```
Closing far from the time-averaged VWAP signals positioning to revert.
Group-rank by subindustry to remove sector beta.

### PV-4 · Reversion-to-Weekly-Mean
```
rank(-(close - ts_mean(close, 5)))
```
Wrap the absolute difference in `rank(...)` to fix scale-bias from
high-priced stocks. Long-short neutralized by rank itself.

### PV-5 · Volume × Volatility Composite (Delay 0)
```
zscore(vwap / close) * (1 - rank(high / low))
```
Settings: market-neutralization, truncation 0.01, decay 15, TOP1000, **delay 0**.
Combine VWAP reversion with intraday-range filter. Liquid universe is key.

### PV-6 · Volume-VWAP Anti-Correlation (China)
```
-ts_corr(ts_rank(volume, 10), ts_rank(vwap, 10), 20)
```
Settings: subindustry-neutralization, truncation 0.1, decay 3, TOP3000 China, delay 0.
Negative correlation between volume rank and VWAP rank predicts
short-term reversion.

### PV-7 · Volume-Spike Activated Trend-Reversal (China)
```
trade_when(
  ts_arg_max(volume, 5) == 0,
  -rank(ts_delta(close, 3)),
  -1
)
```
Settings: subindustry-neutralization, truncation 0.1, decay 3, TOP3000 China, delay 1.
Activate the 3-day reversal only on days where today is the 5-day
volume max.

## Fundamental & Model-Data Alphas

### FUND-1 · Book/Market via equity/cap (≈ 1.6 Sharpe, 0.87 fitness, 25% turnover)
```
ts_rank(equity / cap, 20)
```
Settings: TOP3000, neutralization industry, decay 5, truncation 0.1.

### FUND-2 · Short Rising Valuation (≈ 1.7 Sharpe, 1.08 fitness, 15% turnover)
```
-ts_zscore(enterprise_value / ebitda, 63)
```
Settings: TOP3000, neutralization industry, decay 5, truncation 0.01.

### FUND-3 · Long Increasing Operating-Earnings Yield (≈ 1.9 Sharpe, 1.14 fitness)
```
ts_rank(mdf_oey, 250)
```
Settings: TOP3000, neutralization industry, decay 0, truncation 0.01.
`mdf_oey` is a Model-Data Fundamental (proprietary BRAIN field).

### FUND-4 · Growth Rate × Dividend Yield (≈ 1.9 Sharpe, 0.86 fitness, 33% turnover)
```
group_zscore(ts_zscore(mdf_gry, 20), sector)
```
Settings: TOP3000, neutralization industry, decay 0, truncation 0.1.
**Tip**: lower turnover further by raising decay.

### FUND-5 · Net Profit Smoothness Average-Diff
```
ts_av_diff(mdf_nps, 500)
```
Settings: TOP3000, neutralization market or subindustry, decay 0,
truncation 0.08, delay 1. Useful baseline for "same idea, different
neutralization" sweeps.

### FUND-6 · Retained Earnings per Share Growth (China)
```
rank(ts_delta(retained_earnings / sharesout, 90))
```
Settings: subindustry-neutralization, truncation 0.01, decay 5, TOP3000 China, delay 1.
Lower the days in `ts_delta` to push turnover up.

### FUND-7 · Price-to-Book Mean Reversion w/ News Filter
```
rank(-(mdf_pbk - ts_max(mdf_pbk, 10)))
```
Settings: subindustry-neutralization, truncation 0.01, decay 3, TOP3000.
Improvement: combine with after-hours news vector signal:
```
rank(ts_sum(vec_avg(nws12_afterhsz_s1), 60)) > 0.5 ? 1 : <above>
```
Then group_neutralize against PV13 model-grouping for further uplift:
```
group_neutralize(<above>, densify(pv13_r2_min20_3000_sector))
```

## News & Sentiment Alphas

### NEWS-1 · After-Hours News Sentiment with Daily Reversion
```
rank(ts_sum(vec_avg(nws12_afterhsz_sl), 60)) > 0.5 ?
  1 :
  rank(-ts_delta(close, 2)) * 1
```
Settings: TOP3000, subindustry-neutralization, decay 3, truncation 0.01.
Vector-data fields require `vec_avg` (or `vec_sum`) before scalar ops.

### NEWS-2 · After-Hours News Max-Up Amount, Momentum-Neutral
```
ts_backfill(-vec_avg(nws12_afterhsz_maxupamt), 20)
```
Settings: TOP1000, neutralization industry, decay 10, truncation 0.01.
Improvement: orthogonalize to 250d momentum and densify-group by industry-exchange:
```
neut_a = vector_neut(<above>, ts_mean(returns, 250));
decay_a = ts_decay_exp_window(neut_a, 20, factor=0.4);
group_neutralize(decay_a, densify((industry+1)*10 + exchange))
```

### SENT-1 · Sentiment Buzz-Return Reversion
```
-ts_regression(returns, ts_delay(snt_buzz_ret, 1), 120)
```
Settings: TOP3000, subindustry-neutralization, decay 15, max weight 0.1.
`snt_buzz_ret` predicts returns from buzz magnitude.

### SENT-2 · Social-Buzz Vector Average-Diff
```
buzz = ts_backfill(-vec_sum(scl12_alltype_buzzvec), 20);
ts_av_diff(buzz, 60)
```
Settings: TOP3000, neutralization industry or subindustry, decay 15,
truncation 0.08.

## Options Alphas

### OPT-1 · Call/Put Implied-Vol Skew (Delay 0)
```
zscore(implied_volatility_call_720 - implied_volatility_put_720)
```
Settings: market-neutralization, truncation 0.01, decay 3, TOP3000, delay 0.
Improve by adding historical volatility, trading volume, open interest filters.

### OPT-2 · Call Breakeven Distance, Activated by PCR Volume
```
a = ts_delay(call_breakeven_10, 7) / close;
trade_when(ts_arg_max(pcr_vol_10, 7) < 1, a, -1)
```
Settings: industry-neutralization, truncation 0.03, decay 0, TOP3000.
`pcr_vol_10` = 10d put/call volume ratio.

### OPT-3 · Rising Call IV vs Cap-Vector-Neutralized
```
a = ts_decay_linear(ts_delta(implied_volatility_call_60, 25) > 0, 20);
vector_neut(a, cap)
```
Settings: subindustry-neutralization, truncation 0.03, decay 0, TOP3000.
Backed by SSRN paper 2008902 (high call-IV growth → higher returns).

## China-Specific Alphas

### CHN-1 · Volatility-Penalized Volume × Revenue Composite
```
rank(-mdl175_volatility * log(volume))
  * (1 + group_rank(mdl175_revenuettm, sector))
```
Settings: market-neutralization, truncation 0.1, decay 3, TOP3000 China.
Improvement (vector-neut against AMVT mean):
```
group_vector_neut(<above>, ts_mean(mdl175_02amvt, 240), sector)
```

## Geometric-Mean Composite

### COMP-1 · Geometric-Return vs Arithmetic-Return Spread, Vol-Activated
```
avg_ret  = power(ts_product(returns + 1, 5), 1/5);
comp_avg = power(ts_product(rel_ret_comp + 1, 5), 1/5);
a    = zscore(comp_avg / avg_ret);
when = ts_rank(ts_std_dev(returns, 60), 126) > 0.55;
trade_when(when, a, -1)
```
Settings: subindustry-neutralization, truncation 0.01, decay 3, TOP3000.
**Tip**: geometric mean is more stable for return-series than arithmetic
mean. Numerically: `exp((1/N) * sum(log(x)))`. Improve further by
neutralizing against 120d momentum: `vector_neut(<above>, ts_mean(returns, 120))`.

---

## Operator + Setting Conventions Established by the Seminar

- **Default truncation = 0.01 to 0.08**, with `0.01` recommended when
  combined with `rank(...)` (rank prevents overweight). Use 0.1 only
  when subindustries are too sparse to host enough breadth.
- **Default decay = 3-5** for most price-volume alphas; 10-15 for news/sentiment.
- **Default neutralization = subindustry**; industry for narrower universes; market for cross-sector composites.
- **`trade_when(cond, alpha, -1)`** holds yesterday's position when `cond`
  is false. Standard threshold for vol-conditional activation:
  `ts_rank(ts_std_dev(returns, 22), 252) > 0.55`.
  Rationale: empirical decomposition of returns is roughly 50% reversion,
  10% momentum, 40% random — the 0.55 threshold catches the volatile
  reversion regime.
- **Same idea, different field**: rotate the same operator structure
  across `equity/cap`, `operating_income/cap`, `mdf_oey`, etc.
- **Same idea, different operator**: try `ts_rank` ↔ `ts_quantile` ↔
  `ts_zscore`. Stack `group_rank` before `ts_rank`.
- **China**: prefer `group_rank` over `rank`; prefer
  `group_vector_neut` over `vector_neut`. Beware the 10% daily price
  limit — design exits when stocks hit limits.
- **News/options at delay 0**: news is released pre-trading or
  post-trading; the price jump shows up in main session — delay 0
  captures it. Liquid universe (TOP1000) compensates for delay-0 noise.
- **Vector data fields** (`nws*_*`, `scl*_*`, `*_vec`) MUST be reduced
  with `vec_avg`, `vec_sum`, `vec_max`, or `vec_min` before any scalar
  operator. Otherwise the expression fails to compile.

## Reference Reading (cite in synth prompt)

- "101 Formulaic Alphas" — Kakushadze, Wilmott Magazine
- SSRN 2008902 — Implied-vol changes predict returns
- SSRN 3090626 — Firm fundamentals explaining stock returns
- SSRN 342581 — Earnings and price momentum
- BRAIN forum posts: "Seven Tips for Creating Delay 0 Alphas",
  "6 ways to evaluate a dataset"
