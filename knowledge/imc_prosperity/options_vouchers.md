# IMC Prosperity — Volcanic Rock Vouchers (Options)

## Contract specs

- Underlying: VOLCANIC_ROCK (position limit 400)
- Vouchers: VOLCANIC_ROCK_VOUCHER_9500 … _10500 (5 strikes, step 250)
- Style: European, cash-settled at expiry
- Expiry: decrements each tick; `state.timestamp` counts up

```python
# Days to expiry from tick timestamp (competition uses 10000 ticks/day approx)
TTE = (expiry_tick - state.timestamp) / 10_000
```

## Black-Scholes pricing

```python
import math

def bs_call(S, K, T, r, sigma):
    if T <= 0:
        return max(S - K, 0.0)
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return S * _N(d1) - K * math.exp(-r * T) * _N(d2)

def _N(x):  # standard normal CDF via Taylor approximation
    a = abs(x)
    t = 1 / (1 + 0.2316419 * a)
    poly = t * (0.319381530 + t * (-0.356563782 + t * (1.781477937
           + t * (-1.821255978 + t * 1.330274429))))
    n = 1 - (1 / math.sqrt(2 * math.pi)) * math.exp(-0.5 * a**2) * poly
    return n if x >= 0 else 1 - n

def bs_delta(S, K, T, r, sigma):
    if T <= 0:
        return 1.0 if S > K else 0.0
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    return _N(d1)
```

## Implied volatility estimation

```python
def implied_vol(market_price, S, K, T, r, tol=1e-5, max_iter=50):
    lo, hi = 1e-6, 10.0
    for _ in range(max_iter):
        mid = (lo + hi) / 2
        price = bs_call(S, K, T, r, mid)
        if abs(price - market_price) < tol:
            return mid
        if price < market_price:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2
```

## Delta hedging

```python
delta = bs_delta(S=rock_mid, K=strike, T=TTE, r=0.0, sigma=iv)
hedge_qty = -round(voucher_pos * delta)   # shares of VOLCANIC_ROCK needed

# Clamp to position limits
rock_pos = state.position.get("VOLCANIC_ROCK", 0)
hedge_qty = max(-400 - rock_pos, min(hedge_qty, 400 - rock_pos))
```

## Strategy summary

1. For each voucher, compute IV from the observable market mid.
2. If IV deviates significantly from rolling-mean IV (z-score > 1.5): sell expensive / buy cheap vol.
3. After each vol trade, delta-hedge with VOLCANIC_ROCK to remain delta-neutral.
4. Re-hedge every tick (delta changes with S and T).

## Anti-patterns

- Using `r > 0` without justification — the competition has no risk-free rate; set `r=0`.
- Forgetting TTE decrements: static T causes mispricing and wrong Greeks.
- Delta-hedging with market orders (crosses spread every tick) — use resting limit orders at mid.
- Ignoring gamma: near expiry and ATM, delta changes rapidly; hedge more frequently or widen hedge band.
- Treating all 5 vouchers as a single "options book" — each has its own limit, IV, and delta.
