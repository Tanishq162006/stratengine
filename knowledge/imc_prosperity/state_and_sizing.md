# IMC Prosperity 4 — State Management & Position Sizing

## traderData persistence pattern

AWS Lambda recreates the Trader instance every tick. Only `traderData` survives.

```python
import json

class Trader:
    def run(self, state):
        # ── Deserialize ──────────────────────────────────────────────────
        try:
            S = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            S = {}

        # Access per-product history
        hist = S.setdefault("mid_hist", {})     # {product: [prices]}
        params = S.setdefault("params", {})     # {product: {key: val}}

        # ── Your logic here ──────────────────────────────────────────────
        for product, depth in state.order_depths.items():
            if not depth.buy_orders or not depth.sell_orders:
                continue
            mid = (max(depth.buy_orders) + min(depth.sell_orders)) / 2
            h = hist.setdefault(product, [])
            h.append(mid)
            h[:] = h[-100:]   # keep last 100 ticks (watch 50k char limit)

        # ── Serialize (stay under 50,000 chars) ──────────────────────────
        trader_data = json.dumps(S)
        if len(trader_data) > 45000:            # safety margin
            # Trim oldest history
            for h in S.get("mid_hist", {}).values():
                del h[:len(h)//2]
            trader_data = json.dumps(S)

        return result, 0, trader_data
```

## Position headroom calculation

```python
def headroom(pos, limit, pending_buy_qty=0, pending_sell_qty=0):
    """How much more can we buy/sell without hitting limits."""
    buy_room  = limit - pos - pending_buy_qty
    sell_room = limit + pos - pending_sell_qty
    return max(0, buy_room), max(0, sell_room)

# CRITICAL: Prosperity exchange rejects ALL orders for a product
# if aggregated buy qty would cause long > limit (or sell > short limit).
# Always pre-validate:
def safe_buy(product, price, desired_qty, pos, limit, already_buying=0):
    room = limit - pos - already_buying
    qty = min(desired_qty, room)
    return [Order(product, price, qty)] if qty > 0 else []
```

## Kelly criterion for sizing

```python
def kelly_fraction(win_prob, win_pnl, loss_pnl):
    """Optimal fraction of position limit to use."""
    if loss_pnl == 0:
        return 0.0
    b = win_pnl / loss_pnl        # win/loss ratio
    f = (b * win_prob - (1 - win_prob)) / b
    return max(0.0, min(0.25, f)) # cap at 25% of limit (half-Kelly for safety)

# Example: 60% win rate, avg win = 5, avg loss = 3
# f = (5/3 * 0.6 - 0.4) / (5/3) = 0.36 → capped at 0.25
# If limit=80, max position = 80 * 0.25 = 20 units per trade
```

## Multi-product position summary

```python
def position_summary(state, limits):
    """Print a clean summary for debugging."""
    for p, limit in limits.items():
        pos = state.position.get(p, 0)
        pct = pos / limit * 100
        depth = state.order_depths.get(p)
        mid = None
        if depth and depth.buy_orders and depth.sell_orders:
            mid = (max(depth.buy_orders) + min(depth.sell_orders)) / 2
        print(f"{p}: pos={pos:+d}/{limit} ({pct:+.0f}%) mid={mid}")
```

## Inventory unwind — never cross spread

```python
def unwind_position(product, pos, depth, target=0):
    """Unwind toward target using passive orders (don't cross spread)."""
    orders = []
    if pos > target:    # too long → need to sell
        inside_ask = max(depth.buy_orders) + 1   # one tick above best bid
        qty = pos - target
        orders.append(Order(product, inside_ask, -qty))
    elif pos < target:  # too short → need to buy
        inside_bid = min(depth.sell_orders) - 1  # one tick below best ask
        qty = target - pos
        orders.append(Order(product, inside_bid, qty))
    return orders
# Note: if bots don't trade against passive, order is cancelled next tick.
# Acceptable — inventory unwinds gradually without eating spread every tick.
```

## End-of-round inventory risk

Prosperity scores PnL including mark-to-market on open positions. Large inventory at end of round = risk.

```python
TICKS_TOTAL = 1000    # testing; 10000 final
UNWIND_THRESHOLD = 0.8  # start aggressive unwind when 80% through

def urgency(tick, total=TICKS_TOTAL):
    return tick / total

def position_target(pos, limit, urgency_level):
    """Target position shrinks toward 0 as round ends."""
    max_pos = round(limit * (1 - urgency_level))
    if pos > max_pos:
        return max_pos
    elif pos < -max_pos:
        return -max_pos
    return pos   # no change needed
```
