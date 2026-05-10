# WorldQuant BRAIN — Data Fields Reference

Fields available in the BRAIN DSL. All names are lowercase, no spaces.
Use ts_backfill(x, 90) to forward-fill quarterly fundamental fields.

## Price-Volume Fields (update every trading day)

| Field | Type | Description |
|---|---|---|
| `close` | float | Adjusted closing price (splits + dividends) |
| `open` | float | Opening price |
| `high` | float | Intraday high |
| `low` | float | Intraday low |
| `volume` | float | Shares traded |
| `vwap` | float | Volume-weighted average price |
| `returns` | float | Daily total return (close-to-close, adjusted) |
| `cap` | float | Market capitalization in USD |
| `adv20` | float | 20-day average daily dollar volume (liquidity proxy) |
| `beta` | float | Market beta (systematic risk vs. index) |

## Fundamental Fields (update quarterly — always forward-fill)

| Field | Description | Usage |
|---|---|---|
| `equity` | Shareholders' equity (book value of firm) | `equity / cap` = book-to-market |
| `debt` | Total debt (short + long term) | leverage signal |
| `ebitda` | Earnings before interest, taxes, depreciation, amortization | profitability proxy |
| `revenues` | Total revenues | growth signal: `ts_delta(revenues, 63)` |
| `sales` | Net sales | similar to revenues |
| `operating_income` | Operating earnings (EBIT) | earnings yield: `operating_income / cap` |
| `assets` | Total assets | asset efficiency: `revenues / assets` |
| `retained_earnings` | Cumulative undistributed profits | quality signal |
| `inventory` | Inventory value | inventory turn: `revenues / (inventory + 1)` |
| `enterprise_value` | Market cap + debt - cash | EV/EBITDA: `enterprise_value / (ebitda + 1)` |
| `sharesout` | Shares outstanding | dilution signal |
| `fnd13` | Book value per share | P/B: `cap / (fnd13 * sharesout + 1)` |

## Compustat fnd1..fnd28 Reference (subscription-dependent)

Compustat fundamental fields exposed in BRAIN follow the `fndN` naming
convention. Verify subscription in the BRAIN IDE before depending on a field.
The most commonly used subset:

| Field | Item | Typical use |
|---|---|---|
| `fnd1`  | Cash and short-term investments | liquidity ratio |
| `fnd2`  | Receivables | working capital |
| `fnd3`  | Inventories | inventory turn |
| `fnd4`  | Current assets | quick ratio numerator |
| `fnd5`  | Current liabilities | quick ratio denominator |
| `fnd6`  | Total assets (alias of `assets`) | size proxy |
| `fnd7`  | Property/plant/equipment net | capex proxy |
| `fnd8`  | Long-term debt | leverage |
| `fnd9`  | Total liabilities | leverage / size |
| `fnd10` | Common equity | book value |
| `fnd11` | Sales (alias of `sales`) | growth |
| `fnd12` | Cost of goods sold | gross margin: `(sales - fnd12) / sales` |
| `fnd13` | Book value per share | P/B numerator (per-share form) |
| `fnd14` | Earnings per share | E/P |
| `fnd15` | Dividends per share | yield |
| `fnd16` | Operating income before depreciation | operating margin |
| `fnd17` | Net income | profitability |
| `fnd18` | Cash flow from operations | quality |
| `fnd19` | Capital expenditures | capex / sales |
| `fnd20` | R&D expense | innovation factor |
| `fnd21` | Goodwill | quality red flag |
| `fnd22` | Intangibles total | quality red flag |
| `fnd23` | Accounts payable | working capital |
| `fnd24` | Selling, general & admin | operating efficiency |
| `fnd25` | Tax expense | effective rate proxy |
| `fnd26` | Depreciation & amortization | EBITDA reconstruction |
| `fnd27` | Interest expense | leverage burden |
| `fnd28` | Pretax income | tax rate proxy |

All `fndN` fields require `ts_backfill(x, 120)` before use — quarterly
reporting cadence creates ~2-month NaN gaps that destroy universality.

## IBES / Estimates Fields (subscription-dependent)

| Field | Description |
|---|---|
| `eps_est_curr_qtr` | Mean analyst EPS estimate, current quarter |
| `eps_est_curr_yr`  | Mean analyst EPS estimate, current year |
| `eps_est_next_yr`  | Mean analyst EPS estimate, next year |
| `sales_est_curr_qtr` | Mean analyst sales estimate, current quarter |
| `eps_actual` | Actual reported EPS |
| `eps_surprise` | Reported minus consensus |
| `analyst_rating` | Mean analyst rating (1=strong buy ... 5=strong sell) |
| `target_price` | Mean analyst price target |
| `revisions_up` / `revisions_down` | Estimate revisions in last 30 days |

