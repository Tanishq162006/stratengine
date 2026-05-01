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
