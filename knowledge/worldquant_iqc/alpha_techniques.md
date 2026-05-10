# Alpha Techniques — Learn-Don't-Copy Card

This card is the **distillation** of every alpha catalog in
`knowledge/worldquant_iqc/` (Kakushadze 101, WQ seminar examples, WQ
beginner / video alphas, RussellDash332/WQ-Brain community alphas).

The catalogs themselves (`alphas_101.md`, `alphas_101_brain.md`,
`alphas_official.md`, `seminar_alphas.md`, `alphas_book_ideas.md`) are
**study references** — examples of techniques applied to specific
fields. Do not copy them verbatim. Read them, learn the pattern, then
**stem new alphas** from the technique using fields you actually have
and ideas you actually believe.

The synth/refine prompts should consult this card first, then use the
catalogs as proof-by-example, then propose original combinations.

---

## A. Cross-Sectional Techniques

### A1 · Rank-of-rank-of-rank (triple ranking)
Apply `rank` repeatedly so each level is a normalized cross-sectional
score. Each layer compresses the distribution closer to uniform. Use
when you want the final magnitude bounded but the signal information
preserved.
```
rank(rank(rank(<inner-signal>)))
```
Seen in 101 #31, #78. Use sparingly — three layers is the upper limit.

### A2 · Rank-of-correlation reversal
Cross-stock reversal signal: when two ranked time series are highly
correlated cross-sectionally, the future is likely to revert.
```
-1 * ts_corr(rank(X), rank(Y), d)
-1 * rank(ts_covariance(rank(X), rank(Y), d))
```
Seen in 101 #2, #3, #13, #16, #26, #44, #50.

### A3 · Group-relative measure
Subtract / divide / rank within an industry-aware bucket. The signal
becomes "outperformance vs subindustry peers" rather than "absolute".
```
group_rank(X, subindustry)
group_zscore(X, sector)
X - group_mean(X, industry)
```
Seen across most fundamental alphas.

### A4 · Weighted blend of two correlated fields
Linearly mix two related typed-fields with a tunable weight (often
~0.5–0.9). Reduces noise vs picking one. Common knob:
```
(close * w + vwap * (1 - w))
(low * w + open * (1 - w))
```
Seen in 101 #59, #63–66, #69, #78–80, #87, #89, #93. Weight is an
optimization handle the synth step can sweep.

### A5 · Signed-power for concave/convex transforms
Compress (n<1) or amplify (n>1) the signal magnitude while preserving
sign. Useful when raw magnitudes are dominated by a few outliers (use
n<1) or you want to penalize small deviations (use n>1).
```
signed_power(x, 0.5)   # square-root, concave
signed_power(x, 2)     # squared, convex with sign preserved
```
Seen in 101 #1, #21, #67, #70, #78, #84, #85, #94, #95.

---

## B. Time-Series Techniques

### B1 · ts_decay_linear of differenced typed-field
Smooth a delta with a linear decay window. The decay reduces turnover
without throwing away the directional signal. The differencing isolates
change. Together: a clean, low-turnover momentum / change signal.
```
ts_decay_linear(ts_delta(<typed-field>, d_fast), d_decay)
```
Seen in 101 #31, #39, #57, #63, #66, #71–73, #76–77, #87–91, #96–98.

### B2 · Ts-rank of correlation (lookahead-free regime detector)
A correlation that is itself ranked over time tells you whether the
correlation regime is unusual today. Useful as a gate.
```
ts_rank(ts_corr(X, Y, d_corr), d_rank)
```
Seen in 101 #26, #50, #58, #59.

### B3 · Ts_arg_max / Ts_arg_min for "when did the extreme occur"
Returns a 0..(d-1) index. Use as both a magnitude and as a regime
trigger (`ts_arg_max(volume, 5) == 0` means the volume max is today).
```
ts_arg_max(close, 30)             # days-ago of recent peak
ts_arg_max(volume, 5) == 0        # today is the volume peak
ts_arg_min(close, 30)             # days-ago of recent trough
```
Seen in 101 #1, #7, #26, #96, #98 and seminar PV-7.

