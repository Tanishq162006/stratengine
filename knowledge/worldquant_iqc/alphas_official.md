# WorldQuant BRAIN — Official Alpha Catalog

Three blocks of expressions surfaced in WQ-published material:

1. **Listed alphas** (37 simple expressions on the WQ site)
2. **Beginner alphas** (19 examples with full settings + improvement hints)
3. **Video / email alphas** (15 fundamental + sentiment ideas)

Use as seed candidates and as proof-by-example for operator usage.

---

## Listed Alphas (WorldQuant site — pseudo-code form)

| # | Expression |
|---|---|
| 1 | `1/close` |
| 2 | `volume / adv20` |
| 3 | `ts_corr(close, open, 10)` |
| 4 | `open` |
| 5 | `(high + low)/2 - close` |
| 6 | `vwap < close ? high : low` |
| 7 | `Rank(adv20)` |
| 8 | `Min(0.5*(open+close), vwap)` |
| 9 | `Max(0.5*(high+low), vwap)` |
| 10 | `1 / ts_stddev(returns, 22)` |
| 11 | `ts_sum(sharesout, 5)` |
| 12 | `ts_covariance(vwap, returns, 22)` |
| 13 | `1 / Abs(0.5*(open+close) - vwap)` |
| 14 | `ts_corr(vwap, ts_delay(close, 1), 5)` |
| 15 | `ts_delta(close, 5)` |
| 16 | `ts_decay_linear(sharesout * vwap, 5)` |
| 17 | `ts_decay_exp_window(close, 5, factor=0.25)` |
| 18 | `ts_product(volume / sharesout, 5)` |
| 19 | `Tail(close / vwap, lower=0.9, upper=1.1, newval=1.0)` |
| 20 | `Sign(close - vwap)` |
| 21 | `SignedPower(close - open, 0.5)` |
| 22 | `Pasteurize(1 / (close - open))` |
| 23 | `Log(high / low)` |
| 24 | `group_neutralize(volume * vwap, market)` |
| 25 | `Scale(close^0.5)` |
| 26 | `Ts_Min(open, 22)` |
| 27 | `Ts_Max(close, 22)` |
| 28 | `Ts_Rank(volume, 22)` |
| 29 | `Ts_Skewness(returns, 11)` |
| 30 | `Ts_Kurtosis(returns, 11)` |
| 31 | `Ts_Moment(returns, 11, k=3)` |
| 32 | `ts_count_nans((close - open)^0.5, 22)` |
| 33 | `ts_corr(close, ts_step(1), 5)` |
| 34 | `Last_Diff_Value(sales, lookback=125)` |
| 35 | `group_rank(returns, industry)` |
| 36 | `group_mean(returns, volume, subindustry)` |
| 37 | `Ts_Regression(close, open, 20, lag=0, rettype=2)` |

The strongest bare-bones picks: **#5, #10 (negated), #15 (negated), #20 (negated), #32, #34 (negated)**.

### Other site/email/video ideas

- `rank(sales / assets)`, subindustry-neutral, TOP3000 — efficiency-of-revenue.
- `rank(-ts_delta(debt, 90))`, sector-neutral, TOP3000 — decreasing leverage.
- `-ts_delta(close, 1)` — daily reversion baseline.
- `-rank(ts_delta(close, 2)) * rank(volume / ts_sum(volume, 30) / 30)` —
  reversion gated by volume spike.

---

## Beginner Alphas (WQ-published — settings provided)

### B1 · Mean-reversion vs returns sign
```
signal = abs(ts_mean(close, 20) / ts_mean(close, 60) - 1);
-signal * sign(returns)
```
Settings: TOP3000, decay 5, neutralization market.
Improvement: wrap with `trade_when` to lower turnover.

### B2 · Rank model-data revenue/sales
```
rank(mdf_rds)
```
Settings: TOP3000, decay 0, neutralization sector. Try multiple groups.

### B3 · ROE rank × Asset turnover
```
fam_roe_rank * rank(sales / assets)
```
Settings: TOP3000, decay 0, neutralization industry. Try multiple groups.

