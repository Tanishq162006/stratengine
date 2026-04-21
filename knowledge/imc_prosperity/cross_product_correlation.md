# IMC Prosperity 4 — Cross-Product Correlation & Multi-Asset Strategy

## When new products arrive in later rounds

Round 3+ typically introduces products that are correlated with each other or with
existing products. Correlation creates two opportunities:
1. **Basket/index arb** — trade the spread between a basket and its components
2. **Lead-lag** — one product's price predicts the other's next move

## Detecting correlation in live trading

```python
import statistics

def rolling_correlation(series_a, series_b, window=20):
    """Pearson correlation over rolling window. Returns -1 to 1."""
    if len(series_a) < window or len(series_b) < window:
        return 0.0
    a = series_a[-window:]
    b = series_b[-window:]
    mu_a, mu_b = statistics.mean(a), statistics.mean(b)
    cov = sum((a[i]-mu_a)*(b[i]-mu_b) for i in range(window))
    var_a = sum((x-mu_a)**2 for x in a)
    var_b = sum((x-mu_b)**2 for x in b)
    denom = (var_a * var_b) ** 0.5
    return cov / denom if denom > 1e-9 else 0.0
```

## Lead-lag detection

```python
def lead_lag(series_a, series_b, max_lag=3):
    """
    Returns lag where correlation is highest.
    Positive lag = A leads B (A moves first).
    Negative lag = B leads A.
    """
    best_lag, best_corr = 0, 0.0
    for lag in range(-max_lag, max_lag+1):
        if lag >= 0:
            a_slice = series_a[:len(series_a)-lag] if lag > 0 else series_a
            b_slice = series_b[lag:] if lag > 0 else series_b
        else:
            a_slice = series_a[-lag:]
            b_slice = series_b[:len(series_b)+lag]
        n = min(len(a_slice), len(b_slice), 20)
        if n < 5:
            continue
        corr = rolling_correlation(a_slice[-n:], b_slice[-n:], n)
        if abs(corr) > abs(best_corr):
            best_lag, best_corr = lag, corr
    return best_lag, best_corr
# If A leads B by 1 tick: buy B when A goes up, short B when A goes down
```

## Pairs spread trading (cointegrated products)

```python
def spread(price_a, price_b, hedge_ratio=1.0):
    """Spread = A - hedge_ratio * B. Mean-reverts if cointegrated."""
    return price_a - hedge_ratio * price_b

def hedge_ratio_ols(series_a, series_b):
    """OLS estimate: regress A on B, return slope."""
    n = min(len(series_a), len(series_b))
    a, b = series_a[-n:], series_b[-n:]
    mu_b = sum(b) / n
    mu_a = sum(a) / n
    num = sum((b[i]-mu_b)*(a[i]-mu_a) for i in range(n))
    den = sum((b[i]-mu_b)**2 for i in range(n))
    return num / den if den > 1e-9 else 1.0

# Usage: track spread z-score → enter when |z| > 1.5, exit at |z| < 0.3
```

## Basket arbitrage (if basket product introduced)

```python
# basket_fair = sum(weight_i * price_i for each component)
# If basket trades at premium to fair → short basket, buy components
# If basket trades at discount → long basket, short components

def basket_fair_value(component_mids, weights):
    return sum(w * p for w, p in zip(weights, component_mids))

def basket_spread_z(basket_price, component_mids, weights, history, window=20):
    fair = basket_fair_value(component_mids, weights)
    spread_val = basket_price - fair
    history.append(spread_val)
    if len(history) < window:
        return 0.0, spread_val
    recent = history[-window:]
    mu = sum(recent) / window
    sd = (sum((x-mu)**2 for x in recent)/window)**0.5
    return (spread_val - mu) / (sd + 1e-9), spread_val
```

## Adjusting position limits for correlated products

When two products are correlated (ρ > 0.7), your effective risk is NOT 2× independent:

```python
def portfolio_var(pos_a, pos_b, vol_a, vol_b, rho):
    """Portfolio variance for two correlated positions."""
    return (pos_a*vol_a)**2 + (pos_b*vol_b)**2 + 2*rho*pos_a*pos_b*vol_a*vol_b

# If rho=1 (perfect correlation): risk = (pos_a*vol_a + pos_b*vol_b)^2
# If rho=-1: risk can be hedged to near zero
# Size positions so portfolio_var stays within your risk budget
```

## Key principles for new Round 3 products

1. **First 10-20 ticks**: observe and collect — don't trade aggressively
2. **Estimate correlation with existing products** (PEPPER_ROOT, OSMIUM) immediately
3. **Check if new product leads or lags** existing products
4. **If basket**: compute fair value from components, trade the spread
5. **If conversion**: compute arbitrage bounds including all fees (see conversion_products.md)
6. **If options**: compute implied vol, compare to realized vol (see options_vouchers.md)
