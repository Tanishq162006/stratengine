# IMC Prosperity 4 — Fair Value Estimation

## INTARIAN_PEPPER_ROOT (stable value)

Stable products have a fixed true value. Estimate it from early ticks:

```python
def estimate_stable_fair(history, n_bootstrap=20):
    """Use median of first N mids — robust to outliers."""
    if len(history) < 5:
        return None
    sample = history[:min(n_bootstrap, len(history))]
    sorted_sample = sorted(sample)
    return sorted_sample[len(sorted_sample) // 2]  # median

# Once estimated, treat as constant. Do NOT update from your own fills.
# Only update from order book snapshots.
PEPPER_FAIR = None

def get_pepper_fair(history):
    global PEPPER_FAIR
    if PEPPER_FAIR is None and len(history) >= 10:
        PEPPER_FAIR = estimate_stable_fair(history)
    return PEPPER_FAIR
```

## ASH_COATED_OSMIUM (drifting/patterned)

Use an exponentially weighted moving average — adapts to drift while smoothing noise:

```python
def ema(prices, alpha=0.2):
    """alpha=0.2 → ~5-tick memory. alpha=0.05 → ~20-tick memory."""
    if not prices:
        return None
    val = prices[0]
    for p in prices[1:]:
        val = alpha * p + (1 - alpha) * val
    return val

def wma(prices, window=10):
    """Linearly weighted — most recent tick gets highest weight."""
    recent = prices[-window:]
    weights = list(range(1, len(recent) + 1))
    return sum(p * w for p, w in zip(recent, weights)) / sum(weights)

def kalman_fair(prices, Q=1e-5, R=1e-2):
    """Kalman filter — optimal linear estimator for noisy observations."""
    if not prices:
        return None
    x = prices[0]   # state estimate
    P = 1.0          # estimate uncertainty
    for z in prices[1:]:
        # Predict
        P = P + Q
        # Update
        K = P / (P + R)   # Kalman gain
        x = x + K * (z - x)
        P = (1 - K) * P
    return x
```

## Choosing the right estimator

| Product type | Estimator | Window |
|---|---|---|
| Stable (PEPPER_ROOT) | Median of first 20 ticks | Fixed |
| Slow drift | EMA alpha=0.1 | ~10 ticks |
| Fast pattern | EMA alpha=0.3 | ~3 ticks |
| Noisy with trend | Kalman filter | All history |
| Regime-switching | Weighted blend | 5-20 ticks |

## NEVER update fair value from your own fills

```python
# WRONG — self-influence bias
for trade in state.own_trades.get(product, []):
    fair = trade.price  # your trade moved the price, not the market

# RIGHT — only from order book
if depth.buy_orders and depth.sell_orders:
    mid = (max(depth.buy_orders) + min(depth.sell_orders)) / 2
    history.append(mid)
    fair = ema(history)
```

## Bid-ask midpoint vs VWAP

```python
# Simple mid — fast, standard
mid = (best_bid + best_ask) / 2

# Micro-price — weighted by depth (better fair value estimate)
bid_vol = depth.buy_orders.get(best_bid, 0)
ask_vol = -depth.sell_orders.get(best_ask, 0)
total = bid_vol + ask_vol
micro_price = (best_ask * bid_vol + best_bid * ask_vol) / total if total else mid
# Micro-price > mid → more buying pressure → price likely to tick up
```
