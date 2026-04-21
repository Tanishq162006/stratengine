# Market Microstructure — Advanced Quant Reference

## Bid-ask spread decomposition

The spread has three components:
1. **Inventory cost** — market maker charges for holding unwanted risk
2. **Adverse selection** — compensation for trading against informed flow
3. **Order processing** — fixed costs (exchange fees, latency)

In competition: fees=0, latency=0 → spread is purely inventory + adverse selection.

## Price impact model

```python
# Kyle's lambda: price impact per unit of order flow
# Each unit you buy moves the price up by lambda
lambda_kyle = sigma / (2 * sqrt(volume_per_tick))

# Practical: if you buy X units at once, expect mid to move:
expected_impact = lambda_kyle * X
```

## Spread as a function of volatility

```python
# Empirical rule: optimal spread ≈ 2 * realized_volatility_per_tick
import statistics

def optimal_spread(recent_mids, min_spread=1):
    if len(recent_mids) < 5:
        return min_spread
    returns = [abs(recent_mids[i] - recent_mids[i-1]) for i in range(1, len(recent_mids))]
    vol = statistics.mean(returns)
    return max(min_spread, round(2 * vol))
```

## Informed vs uninformed flow

- **Uninformed (noise) traders**: trade randomly, provide profit to market makers
- **Informed traders**: trade on private information, cause adverse selection

Signs of informed flow in `market_trades`:
- Large single trades (not split up)
- Consistent direction across multiple ticks
- Price moves immediately after the trade

When you see informed flow → widen spread or stop quoting.

## Mean reversion vs momentum — which regime are you in?

```python
import statistics

def classify_regime(prices, window=20):
    if len(prices) < window + 1:
        return 'unknown'
    recent = prices[-window:]
    returns = [recent[i] - recent[i-1] for i in range(1, len(recent))]

    # Autocorrelation at lag 1
    mu = statistics.mean(returns)
    diffs = [r - mu for r in returns]
    acf1 = (sum(diffs[i]*diffs[i-1] for i in range(1, len(diffs))) /
            (sum(d**2 for d in diffs) + 1e-9))

    if acf1 < -0.2:
        return 'mean_reverting'   # negative autocorr → reversals dominate
    elif acf1 > 0.2:
        return 'trending'         # positive autocorr → momentum works
    return 'random_walk'          # neutral → pure MM, no directional edge
```

## Risk management — the quant's laws

1. **Never bet more than you can afford to lose in one bad run** — Kelly fraction
2. **Correlation kills diversification in stress** — when volatility spikes, products co-move
3. **Mean reversion strategies have limited downside per trade but can trend against you**
4. **Momentum strategies have large wins but sharp drawdowns at reversals**
5. **Inventory risk compounds** — a position held for N ticks has N-times the variance