### B4 · Average-diff (`ts_av_diff`) for mean-reverting fundamentals
Computes `x - ts_mean(x, d)`. For valuation ratios that have a
long-run mean (P/B, P/E, payout ratio), `ts_av_diff(x, 250+)` captures
"how far from normal".
```
ts_av_diff(mdf_pbk, 250)
ts_av_diff(mdf_pec, 480)
```
Seen in WQ beginner B4, B7; video V12.

### B5 · Geometric-mean composite for returns
Geometric mean is the right average for compounding return series.
Numerically stable form: `exp(mean(log(x)))`.
```
power(ts_product(returns + 1, d), 1/d)
```
Seen in seminar COMP-1.

### B6 · `ts_regression` residual (autoregression detrend)
Predict next-period from past, take the residual. The residual is
"news / shock not explained by the trend". Excellent for reversal.
```
ts_regression(close, close, 20, LAG=1, RETTYPE=3)   # prediction
close - ts_regression(close, close, 20, LAG=1, RETTYPE=3)  # residual
-ts_regression(returns, ts_delay(returns, 1), 252)  # AR(1) reversal
```
Seen in seminar PV-1, WQ-Brain community alphas.

---

## C. Regime / Conditional Techniques

### C1 · Vol-conditional activation
Trade only in high-volatility regimes (where reversion is empirically
strongest). Threshold 0.55 maps to roughly the 50% reversion-dominant
fraction of the day distribution.
```
trade_when(
  ts_rank(ts_std_dev(returns, 22), 252) > 0.55,
  <reversion-alpha>,
  -1
)
```
The `-1` argument means "hold yesterday's position" when the gate is
false — preserves capital without churning. Seen in seminar PV-1, COMP-1.

### C2 · Volume-spike activation
Trade only when today's volume is a 5-day max or above 5-day mean.
```
trade_when(
  (ts_arg_max(volume, 5) < 1) && (volume >= ts_sum(volume, 5) / 5),
  <reversion-alpha>,
  -1
)
```
Seen in seminar PV-7, WQ-Brain community alphas.

### C3 · Earnings-event gate
Trade only on earnings-announcement day, then revert.
```
trade_when(
  days_from_last_change(fam_earn_surp_pct) == 0,
  fam_earn_surp_pct * -returns,
  -1
)
```
Seen in WQ beginner B13.

### C4 · Sentiment / news-spike gate
Activate the alpha only when buzz is in the top quantile.
```
trade_when(rank(sent_vol) > 0.95, -zscore(scl12_buzz) * sent_vol, -1)
```
Seen in WQ beginner B18, video V12.

### C5 · Conditional ternary (regime sub-routing)
Pick alpha A in regime 1, alpha B in regime 2.
```
<cond> ? <alpha_A> : <alpha_B>
```
Seen pervasively in 101 #7, #9, #10, #21, #23, #24, #27, #46, #49, #51.
**Caveat**: ternary alphas are harder to interpret and can fail self-
correlation if both branches collapse to similar PnL — prefer
`trade_when(...)` when the second branch is "do nothing".

---

## D. Risk-Factor Neutralization

### D1 · Vector-neutralization against a risk factor
`vector_neut(a, b)` returns `a − projection(a onto b)`. Removes the
component of `a` that is explained by `b`.
```
# orthogonalize alpha against cap (size factor)
vector_neut(alpha, cap)

# orthogonalize against momentum
vector_neut(alpha, ts_mean(returns, 250))

# orthogonalize against IR (signal stability)
vector_neut(alpha, ts_ir(alpha, 250))

# group-wise variant — use in China and other tighter universes
group_vector_neut(alpha, ts_mean(returns, 120), sector)
```
Seen in seminar OPT-3, NEWS-2, CHN-1; WQ beginner B4.

