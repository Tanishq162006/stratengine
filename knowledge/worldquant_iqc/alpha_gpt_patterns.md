# Alpha-GPT Patterns for WorldQuant IQC

**Source:** Wang, S., Yuan, H., Zhou, L., Ni, L. M., Shum, H.-Y., & Guo, J. (2025).
*Alpha-GPT: Human-AI Interactive Alpha Mining for Quantitative Investment.*
arXiv:2308.00016v2 [q-fin.CP]. https://arxiv.org/abs/2308.00016

**Result:** Top-10 globally at WorldQuant IQC 2024 — 81 qualified alphas, total score 48,866,
in-sample score 65,505, out-of-sample score 43,319 (comparable to Worldwide Top-10).

## The Three-Stage Alpha Workflow

Mirrors StratEngine's pipeline exactly:

| Alpha-GPT Stage | StratEngine Stage | Goal |
|---|---|---|
| **Ideation** — Trading Idea Polisher | synthesize | Translate natural language idea → structured prompt |
| **Implementation** — Quant Developer | coder | Generate valid BRAIN expression from structured prompt |
| **Review** — Analyst | critic | Backtest + score; feed results back for next iteration |

Key insight: alphas improve significantly through iteration. IC doubles after 10 rounds of search enhancement
(Seed IC 0.58% → after Search Enhancement 1.23% → after 1 round human interaction + SE: 2.23%).

## Idea Categories That Generate Strong Alphas

### Price-Volume (fastest to iterate, always valid in BRAIN)
- Short-term reversal (5-day negative return rank) — baseline, works across all regions
- Volume surge + price lag: `ts_rank(volume/ts_mean(volume,20), 5)` combined with return reversal
- VWAP deviation: close vs vwap as intraday positioning signal
- Overnight gap: open vs prior close, typically mean-reverting

### Technical Patterns (translate well to BRAIN DSL)
- **Golden cross**: short EMA crossing above long EMA → `ts_ema(close,5) - ts_ema(close,20)`
- **Bollinger breakout**: `(close - ts_mean(close,20)) / (ts_std_dev(close,20) + 0.001)` → trade when signal > 2
- **Three white soldiers**: `greater(returns, 0) * greater(ts_delay(returns,1), 0) * greater(ts_delay(returns,2), 0)`
- **Trend confirmation**: `ts_linear_reg(close, 10)` — positive slope = trending

### Fundamental / Value
- Book-to-market: prefer low P/B stocks (mean-revert to fair value)
- Earnings yield: `operating_income / (cap + 1)` — rank ascending for value tilt
- Debt leverage: penalize high debt-to-equity names in risk-off environments
- Revenue momentum: `ts_delta(revenues, 63)` — quality growth signal

### Cross-Product / Correlation Signals (advanced)
- Industry spread: `group_neutralize(returns, sector)` — captures relative performance vs peers
- Volatility regime: in high-vol regimes, amplify mean-reversion signal; in low-vol, amplify momentum
- Beta-adjusted return: `returns - beta * market_return` — residual idiosyncratic return

## Alpha Construction Rules from IQC Top Performers

1. **Always rank-transform inputs** before combining — prevents one field dominating due to scale differences
2. **Use subindustry neutralization** as the default; industry if subindustry has too few members
3. **Combine two weakly-correlated alphas** via rank-average: `scale(group_neutralize(0.5*alpha1 + 0.5*alpha2, subindustry))`
4. **Volatility-scale** signals to target consistent exposure: `signal / (ts_std_dev(returns, 20) + 0.001)`
5. **Decay parameter 3-5** reduces turnover without significant Sharpe loss for most mean-reversion alphas
6. **Keep expressions concise** — BRAIN penalizes complexity; a 3-line expression often beats a 10-line one

## Prompt Engineering for Alpha Generation (from Alpha-GPT paper)

When prompting Claude to generate a WQ Brain alpha, structure as:

```
## Specification
You are a quant researcher on the WQ BRAIN platform.

## Trading Idea
[user's idea in natural language]

## Instructions
Generate at least N alpha expressions using only BRAIN DSL operators.
For each alpha: expression, config (universe, neutralization, decay, delay), description.

## Examples
[1-3 seed alphas from knowledge base]
```

The paper shows this structure (Specification + Trading Ideas + Instructions + Examples) produces
the highest-quality and most consistent alpha expressions.

## Search Enhancement Strategy

After generating initial seed alphas:
1. Evaluate on WQ BRAIN (get Sharpe, IC, turnover)
2. Feed metrics back: "Alpha X had Sharpe 0.8, too low. Add confirmation signal to make it more robust."
3. Claude modifies the expression (equivalent to genetic programming mutation)
4. Repeat until Sharpe > 1.25 or fitness > 1.0

This iterative process (search enhancement) consistently improves IC by 2-4x vs the seed alpha.

## IQC Scoring Criteria

| Metric | Target | Notes |
|---|---|---|
| Sharpe Ratio | > 1.25 | Primary filter |
| Fitness Score | > 1.0 | Composite metric |
| Turnover | 3–60% | Outside range = disqualified |
| Weight | Max per stock | Use scale/truncate |
| Universality | Pass | Must work across regions |
| Out-of-sample | Positive Sharpe | Overfitting kills OOS |

Alpha-GPT IQC 2024 result: 81 qualified alphas, comparable to top human participants.
Strategy: generate volume, filter by IS Sharpe, check OOS decay, iterate on survivors.
