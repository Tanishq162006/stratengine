# IMC Prosperity — Conversion Products (ORCHIDS, MAGNIFICENT_MACARONS)

## Mechanics

Conversion products let you convert between "local" and "south island" inventory at each tick.
The simulator charges fees per conversion:

```
effective_buy  = south_ask + transport_fee + import_tariff
effective_sell = south_bid - transport_fee - export_tariff
storage_cost   = 0.1 seashells / unit / tick  (only when long locally)
```

`observations.conversionObservations[product]` fields:
- `bidPrice`, `askPrice`  — South island quotes
- `transportFees`, `exportTariff`, `importTariff`
- `sunlightIndex`, `sugarPrice`  (MACARONS only — drive fair value)

## Core arbitrage logic

```python
obs = state.observations.conversionObservations.get("ORCHIDS")
if obs is None:
    return

cost_to_buy_south  = obs.askPrice + obs.transportFees + obs.importTariff
cost_to_sell_south = obs.bidPrice - obs.transportFees - obs.exportTariff

# If local ask < effective south sell → buy locally, convert out for profit
for ask_px, ask_vol in sorted(depth.sell_orders.items()):
    if ask_px < cost_to_sell_south and pos < limit:
        qty = min(-ask_vol, limit - pos)
        orders.append(Order("ORCHIDS", ask_px, qty))
        conversions += qty          # convert immediately to flatten

# If local bid > effective south buy → buy south, sell locally
for bid_px, bid_vol in sorted(depth.buy_orders.items(), reverse=True):
    if bid_px > cost_to_buy_south and pos > -limit:
        qty = min(bid_vol, pos + limit)
        orders.append(Order("ORCHIDS", bid_px, -qty))
        conversions -= qty
```

## Storage cost avoidance

Long positions accumulate 0.1 seashells/tick. **Never hold long ORCHIDS overnight.**
- Prefer flat or short going into end of day.
- If stuck long: convert out via `conversions` (costs transport but avoids accumulation).
- Treat storage as a running cost when computing fair-value vs south price.

## MAGNIFICENT_MACARONS fair value

Fair value is driven by observable macro inputs:

```python
# Sunlight: higher sun → cheaper production → lower fair value
# Sugar: higher price → higher cost → higher fair value
fair = base + sugar_coeff * obs.sugarPrice - sun_coeff * obs.sunlightIndex
```

Calibrate `base`, `sugar_coeff`, `sun_coeff` from historical observations in the dataset.
MACARONS also has storage cost — apply same intraday-flatten discipline as ORCHIDS.

## Anti-patterns

- Forgetting `importTariff` / `exportTariff` — makes arb appear larger than it is; real fills lose money.
- Holding a long ORCHIDS position for multiple ticks hoping it appreciates — storage bleeds you.
- Treating `conversions` as optional: if you want to arbitrage, you must use the conversion count.
- Using conversion for speculative directional bets — conversion costs destroy small directional edges.