## Group / Classification Fields (use as `g` in group operators)

| Field | Granularity | Notes |
|---|---|---|
| `market` | global | rarely used — too broad |
| `sector` | ~11 buckets | use when subindustry is too sparse |
| `industry` | ~25 buckets | mid-granularity neutralization |
| `subindustry` | ~158 buckets | DEFAULT — use for `group_neutralize` |
| `country` | per-region | needed for global universes |
| `exchange` | NYSE/NASDAQ/etc | rarely needed |

## Model Data Fundamentals (`mdf_*`)

Proprietary BRAIN aggregations of fundamental data, denser than raw
Compustat. Daily updated. Subscription required.

| Field | Description |
|---|---|
| `mdf_oey` | Operating earnings yield |
| `mdf_gry` | Growth rate × dividend yield composite |
| `mdf_nps` | Net profit smoothness |
| `mdf_pbk` | Price-to-book |

## China Model Variants (`mdl175_*`, `mdl*_*`)

China-specific model fields. Use with `group_rank` / `group_vector_neut`
rather than global `rank` / `vector_neut` (China price-limit system makes
global ranks misleading).

| Field | Description |
|---|---|
| `mdl175_volatility` | Realized volatility (China) |
| `mdl175_revenuettm` | Trailing-twelve-month revenue (China) |
| `mdl175_02amvt` | Activity / amount-weighted measure (China) |

## News (`nws*_*`) — vector-valued

News-event arrays. **MUST** be reduced with `vec_avg`, `vec_sum`,
`vec_max`, or `vec_min` before any scalar operator. After-hours news
fields work well at delay 0 because the price jump shows up next
session.

| Field | Description |
|---|---|
| `nws12_afterhsz_sl` | After-hours news sentiment level |
| `nws12_afterhsz_s1` | After-hours news primary signal vector |
| `nws12_afterhsz_maxupamt` | Max upgrade amount per article (after-hours) |

## Sentiment (`snt_*`) and Social (`scl*_*`)

| Field | Description |
|---|---|
| `snt_buzz_ret` | Buzz-magnitude predicted return |
| `scl12_alltype_buzzvec` | Vector of social-buzz aggregates (use `vec_sum`) |

## Options (`implied_volatility_*`, `pcr_*`, `*_breakeven_*`)

| Field | Description |
|---|---|
| `implied_volatility_call_60` / `implied_volatility_call_720` | Call IV at 60d / 720d |
| `implied_volatility_put_60` / `implied_volatility_put_720` | Put IV at 60d / 720d |
| `pcr_vol_10` | 10-day put/call volume ratio |
| `call_breakeven_10` / `put_breakeven_10` | 10d call / put breakeven price |

## PV-Grouping Models (`pv*_*`)

Pre-built risk-factor grouping signals. Useful in
`group_neutralize(..., densify(pv13_r2_min20_3000_sector))`-style
chains.

| Field | Description |
|---|---|
| `pv13_r2_min20_3000_sector` | PV13 model, R²-clustered, min-20-members, TOP3000, sector-level |

## Family-Aggregated Fields (`fam_*`)

WorldQuant pre-built per-stock aggregations of analyst, ratings, or
estimates data. Drop-in scalars; no `vec_*` reduction required.

| Field | Description |
|---|---|
| `fam_roe_rank` | Family-aggregated ROE rank |
| `fam_est_eps_rank` | Family-aggregated EPS-estimate rank |
| `fam_earn_surp_pct` | Family earnings-surprise percent |

## Finer Balance-Sheet / Income-Statement Fields

| Field | Description |
|---|---|
| `cashflow_op` | Cash flow from operations |
| `cash_st`     | Short-term cash equivalents |
| `debt_st`     | Short-term debt |
| `assets_curr` | Current assets |
| `liabilities_curr` | Current liabilities |
| `ebit`        | Earnings before interest and tax |
| `capex`       | Capital expenditures |
| `cogs`        | Cost of goods sold |
| `ppent`       | Property/plant/equipment, net |
| `goodwill`    | Goodwill |
| `rnd_expenses` | R&D expenses |
| `advertising_expenses` | Advertising expenses |
| `total_assets` / `total_liabilities` | Aggregates |
| `accounts_receivable` | A/R |
| `gross_margin` / `gross_income` | Gross-margin metrics |
| `tax_rate`    | Effective tax rate |
| `equity_issuance` | Net equity issued |
| `inventory_turnover` | sales / inventory |
| `sales_growth` | YoY sales growth |
| `sales_ps`    | Sales per share |
| `est_eps` / `est_epsr` | Analyst-estimate EPS / revised EPS |
| `eps_actual_revised` | Revised actual EPS |
| `analyst_rating`, `target_price` | (already noted above) |

