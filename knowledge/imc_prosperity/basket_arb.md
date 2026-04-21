# IMC Prosperity — Basket Arbitrage (PICNIC_BASKET1, PICNIC_BASKET2)

## Basket compositions

| Basket | Components | Weights |
|---|---|---|
| PICNIC_BASKET1 | CROISSANTS, JAMS, DJEMBES | 6, 3, 1 |
| PICNIC_BASKET2 | CROISSANTS, JAMS | 4, 2 |

Position limits: BASKET1=60, BASKET2=100, CROISSANTS=250, JAMS=350, DJEMBES=60.

## Fair value and spread signal

```python
def basket_fair(state, basket):
    weights = {
        "PICNIC_BASKET1": {"CROISSANTS": 6, "JAMS": 3, "DJEMBES": 1},
        "PICNIC_BASKET2": {"CROISSANTS": 4, "JAMS": 2},
    }[basket]
    fair = 0.0
    for comp, w in weights.items():
        depth = state.order_depths.get(comp)
        if not depth or not depth.buy_orders or not depth.sell_orders:
            return None
        comp_mid = (max(depth.buy_orders) + min(depth.sell_orders)) / 2
        fair += w * comp_mid
    return fair

# Spread = basket_mid - basket_fair (premium/discount vs NAV)
spread = basket_mid - basket_fair(state, "PICNIC_BASKET1")
```

## Entry logic

```python
SPREAD_ENTRY = 50   # tune from historical spread distribution
SPREAD_EXIT  = 10

if spread > SPREAD_ENTRY:
    # Basket overpriced → short basket, buy components
    sell_basket(qty)
    buy_components(qty, weights)
elif spread < -SPREAD_ENTRY:
    # Basket underpriced → long basket, short components
    buy_basket(qty)
    sell_components(qty, weights)
elif abs(spread) < SPREAD_EXIT:
    # Mean reverted → unwind
    flatten_basket_leg()
    flatten_component_legs()
```

## Leg sizing with position limits

Always check **both** legs fit within limits before entering:

```python
def max_arb_qty(state, basket, weights, positions, limits):
    basket_room = limits[basket] - abs(positions.get(basket, 0))
    comp_rooms = []
    for comp, w in weights.items():
        room = (limits[comp] - abs(positions.get(comp, 0))) // w
        comp_rooms.append(room)
    return min(basket_room, *comp_rooms)
```

## Rolling statistics for threshold calibration

```python
# Keep last 200 spread observations in trader_data
history["spread"].append(spread)
history["spread"] = history["spread"][-200:]
mu  = mean(history["spread"])
std = stdev(history["spread"])
z   = (spread - mu) / std if std > 0 else 0

# Enter at |z| > 1.5, exit at |z| < 0.3
```

## Anti-patterns

- Quoting on only one leg (basket OR components) without hedging the other — naked directional risk.
- Ignoring per-component position limits: DJEMBES limit is 60, which caps BASKET1 arb at qty=60.
- Using stale spread statistics (never updated from trader_data) — threshold drifts out of regime.
- Treating BASKET1 and BASKET2 as perfectly correlated — they diverge; trade each spread independently.
- Position imbalance after partial fills: always confirm both legs before recording a position change.
