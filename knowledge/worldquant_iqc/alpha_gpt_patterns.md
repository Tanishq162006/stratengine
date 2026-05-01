# Iterative Alpha Mining Patterns

This note is an original StratEngine summary for WorldQuant-style alpha
iteration. It is conceptually informed by public descriptions of iterative
LLM-assisted alpha mining, including:

- Wang et al., "Alpha-GPT: Human-AI Interactive Alpha Mining for Quantitative
  Investment", arXiv:2308.00016.

No source code from the Alpha-GPT repository or paper is used here.

## Workflow

StratEngine uses a three-step loop:

1. Clarify the market hypothesis and the fields needed to express it.
2. Generate a compact BRAIN expression from the hypothesis.
3. Review platform metrics, diagnose the weakness, and mutate the expression.

This loop is useful because most first-pass alphas fail for ordinary reasons:
noisy signal, excessive turnover, weak sub-universe performance, sparse fields,
or missing neutralization.

## Candidate Families

Price-volume ideas are the fastest to iterate because they use universal fields:

- Short-horizon reversal after unusually negative returns.
- Volume-confirmed reversal after a selloff.
- VWAP or open-close dislocation as a short-lived positioning signal.
- Volatility-adjusted momentum when recent moves persist.

Fundamental ideas can work, but they need stricter handling:

- Backfill sparse fields before using them in a time-series operator.
- Prefer ratios that compare like units.
- Neutralize industry exposure before scaling.
- Expect lower coverage and slower turnover than price-volume alphas.

## Construction Rules

- Start from one clear economic reason, not a bag of operators.
- Normalize time-series behavior before cross-sectional comparison.
- Neutralize by subindustry unless the group is too sparse.
- Scale the final expression so weights are controlled.
- Avoid adding dimensionless constants to typed fields.
- Keep expressions compact enough to inspect manually.

## Review Rules

- Low Sharpe usually means the signal is weak or too noisy.
- Low fitness often means the expression lost magnitude during normalization.
- Weak sub-universe Sharpe usually points to industry beta or sparse fields.
- Turnover above the platform limit needs longer windows or decay.
- Turnover below the platform minimum needs shorter windows or less smoothing.

## Iteration Template

For each tested expression, record:

- expression
- universe and settings
- Sharpe, fitness, sub-universe Sharpe, turnover, and warnings
- one diagnosis
- one mutation rationale

Prefer small, attributable mutations so each test teaches something.