### B4 · Average-diff price-to-EBIT, group-ranked, vector-neutralized to IR
```
-group_rank(ts_av_diff(mdf_pec, 480), subindustry)
```
Settings: TOP3000, decay 0, neutralization none.
Improvement: `vector_neut(x, ts_ir(x, 250))` — orthogonalize to one-year IR.

### B5 · Social-buzz sentiment composite (TOP200)
```
sum_vol      = ts_sum(vec_sum(scl12_alltype_buzzvec), 5);
significance = vec_norm(scl12_alltype_sentvec) / vec_count(scl12_alltype_sentvec);
sent_vol     = -ts_rank(sum_vol, 60);
sent_sig     = ts_max(significance, 10);
sent_vol * group_rank(sent_sig, sector)
```
Settings: TOP200, decay 0, neutralization none.
Note: scl/snt vector fields require `vec_*` reductions before scalar ops.

### B6 · IR of cashflow/short-debt
```
zscore(ts_ir(cashflow_op / debt_st, 1250))
```
Settings: TOP3000, decay 10, neutralization subindustry.
Improvement: filter to companies with positive cashflow from ops.

### B7 · Net-profit smoothness average-diff
```
ts_av_diff(mdf_nps, 500)
```
Settings: TOP3000, decay 5, neutralization market.
Try: subindustry / industry / sector to find optimum.

### B8 · Put-call open-interest ratio
```
pcr_oi_all
```
Settings: TOP200, decay 5, neutralization market.
Improvement: weight by trailing average volume; rotate universe.

### B9 · Earnings growth × Sales-growth correlation
```
ts_av_diff(mdf_eg3, 250) * ts_corr(mdf_eg3, mdf_sg3, 250)
```
Settings: TOP200, decay 0, neutralization subindustry.
Improvement: lengthen lookback.

### B10 · Realised vs CAPM-expected return spread
```
market_ret      = ts_product(1 + group_mean(returns, 1, market), 250) - 1;
rfr             = vec_avg(fnd6_newqeventv110_optrfrq);
expected_return = rfr + beta_last_360_days_spy * (market_ret - rfr);
actual_return   = ts_product(returns + 1, 250) - 1;
actual_return - expected_return
```
Settings: TOP1000, decay 5, neutralization subindustry.

### B11 · Family-aggregated EPS estimate rank
```
group_rank(fam_est_eps_rank, sector)
```
Settings: TOP3000, decay 0, neutralization subindustry. Try other groups.

### B12 · Negative average-diff price-to-book, group-ranked
```
-group_rank(ts_av_diff(mdf_pbk, 5), subindustry)
```
Settings: TOP3000, decay 20, neutralization market.
Improvements: build custom subgroups with `bucket(rank(mdf_pbk), "0,1,0.1")`;
try `group_normalize`.

### B13 · Earnings-surprise reversion gate
```
trade_when(
  days_from_last_change(fam_earn_surp_pct) == 0,
  fam_earn_surp_pct * -returns,
  -1
)
```
Settings: TOP3000, decay 0, neutralization market. Try smoothing.

### B14 · Liquidity ratio z-score
```
zscore(cash_st / debt_st)
```
Settings: TOP500, decay 0, neutralization subindustry.
Improvement: compare against industry peers, not market.

### B15 · News-event volatility decay
```
percent = ts_rank(vec_stddev(nws12_prez_result2), 50);
-ts_rank(ts_decay_linear(percent, 150), 50)
```
Settings: TOP3000, decay 20, neutralization market.
Improvement: `trade_when` to lower turnover.

### B16 · EBIT-to-CapEx
```
-rank(ebit / capex)
```
Settings: TOP3000, decay 0, neutralization sector. Try other groups.

### B17 · Negative ts-rank of retained earnings
```
-ts_rank(retained_earnings, 250)
```
Settings: TOP3000, decay 10, neutralization sector.

### B18 · Sentiment-spike gated reversal
```
sent_vol = vec_sum(scl12_alltype_buzzvec);
trade_when(rank(sent_vol) > 0.95, -zscore(scl12_buzz) * sent_vol, -1)
```
Settings: TOP3000, decay 0, neutralization subindustry. Smoothing helps.

