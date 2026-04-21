# IMC Prosperity 4 — Reading the Order Book

## Order book structure (Prosperity 4)

```python
# sell_orders: {price: negative_qty}  e.g. {10005: -3, 10007: -8}
# buy_orders:  {price: positive_qty}  e.g. {9995: 5, 9993: 4}

best_ask = min(depth.sell_orders)     # lowest ask
best_bid = max(depth.buy_orders)      # highest bid
mid      = (best_bid + best_ask) / 2
spread   = best_ask - best_bid        # tighter = more competitive
```

## Order imbalance signal

Order imbalance predicts short-term price direction. Heavy bid side → price going up.

```python
def order_imbalance(depth, levels=3):
    """Returns value in [-1, 1]. Positive = more buy pressure."""
    bids = sorted(depth.buy_orders.keys(), reverse=True)[:levels]
    asks = sorted(depth.sell_orders.keys())[:levels]
    bid_vol = sum(depth.buy_orders[p] for p in bids)
    ask_vol = sum(-depth.sell_orders[p] for p in asks)
    total = bid_vol + ask_vol
    if total == 0:
        return 0.0
    return (bid_vol - ask_vol) / total

# Usage:
imb = order_imbalance(depth)
if imb > 0.6:   # strong buy pressure → buy before price rises
    orders.append(Order(product, best_ask, qty))
elif imb < -0.6:  # strong sell pressure → sell before price drops
    orders.append(Order(product, best_bid, -qty))
```

## VWAP from order book

```python
def book_vwap(depth, side='both'):
    total_vol = 0
    total_notional = 0.0
    if side in ('buy', 'both'):
        for px, qty in depth.buy_orders.items():
            total_vol += qty
            total_notional += px * qty
    if side in ('sell', 'both'):
        for px, qty in depth.sell_orders.items():
            vol = -qty
            total_vol += vol
            total_notional += px * vol
    return total_notional / total_vol if total_vol else 0.0
```

## Aggressive vs passive order strategy

```python
# AGGRESSIVE: take liquidity (cross spread) — guarantees fill, costs spread
orders.append(Order(product, best_ask, qty))   # pay the ask to buy

# PASSIVE: provide liquidity (post inside spread) — better price, may not fill
inside_bid = best_bid + 1    # one tick better than best bid
orders.append(Order(product, inside_bid, qty))

# IMC RULE: passive orders not filled by bots are CANCELLED at end of tick.
# Use passive when: confident in direction AND spread is wide enough.
# Use aggressive when: strong signal, position near limit, need quick exit.
```

## Exhausting the book safely

```python
def sweep_asks(depth, fair_value, pos, limit):
    """Buy all ask volume below fair value, respecting position limit."""
    orders = []
    remaining_room = limit - pos
    for ask_px in sorted(depth.sell_orders.keys()):
        if ask_px >= fair_value:
            break
        vol = -depth.sell_orders[ask_px]
        qty = min(vol, remaining_room)
        if qty <= 0:
            break
        orders.append(Order(depth, ask_px, qty))
        remaining_room -= qty
    return orders

def sweep_bids(depth, fair_value, pos, limit):
    """Sell all bid volume above fair value, respecting position limit."""
    orders = []
    remaining_room = limit + pos
    for bid_px in sorted(depth.buy_orders.keys(), reverse=True):
        if bid_px <= fair_value:
            break
        vol = depth.buy_orders[bid_px]
        qty = min(vol, remaining_room)
        if qty <= 0:
            break
        orders.append(Order(depth, bid_px, -qty))
        remaining_room -= qty
    return orders
```

## Market trades signal (own_trades + market_trades)

```python
# market_trades: what OTHER participants traded this tick
# Large market trade → informed flow → price will move in that direction

def detect_informed_flow(market_trades, product, threshold=20):
    trades = market_trades.get(product, [])
    net_buy = sum(t.quantity for t in trades if t.quantity > 0)
    net_sell = sum(-t.quantity for t in trades if t.quantity < 0)
    imb = net_buy - net_sell
    if imb > threshold:
        return 'buy_pressure'
    elif imb < -threshold:
        return 'sell_pressure'
    return 'neutral'
```

## Key invariants (Prosperity-specific)

1. `sell_orders` values are **always negative** — negate them for volume.
2. Aggregated buy qty for a product must not exceed `limit - pos` or ALL orders rejected.
3. Passive orders surviving a tick appear in next tick's `own_trades`.
4. Bot-to-bot trades appear in `market_trades` but NOT in your `own_trades`.
