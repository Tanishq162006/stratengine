# IMC Prosperity 4 — Timing, Urgency & End-of-Round Management

## Round structure

- Each round runs ~1000 ticks (900ms timeout per tick)
- Final position is marked to fair value — unwound positions get no credit
- **End-of-round inventory = guaranteed loss at fair value, not market price**

## Tracking tick count

```python
# traderData carries tick counter between calls
data = json.loads(state.traderData or "{}")
tick = data.get("tick", 0) + 1
data["tick"] = tick
TOTAL_TICKS = 1000
ticks_left = TOTAL_TICKS - tick
```

## Urgency-based position unwinding

```python
def unwind_orders(product, position, depth, ticks_left, limit=80):
    """Generate orders to close position, more aggressively as time runs out."""
    if position == 0:
        return []

    orders = []

    if ticks_left > 100:
        # Passive: post at fair, wait for fill
        if position > 0 and depth.buy_orders:
            best_bid = max(depth.buy_orders)
            orders.append(Order(product, best_bid, -min(5, position)))
        elif position < 0 and depth.sell_orders:
            best_ask = min(depth.sell_orders)
            orders.append(Order(product, best_ask, min(5, -position)))

    elif ticks_left > 20:
        # Semi-aggressive: cross spread partially
        if position > 0 and depth.sell_orders:
            best_ask = min(depth.sell_orders)
            orders.append(Order(product, best_ask, -min(position // 2 + 1, position)))
        elif position < 0 and depth.buy_orders:
            best_bid = max(depth.buy_orders)
            orders.append(Order(product, best_bid, min((-position) // 2 + 1, -position)))

    else:
        # Aggressive: cross spread fully
        if position > 0 and depth.sell_orders:
            best_ask = min(depth.sell_orders)
            orders.append(Order(product, best_ask, -position))
        elif position < 0 and depth.buy_orders:
            best_bid = max(depth.buy_orders)
            orders.append(Order(product, best_bid, -position))

    return orders
```

## Tick budget management (900ms limit)

```python
import time

class Trader:
    def run(self, state):
        t_start = time.time()
        data = self._load(state.traderData)
        orders = {}

        # Always do cheap operations first
        # Skip expensive computations if time budget low
        for product, depth in state.order_depths.items():
            elapsed_ms = (time.time() - t_start) * 1000
            if elapsed_ms > 700:  # 200ms safety margin
                break  # submit whatever we have — don't timeout

            orders[product] = self._trade(product, depth, state, data)

        return orders, 0, self._save(data)
```

## Quote suppression near limits

```python
def should_quote(position, limit=80, buffer=10):
    """
    Stop posting bids when near long limit.
    Stop posting asks when near short limit.
    """
    can_buy  = position < limit - buffer
    can_sell = position > -limit + buffer
    return can_buy, can_sell

# Usage
can_buy, can_sell = should_quote(state.position.get(product, 0))
if can_buy:
    orders.append(Order(product, bid_price, +size))
if can_sell:
    orders.append(Order(product, ask_price, -size))
```

## traderData size management

```python
def trim_history(data, key, max_len=100):
    """Keep only recent history to stay under 50k traderData limit."""
    if key in data and len(data[key]) > max_len:
        data[key] = data[key][-max_len:]
    return data

def safe_save(data):
    raw = json.dumps(data)
    if len(raw) <= 45000:
        return raw
    # Emergency trim: halve all history lists
    for k, v in data.items():
        if isinstance(v, list) and len(v) > 10:
            data[k] = v[-(len(v)//2):]
    raw = json.dumps(data)
    return raw[:45000]  # hard cut as last resort
```

## End-of-round checklist

| Tick | Action |
|---|---|
| 0-800 | Normal strategy, small passive sizes |
| 801-900 | If abs(pos) > 20: switch to unwind mode |
| 901-950 | Semi-aggressive unwind, cross spread |
| 951-999 | Fully aggressive: cross any spread to get flat |
| 999 | No new positions — only reduce |

## Why end-of-round matters so much

At round end, the engine evaluates your position at **fair value** (mid-price).
If you're long 80 OSMIUM and the price moved against you by 5:
- Loss = 80 × 5 = 400 SEASHELLS — this is real, permanent PnL damage
- No chance to trade out next tick — round is over

Strategy: **target flat by tick 950**. Never sacrifice 200 ticks of MM profit
trying to hold a directional bet you missed the exit on.
