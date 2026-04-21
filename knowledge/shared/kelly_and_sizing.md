# Kelly Criterion & Position Sizing — Advanced Quant Reference

## Kelly formula

```
f* = (p * b - q) / b
where:
  p = probability of winning
  q = 1 - p (probability of losing)
  b = net profit per unit (odds)
  f* = optimal fraction of capital to bet
```

```python
def kelly(p_win, net_odds):
    """Returns optimal fraction. Negative means don't bet."""
    return (p_win * (net_odds + 1) - 1) / net_odds

# Conservative: use half-Kelly to reduce variance
# Full Kelly → maximum long-run growth but 50% drawdowns possible
# Half Kelly → ~75% of growth, much lower drawdowns

def safe_kelly(p_win, net_odds, fraction=0.5, max_bet=0.25):
    raw = kelly(p_win, net_odds)
    return max(0.0, min(raw * fraction, max_bet))
```

## Translating Kelly to discrete order sizes

```python
def kelly_size_units(edge, volatility_per_tick, position_limit, current_pos):
    """
    edge = expected return per tick (in price units)
    vol  = std dev of price per tick
    Sharpe-inspired sizing: size ∝ edge / vol²
    """
    if volatility_per_tick < 1e-6:
        return 0
    kelly_f = edge / (volatility_per_tick ** 2)
    desired = int(kelly_f * position_limit)
    desired = max(-position_limit, min(desired, position_limit))
    delta = desired - current_pos
    return delta  # positive = buy, negative = sell
```

## Fractional Kelly table

| Kelly Fraction | Expected growth | Max drawdown |
|---|---|---|
| 1.0 (full) | Maximum | ~50% |
| 0.5 (half) | ~75% of max | ~25% |
| 0.25 (quarter) | ~50% of max | ~12% |
| 0.0 | 0% | 0% |

In competitions: use **quarter-Kelly** for new products/regimes, **half-Kelly** after 50+ ticks of calibrated estimates.

## Multi-product portfolio sizing

```python
def portfolio_sizes(signals, vols, corr_matrix, limit=80, risk_budget=1.0):
    """
    signals: dict {product: expected_return}
    vols: dict {product: volatility}
    corr_matrix: 2D — if products correlated, reduce combined size
    """
    n = len(signals)
    products = list(signals.keys())
    raw_sizes = {}
    for p in products:
        if vols[p] > 0:
            raw_sizes[p] = signals[p] / (vols[p] ** 2)

    # Scale so largest position = limit
    if raw_sizes:
        max_raw = max(abs(v) for v in raw_sizes.values()) or 1
        scale = limit / max_raw
        return {p: int(v * scale * risk_budget) for p, v in raw_sizes.items()}
    return {p: 0 for p in products}
```

## Ergodicity — why Kelly matters

- **Arithmetic mean** of returns looks great on paper
- **Geometric mean** (actual compounding) gets destroyed by large losses
- Kelly maximizes geometric mean — optimizes what actually compounds over time
- Overbetting beyond Kelly → **negative geometric mean even with positive edge**

```python
# Illustration
import math
def simulate_kelly(p, b, f, rounds=1000):
    """Returns log of final wealth."""
    log_w = 0
    for _ in range(rounds):
        if random.random() < p:
            log_w += math.log(1 + f * b)
        else:
            log_w += math.log(1 - f)
    return log_w  # positive = profitable long-run
```
