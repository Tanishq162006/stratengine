# Alpha Research — Advanced Quant Playbook

## What makes a good alpha signal?

1. **Economic rationale** — WHY should this edge exist? (risk premium, behavioral bias, structural)
2. **Out-of-sample evidence** — does it work on data the model never saw?
3. **Decay rate** — how quickly does the alpha fade after entry?
4. **Capacity** — how much capital can you deploy before moving the market?
5. **Correlation** — is it already in your portfolio? Uncorrelated alphas are gold.

## Signal construction pipeline

```
raw_data → transform → normalize → filter → combine → size → execute
```

### Transform
```python
# Level → return (removes non-stationarity)
returns = [prices[i]/prices[i-1] - 1 for i in range(1, len(prices))]

# Smooth noise
ema = prices[-1]
alpha_ema = 0.3
ema = alpha_ema * prices[-1] + (1 - alpha_ema) * ema  # in loop

# Z-score (cross-sectional or time-series)
zscore = (x - mean) / (std + 1e-9)
```

### Normalize
- Clip at ±3σ to prevent outlier dominance
- Rank-transform for robustness: `rank / n_samples`

### Combine signals (ensemble)
```python
# Equal-weight ensemble — reduces noise, often beats any single signal
signal = (signal_1 + signal_2 + signal_3) / 3

# Weighted by Sharpe
weights = [s / sum(sharpes) for s in sharpes]
signal  = sum(w * s for w, s in zip(weights, signals))
```

## Classic alpha signals

### Short-term reversal (1-5 ticks)
```python
# Works when: spread is wide, uninformed flow dominates
signal = -sum(returns[-5:])  # negative: recent losers expected to bounce
```

### Momentum (20-100 ticks)
```python
# Works when: trending regime, informed flow present
signal = sum(returns[-20:]) - sum(returns[-5:])  # medium-term minus short-term
```

### Mean reversion with Bollinger
```python
import statistics
def bollinger_z(prices, window=20):
    recent = prices[-window:]
    mu = statistics.mean(recent)
    sd = statistics.stdev(recent)
    return (prices[-1] - mu) / (sd + 1e-9)
# Buy when z < -2, sell when z > 2, exit at z ≈ 0
```

### Order imbalance (1-3 ticks ahead)
```python
# Strong predictor of next-tick price direction
def imbalance(buy_vol, sell_vol):
    return (buy_vol - sell_vol) / (buy_vol + sell_vol + 1e-9)
```

## Signal evaluation framework

```python
def evaluate_signal(signals, forward_returns, n_buckets=5):
    """Quintile analysis — top bucket should have highest return."""
    pairs = sorted(zip(signals, forward_returns), key=lambda x: x[0])
    n = len(pairs)
    bucket_size = n // n_buckets
    results = []
    for i in range(n_buckets):
        bucket = pairs[i*bucket_size:(i+1)*bucket_size]
        avg_ret = sum(r for _, r in bucket) / len(bucket)
        results.append(avg_ret)
    # Monotonically increasing results = good signal
    ic = sum((results[i] > results[i-1]) for i in range(1, len(results))) / (n_buckets - 1)
    return results, ic  # ic close to 1.0 = strong monotonic signal
```

## Overfitting red flags

- Sharpe > 3 in-sample on < 500 observations → almost certainly overfit
- Strategy uses more than 5 free parameters → needs > 5000 obs to validate
- Works only in a single year → likely regime-specific
- Required 50+ trials to find → multiple comparison problem (divide Sharpe by √50)

## Backtest hygiene

1. **Look-ahead bias**: never use data from tick T to make decision at tick T. Use `prices[:-1]`.
2. **Survivorship bias**: index constituents today ≠ index constituents at backtest start.
3. **Transaction costs**: even at 0 bps, slippage from crossing spread hurts high-turnover strategies.
4. **Walk-forward**: train on first 60%, validate on next 20%, final test on last 20%.