### B19 · Ratio of up-day count vs long-window baseline
```
a = ts_sum(open > close, 20)  / ts_sum(open < close, 20);
b = ts_sum(open > close, 250) / ts_sum(open < close, 250);
rank(a / b)
```
Settings: TOP3000, decay 20, neutralization subindustry.

---

## Video / Email Alphas (fundamentals + sentiment)

### V1 · Negative debt/equity, ts-ranked
```
ts_rank(-debt / equity, 240)
```
Improve with leverage and liquidity gates.

### V2 · Decreasing-debt, asset-normalized, sector-neutral
```
group_neutralize(rank(-ts_delta(debt, 60) / assets), sector)
```

### V3 · Inventory-turnover ts-zscore rank
```
rank(ts_zscore(inventory_turnover, 240))
```
Improve with earnings + COGS factors.

### V4 · Sales-per-share growth gate, fall-back to reversion
```
sales_ps > last_diff_value(sales_ps, 5) ? 1 : rank(-ts_delta(close, 5))
```
Replace `1` with a meaningful magnitude expression.

### V5 · COGS-per-PPE × inventory-turnover composite
```
rank(ts_rank(cogs / ppent, 240)) * (1 + rank(ts_rank(inventory_turnover, 240)))
```

### V6 · Estimated-EPS yield
```
rank(ts_rank(est_eps / close, 40))
```
Improve with estimated-sales-per-share.

### V7 · Negative delta of price/EPS-est
```
-rank(ts_delta(close / est_eps, 5))
```
Improve with EPS dispersion + volume.

### V8 · EPS-revision gate, fall-back to reversion
```
est_eps > last_diff_value(est_epsr, 5) ? 1 : rank(-ts_delta(close, 5))
```
Replace `1` with sentiment-driven magnitude.

### V9 · Inventory-vs-asset balance
```
0.5 - rank(ts_rank(inventory / (assets - goodwill), 60)) *
      rank(ts_rank(inventory_turnover, 120))
```
Improve with cashflow / inventory correlation.

### V10 · Social-buzz / customer count
```
ts_rank(snt_social_volume / rel_num_cust, 60)
```
Improve by adding sentiment direction.

### V11 · Customer-return / competitor-count, group-ranked
```
group_rank(argmin(rel_ret_cust / rel_num_comp, 15), subindustry)
```
Improve with competitor returns.

### V12 · Buzz-spike gated sentiment-mean reversion
```
rank(ts_rank(snt_social_volume, 60)) > 0.6 ?
  group_rank(
    (sum(snt_social_value, 10) / 10) / ts_max(snt_social_value, 60),
    subindustry
  ) :
  0
```
Replace `0` with a meaningful expression.

### V13 · Intraday close-position × sentiment volume
```
rank(((high + low) / 2 - close) / (high - low)) *
rank(ts_rank(snt_social_volume, 40))
```
Improve with `trade_when` on volatility/volume.

### V14 · Bullish/bearish ratio × buzz volume
```
group_rank(snt_bullish / snt_bearish, market) * ts_rank(snt_social_volume, 254)
```

### V15 · Sentiment-position ranged
```
y = snt_bullish - snt_bearish;
rank(-(y - ts_min(y, 10)) / (ts_max(y, 10) - ts_min(y, 10))) *
  (1 + rank(snt_social_volume))
```
Improve with price-volume reversion gate.

---

## Synthesis Hooks

When the synth step generates candidates, use this catalog by:

1. Match the user's hypothesis to the closest family above.
2. Take the listed expression as the **template**, then mutate one of:
   field, window length, neutralization, decay, universe.
3. Always wrap the final form in the canonical pipeline:
   `scale(group_neutralize(zscore(ts_zscore(winsorize(<signal>), d)), subindustry))`.
4. If the source uses delay 0, propose both delay-0 and delay-1 variants —
   the delay-1 variant scores 3× higher in IQC merging.