## Sentiment Detail (`snt_*`)

| Field | Description |
|---|---|
| `snt_buzz_ret`     | Buzz-magnitude predicted return |
| `snt_social_volume` | Social-media volume |
| `snt_social_value`  | Aggregated social-media value |
| `snt_bullish` / `snt_bearish` | Directional sentiment counts |

## Social Detail (`scl*_*`) — vector

| Field | Description |
|---|---|
| `scl12_alltype_buzzvec`  | All-type buzz vector |
| `scl12_alltype_sentvec`  | All-type sentiment vector |
| `scl12_buzz`             | Scalar aggregate buzz |
| `scl15_d1_sentiment`     | Daily 1-day sentiment vector |

## Relative Competitor Metrics

| Field | Description |
|---|---|
| `rel_ret_cust`  | Relative return vs customers |
| `rel_ret_comp`  | Relative return vs competitors |
| `rel_num_comp`  | Number of competitors |
| `rel_num_cust`  | Number of customers |

## Risk / Beta / Reference

| Field | Description |
|---|---|
| `beta_last_360_days_spy` | 360-day beta vs SPY |
| `fnd6_newqeventv110_optrfrq` | Risk-free rate (Compustat / new-event) |

## Earnings-Event Helpers

| Field | Description |
|---|---|
| `days_until_earnings_announcement` | Calendar days to next announcement |

## Derived helpers (constructable)

| Name | Formula |
|---|---|
| `rel_ret_comp` | Relative-return composite vs benchmark (use in geometric-mean composites) |

## Named Alternative Data Fields (availability varies by subscription)

| Field | Description |
|---|---|
| `split` | Stock split factor |
| `dividend` | Dividend per share |

## Derived Fields (construct these in your expression)

```
# Relative volume — how much busier today vs 20-day average
rel_vol = volume / (ts_mean(volume, 20) + 1)

# Price momentum (rate of change)
mom_5  = close / (ts_delay(close, 5) + 0.001) - 1
mom_20 = close / (ts_delay(close, 20) + 0.001) - 1

# Intraday range as volatility proxy
atr = ts_mean(high - low, 14)

# Earnings yield (inverse P/E proxy)
ey = operating_income / (cap + 1)

# Book-to-market
btm = equity / (cap + 1)

# Debt-to-equity
dte = debt / (equity + 1)

# Asset turnover
at = revenues / (assets + 1)

# Overnight gap
gap = (open - ts_delay(close, 1)) / (ts_delay(close, 1) + 0.01)

# VWAP deviation (intraday positioning signal)
vwap_dev = (close - vwap) / (vwap + 0.01)

# Normalized dollar volume
dollar_vol = close * volume
ndv = dollar_vol / (ts_mean(dollar_vol, 20) + 1)
```

## Field Selection Guidelines

| Signal Type | Preferred Fields | Timeframe |
|---|---|---|
| Short-term reversal | `returns`, `close`, `volume`, `vwap` | 1-5 days |
| Momentum | `returns`, `close` | 20-252 days |
| Value / fundamental | `equity`, `ebitda`, `operating_income`, `cap`, `fnd13` | 60-252 days |
| Quality | `retained_earnings`, `operating_income`, `assets`, `revenues` | 60-252 days |
| Leverage risk | `debt`, `equity`, `enterprise_value` | 60-252 days |
| Liquidity | `volume`, `adv20`, `cap` | 1-20 days |
| Volatility | `returns` → `ts_std_dev`, `high - low` | 10-60 days |

## Important Caveats

- **Fundamental fields have reporting lag** — use `ts_delay(x, 63)` or `ts_backfill(x, 90)` to avoid look-ahead.
- **`returns` vs `close`** — for momentum, `ts_mean(returns, d)` is cleaner than `close/ts_delay(close,d)` since `returns` is already adjusted.
- **Volume in shares vs dollars** — `volume` is shares; `volume * close` (or `adv20`) is dollar volume and better for cross-stock comparison.
- **Cap is skewed** — always `rank(cap)` or `log(cap + 1)` before using as a signal.
- **Quarterly fields are sparse** — always `ts_backfill(x, 120)` to prevent NaN holes that kill universality score.
