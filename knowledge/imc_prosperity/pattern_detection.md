# IMC Prosperity 4 — Pattern Detection for ASH_COATED_OSMIUM

IMC explicitly says ASH_COATED_OSMIUM has a "hidden pattern." This is the toolkit to find and exploit it.

## Step 1: Characterize the series

```python
import statistics, math

def hurst_exponent(prices, max_lag=20):
    """Hurst < 0.5 = mean-reverting, > 0.5 = trending, ~0.5 = random walk."""
    lags = range(2, max_lag)
    tau = [math.sqrt(statistics.variance(
               [prices[i] - prices[i - lag] for i in range(lag, len(prices))]
           )) for lag in lags]
    if len(tau) < 2:
        return 0.5
    # log-log regression slope
    log_lags = [math.log(l) for l in lags]
    log_tau  = [math.log(t + 1e-9) for t in tau]
    n = len(log_lags)
    sx = sum(log_lags); sy = sum(log_tau)
    sxx = sum(x**2 for x in log_lags)
    sxy = sum(x*y for x, y in zip(log_lags, log_tau))
    return (n*sxy - sx*sy) / (n*sxx - sx**2 + 1e-9)

def autocorr_lag1(prices):
    """Negative autocorr → mean-reverting. Positive → momentum."""
    if len(prices) < 3:
        return 0.0
    returns = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    mu = statistics.mean(returns)
    diffs = [r - mu for r in returns]
    num = sum(diffs[i]*diffs[i-1] for i in range(1, len(diffs)))
    den = sum(d**2 for d in diffs) + 1e-9
    return num / den
```

## Step 2: Bollinger Band mean-reversion

```python
def bollinger_signal(prices, window=20, k=2.0):
    """Returns zscore. |z| > 2 → entry signal."""
    if len(prices) < window:
        return 0.0
    recent = prices[-window:]
    mu  = statistics.mean(recent)
    std = statistics.stdev(recent)
    return (prices[-1] - mu) / (std + 1e-9)

# In run():
z = bollinger_signal(hist)
if z < -2.0 and pos < limit:          # oversold → buy
    qty = min(10, limit - pos)
    orders.append(Order(product, best_ask, qty))
elif z > 2.0 and pos > -limit:        # overbought → sell
    qty = min(10, limit + pos)
    orders.append(Order(product, best_bid, -qty))
elif abs(z) < 0.3:                    # mean-reversion complete → exit
    if pos > 0:
        orders.append(Order(product, best_bid, -pos))
    elif pos < 0:
        orders.append(Order(product, best_ask, -pos))
```

## Step 3: Regime detection (don't trade in trending regimes)

```python
def regime(prices, short=5, long=20):
    """Returns 'trending' or 'mean_reverting'."""
    if len(prices) < long:
        return 'unknown'
    vol_short = statistics.stdev(prices[-short:])
    vol_long  = statistics.stdev(prices[-long:])
    ratio = vol_short / (vol_long + 1e-9)
    if ratio > 1.5:
        return 'trending'     # skip mean-reversion entries
    return 'mean_reverting'   # safe to trade
```

## Step 4: Hidden sinusoidal / cycle pattern

IMC hints at a pattern. Check for cycles:

```python
def detect_cycle(prices, min_period=5, max_period=50):
    """Brute-force period detection via autocorrelation at each lag."""
    returns = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    best_lag, best_corr = 0, 0.0
    mu = statistics.mean(returns)
    var = sum((r - mu)**2 for r in returns) + 1e-9
    for lag in range(min_period, min(max_period, len(returns)//2)):
        corr = sum((returns[i]-mu)*(returns[i-lag]-mu)
                   for i in range(lag, len(returns))) / var
        if corr > best_corr:
            best_corr = corr
            best_lag = lag
    return best_lag, best_corr  # corr > 0.3 → reliable cycle

# Once cycle found:
# phase = (tick % cycle_length) / cycle_length
# if phase < 0.25: expect upswing → buy
# if phase > 0.75: expect downswing → sell
```

## Full ASH_COATED_OSMIUM strategy template

```python
def trade_ash_coated_osmium(depth, pos, hist, tick):
    if not depth.buy_orders or not depth.sell_orders:
        return []
    best_bid = max(depth.buy_orders)
    best_ask = min(depth.sell_orders)
    mid = (best_bid + best_ask) / 2
    limit = 80

    if len(hist) < 20:
        return []

    r = regime(hist)
    if r == 'trending':
        # Don't MM — momentum follow instead
        returns = [hist[i]-hist[i-1] for i in range(1, len(hist))]
        mom = sum(returns[-5:])
        orders = []
        if mom > 0 and pos < limit:
            orders.append(Order("ASH_COATED_OSMIUM", best_ask, min(5, limit-pos)))
        elif mom < 0 and pos > -limit:
            orders.append(Order("ASH_COATED_OSMIUM", best_bid, -min(5, limit+pos)))
        return orders
    else:
        # Mean reversion
        z = bollinger_signal(hist)
        orders = []
        if z < -2.0 and pos < limit:
            orders.append(Order("ASH_COATED_OSMIUM", best_ask, min(15, limit-pos)))
        elif z > 2.0 and pos > -limit:
            orders.append(Order("ASH_COATED_OSMIUM", best_bid, -min(15, limit+pos)))
        elif abs(z) < 0.3 and pos != 0:
            if pos > 0:
                orders.append(Order("ASH_COATED_OSMIUM", best_bid, -pos))
            else:
                orders.append(Order("ASH_COATED_OSMIUM", best_ask, -pos))
        return orders
```