### D2 · Densified-group neutralization (custom buckets)
Combine two group keys into a finer custom bucket.
```
group_neutralize(alpha, densify((industry + 1) * 10 + exchange))
group_neutralize(alpha, densify(pv13_r2_min20_3000_sector))
```
Seen in seminar NEWS-2, FUND-7. Useful when subindustry alone is too
broad but `industry × exchange` adds the right cross-cutting axis.

---

## E. Universe / Field Selection

### E1 · Use universal liquid fields when targeting Sub-Sharpe
For Sub-Universe Sharpe to clear 0.45, use fields that are dense across
the entire universe: `returns`, `close`, `open`, `high`, `low`, `volume`,
`vwap`, `cap`, `adv20`. Fundamentals and analyst data are sparse — use
only when you can `ts_backfill(x, 120)` first.

### E2 · Match universe to data density
- Compustat-heavy alpha → TOPSP500
- Price-volume alpha → TOP3000
- Sentiment / social → TOP1000 (signal density requires liquid names)
- China alphas → TOP3000 with `group_rank` instead of `rank`

### E3 · Choose neutralization by data family
See `neutralization_guide.md`. The lookup is per data family. Auto-pick
by majority field family in `fields_used`.

---

## F. Submission Diversity Techniques

### F1 · "Same idea, different field"
Take a working alpha and rotate the field while keeping operator
structure. e.g. if `ts_rank(equity / cap, 20)` works, also try
`ts_rank(operating_income / cap, 20)`, `ts_rank(mdf_oey, 20)`,
`ts_rank(retained_earnings / sharesout, 20)`.

### F2 · "Same idea, different operator"
Rotate `ts_rank` ↔ `ts_quantile` ↔ `ts_zscore`, or stack `group_rank`
inside `ts_rank`. Each variant correlates differently and may stack on
the leaderboard.

### F3 · "Same idea, different region/delay"
Every alpha submitted to USA D1 should also be tried on USA D0, CHN D1,
CHN D0. Region alphas are highly uncorrelated — free points if any pass.

### F4 · "Same idea, different neutralization"
Sweep `subindustry` → `industry` → `sector` → `market` → `none`. Sub-
Sharpe and Fitness move differently across these — sometimes the
"wrong" neutralization clears Fitness when subindustry doesn't.

---

## G. Anti-Patterns (don't do this)

- **Overfitting via tiny universes + many parameters.** Pick at most
  2 numerical knobs per alpha; let the structure carry the signal.
- **Long ternary chains.** Two branches max, ideally with `trade_when`.
- **Adding bare integers to typed fields** (`volume + 1`). Use ratios.
- **Using `rank` at the cross-sectional step when Fitness must clear 1.0**
  — `zscore` preserves magnitude, `rank` compresses it.
- **Forgetting `vec_*` reduction on vector data fields** (`nws*_*`,
  `scl*_*`, `*_vec`). Compilation fails.
- **Submitting near-duplicates of your own past alphas.** Self-corr
  gate uses 2-year PnL window — diversify field family or neutralization.

---

## How to Use This Card

When the synth step generates candidates from a hypothesis:

1. Identify the **family** (price-volume reversion, fundamental
   valuation, sentiment, options, etc.).
2. Pick **one technique from B / C / D** that fits the family.
3. Pick **one cross-sectional technique from A** to wrap the inner signal.
4. Pick **fields** from `data_fields.md` matching the hypothesis.
5. Pick **neutralization** from `neutralization_guide.md` based on the
   dominant field family.
6. Wrap the result in the canonical pipeline:
   `scale(group_neutralize(zscore(ts_zscore(winsorize(<signal>), d)), <neutralization>))`.
7. Sanity-check against an analogous example in the catalogs. If you
   are pattern-matching too closely, mutate at least two of: field,
   window, neutralization, or operator.
