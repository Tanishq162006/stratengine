# IMC Prosperity 4 — Market Making Playbook

## Products (Rounds 1 & 2)

| Product | Type | Limit | Strategy |
|---|---|---|---|
| `INTARIAN_PEPPER_ROOT` | stable value | 80 | Hard-coded fair value MM + inventory skew |
| `ASH_COATED_OSMIUM` | volatile/patterned | 80 | Regime-aware — investigate hidden pattern |
| `EMERALDS` | stable value (tutorial) | 80 | Same as PEPPER_ROOT |
| `TOMATOES` | drifting (tutorial) | 80 | Rolling mid / EMA fair value |

## Inventory skew (non-negotiable)

Given `pos` in `[-limit, +limit]`, skew quotes so you lean against inventory:

```python
skew = (pos / limit) * k     # k = 1..3 typical
bid = fair_value - base_spread - max(0,  skew)
ask = fair_value + base_spread - min(0,  skew)
```

Effect: when long near the cap, bid is pushed away (don't accumulate more), ask is tighter (encourage unload).

## INTARIAN_PEPPER_ROOT — stable value MM

```python
FAIR = 10000  # estimate from early ticks — check first mid observation

def mm_stable(depth, pos, limit, fair):
    orders = []
    base_spread = 2
    skew = (pos / limit) * 2

    # Take existing mispriced quotes aggressively
    for ask_px in sorted(depth.sell_orders):
        if ask_px < fair and pos < limit:
            qty = min(-depth.sell_orders[ask_px], limit - pos)
            orders.append(Order("INTARIAN_PEPPER_ROOT", ask_px, qty))

    for bid_px in sorted(depth.buy_orders, reverse=True):
        if bid_px > fair and pos > -limit:
            qty = min(depth.buy_orders[bid_px], pos + limit)
            orders.append(Order("INTARIAN_PEPPER_ROOT", bid_px, -qty))

    # Post resting quotes
    my_bid = round(fair - base_spread - max(0, skew))
    my_ask = round(fair + base_spread - min(0, skew))
    bid_room = limit - pos - sum(o.quantity for o in orders if o.quantity > 0)
    ask_room = limit + pos - sum(-o.quantity for o in orders if o.quantity < 0)
    if bid_room > 0:
        orders.append(Order("INTARIAN_PEPPER_ROOT", my_bid, bid_room))
    if ask_room > 0:
        orders.append(Order("INTARIAN_PEPPER_ROOT", my_ask, -ask_room))
    return orders
```

## ASH_COATED_OSMIUM — patterned volatile

IMC hints at a "hidden pattern" — don't pure MM. Steps:

1. **Accumulate mid-price history** in traderData (last 20-50 ticks)
2. **Compute rolling z-score**: `z = (mid - mean) / std`
3. **Enter on extremes**: buy when `z < -1.5`, sell when `z > 1.5`
4. **Regime gate**: skip if `vol_5 > 2 * vol_20` (regime break)
5. **Exit at z ~ 0**: use resting limit orders, don't cross spread

```python
import statistics, json

def fair_osmium(history):
    if len(history) < 5:
        return None
    return statistics.mean(history[-10:])

def zscore(history):
    if len(history) < 10:
        return 0.0
    mu = statistics.mean(history)
    sd = statistics.stdev(history)
    return (history[-1] - mu) / sd if sd > 0 else 0.0
```

## Order sizing rule

```python
# Never exceed limit. Account for already-queued orders.
buy_room  = limit - pos
sell_room = limit + pos
qty = min(desired_qty, buy_room)   # for buy orders
```

## Critical bugs to avoid

1. **Sell orders have negative volume** in `depth.sell_orders` — use `-depth.sell_orders[px]` for qty.
2. **All orders for a product are rejected** if aggregated buy qty would exceed `limit - pos`. Check headroom before sending.
3. **Class variables don't persist** — only `traderData` string survives between ticks. Max 50k chars.
4. **Empty book side** — always check `depth.buy_orders` and `depth.sell_orders` before computing mid.
