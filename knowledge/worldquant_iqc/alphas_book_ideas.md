# Finding Alphas (book) — Strategy Concept Library

Short-form alpha concepts surfaced via the WQ-published seminar notes.
Use as **idea seeds** during the synth step — most are not BRAIN
expressions yet, so the synth step will need to translate the concept
into the canonical pipeline.

## Price-Volume

1. Reversal: `-ts_delta(close, 5) / ts_delay(close, 5)`. Try industry
   neutralization, `rank(...)`, 3-day decay.
2. Volatility ranking: `std(returns)`. Smooth with `clamp` / `hump`.
3. Volume scale: `log(volume)`.
4. Earnings-event filter: `days_until_earnings_announcement < N ? 1 : 0`.
5. Use ratios: `earnings / revenue`. Don't put earnings in denominator
   (zero risk).
6. **Buy before earnings announcements.**
7. Buy if `net_income > 0`, increasing `net_income / total_assets`,
   increasing gross margin.
8. Buy if cash from operations > 0 AND > net income.
9. `net_income / total_assets > industry median`.
10. `cash_flow / total_assets > industry median`.

## Quality / Variance

11. `net_income variance < industry median`.
12. `gross_income variance < industry median`.
13. `rnd_expenses / total_assets > industry median`.
14. `capex / total_assets > industry median`.
15. `advertising_expenses / total_assets > industry median`.

## Operating Efficiency

16. Decreasing inventory per unit sales.
17. Increasing accounts receivable per unit sales.
18. Increasing sales minus change in gross margin.
19. Decreasing admin expenses per unit sales.
20. Improving tax rate.
21. Sales per employee.
22. Net sales < free cash flow.

## Valuation

23. High book-to-price.
24. Low sales growth.
25. High cash-flow-from-ops to price ratio.
26. Equity issuance < industry average over 2 years.

## Sentiment / News

27. Long if sentiment > 70, short if < 30.
    - Adjust magnitude with `novelty`.
    - Refine: `novelty * relevance`.
    - Scale by prior returns: `novelty * relevance * category_score`.
28. Short companies with lots of news.
29. Momentum for 2 days after earnings, then reverse for next 5 days.

## Leverage / Capital Structure

30. `ts_rank(-debt / equity, 240)`.
31. `ts_rank(log(tweets + 1), 20) - 0.5`.

## Options

32. Negate options volatility skew: `-ts_delta(implied_volatility_slope)`.
33. High volatility spread: `call_iv - put_iv`.
34. `-option_volume / equity_volume` (stronger when short-sale cost is
    high and option leverage is low).
35. Negate change in aggregate put open-interest:
    `open_interest_call / open_interest_put`.

## Analyst-Driven

36. Heed analyst recommendations.
37. Buy if `target_price > current_price`.
38. Buy if earnings beat estimates.
39. Track changes in earnings estimates for upcoming year.
40. Sentiment of questions during earnings calls.
41. `short_term_analyst_coverage / long_term_analyst_coverage`.

## Event / Macro

42. Invest in spin-offs and their parents.
43. `(second-to-last-interval-close - last-interval-close) * std(close)`.
44. Long small / short large within an index.
45. Buy sector ETFs trading above moving average.
46. Sell in May, buy in November (calendar anomaly).
47. Follow Commitment-of-Traders reports for commodities.
48. Long if market is risk-on (VIX is low).

## Translation Cheatsheet

When converting a book concept to a BRAIN expression:

| Concept | BRAIN form |
|---|---|
| "improvement vs industry median" | `x - group_mean(x, industry)` |
| "ranked vs industry" | `group_rank(x, industry)` |
| "year-over-year change" | `ts_delta(x, 252)` |
| "rate of change" | `ts_delta(x, d) / (ts_delay(x, d) + 0.0001)` |
| "decreasing" | `-ts_delta(x, d)` |
| "increasing" | `ts_delta(x, d)` |
| "above moving average" | `x > ts_mean(x, d) ? 1 : 0` |
| "ratio to peers" | `x / group_mean(x, industry)` |
| "smoothing" | `ts_decay_linear(x, d)` or `ts_ema(x, d)` |
| "clamp outliers" | `winsorize(x)` or `truncate(x, pct)` |
| "buy/sell binary" | wrap with `trade_when(cond, alpha, -1)` |

After translation, always wrap the final form in:
```
scale(group_neutralize(zscore(ts_zscore(winsorize(<signal>), d)), subindustry))
```
