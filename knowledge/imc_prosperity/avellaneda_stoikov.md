# Avellaneda-Stoikov Market Making Model

The gold standard for inventory-aware market making. Every serious IMC competitor uses some variant of this.

## Core idea

A market maker posts bid/ask quotes around a **reservation price** that shifts based on inventory. The wider you are away from zero inventory, the more you skew quotes to unwind.

## Reservation price

```python
r = mid - pos * gamma * sigma**2 * T

# mid   = current mid price
# pos   = current inventory (signed)
# gamma = risk-aversion parameter (0.01 to 0.1 — tune)
# sigma = volatility of mid price (rolling std of returns)
# T     = time remaining (normalize: ticks_left / total_ticks)
```

As `pos` increases (long), `r` drops below mid → you post a lower bid (don't want more) and lower ask (eager to sell).

## Optimal spread

```python
spread = gamma * sigma**2 * T + (2/gamma) * math.log(1 + gamma/kappa)

# kappa = arrival rate of market orders (estimate from market_trades density)
# Simplified for competition: spread = gamma * sigma**2 + base_spread
```

## Full quote calculation

```python
def as_quotes(mid, pos, limit, sigma, gamma=0.05, kappa=1.5, T=1.0):
    r = mid - pos * gamma * sigma**2 * T
    half_spread = (gamma * sigma**2 * T) / 2 + math.log(1 + gamma / kappa) / gamma
    half_spread = max(1, round(half_spread))   # at least 1 tick

    bid = round(r - half_spread)
    ask = round(r + half_spread)

    # Skew sizes: lean toward zero-inventory side
    skew = pos / limit   # -1 to +1
    bid_qty = max(1, round((1 - skew) * 10))   # bigger when short (want to buy)
    ask_qty = max(1, round((1 + skew) * 10))   # bigger when long (want to sell)

    return bid, ask, bid_qty, ask_qty
```

## Practical IMC adaptation

```python
import statistics, math, json

class Trader:
    GAMMA = 0.05
    KAPPA = 1.5

    def run(self, state):
        data = json.loads(state.traderData) if state.traderData else {}
        result = {}

        for product, depth in state.order_depths.items():
            if not depth.buy_orders or not depth.sell_orders:
                result[product] = []
                continue

            mid = (max(depth.buy_orders) + min(depth.sell_orders)) / 2
            hist = data.get(product, [])
            hist.append(mid)
            hist = hist[-50:]
            data[product] = hist

            pos   = state.position.get(product, 0)
            limit = 80  # Prosperity 4

            if len(hist) < 5:
                result[product] = []
                continue

            returns = [hist[i]/hist[i-1]-1 for i in range(1, len(hist))]
            sigma   = statistics.stdev(returns) * mid if len(returns) > 1 else 1.0
            sigma   = max(sigma, 0.5)

            bid, ask, bq, aq = as_quotes(mid, pos, limit, sigma,
                                          self.GAMMA, self.KAPPA)

            orders = []
            if pos < limit:
                orders.append(Order(product, bid, min(bq, limit - pos)))
            if pos > -limit:
                orders.append(Order(product, ask, -min(aq, limit + pos)))
            result[product] = orders

        return result, 0, json.dumps(data)
```

## Parameter tuning guide

| Parameter | Low value effect | High value effect | Start with |
|---|---|---|---|
| `gamma` | tight spread, holds inventory | wide spread, aggressive unwind | 0.05 |
| `kappa` | wider spread (slow arrivals) | tighter spread (fast arrivals) | 1.5 |
| `T` | (set to 1 — use inventory-only skew in competition) | | 1.0 |

## When NOT to use A-S

- ASH_COATED_OSMIUM during regime breaks: sigma explodes → spread too wide → no fills
- Gate with: `if sigma > 3 * sigma_baseline: skip_quoting = True`
