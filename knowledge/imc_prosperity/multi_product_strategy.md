# IMC Prosperity 4 — Multi-Product Strategy (Round 1)

## Overview

Round 1 has two algorithmic products with fundamentally different behaviours:
- **INTARIAN_PEPPER_ROOT** — stable fair value → pure market making
- **ASH_COATED_OSMIUM** — drifting/patterned → directional + mean-reversion

Combine them in a single `Trader` class. Keep per-product state isolated.

## Full Round 1 Trader skeleton

```python
import json, math, statistics
from datamodel import OrderDepth, TradingState, Order

PEPPER = "INTARIAN_PEPPER_ROOT"
OSMIUM = "ASH_COATED_OSMIUM"
LIMIT = 80

class Trader:
    def run(self, state: TradingState):
        data = self._load(state.traderData)
        orders: dict[str, list[Order]] = {}

        depth_p = state.order_depths.get(PEPPER)
        depth_o = state.order_depths.get(OSMIUM)

        if depth_p:
            orders[PEPPER], data = self._trade_pepper(depth_p, state, data)
        if depth_o:
            orders[OSMIUM], data = self._trade_osmium(depth_o, state, data)

        return orders, 0, self._save(data)

    # ── PEPPER ROOT: stable value market making ──────────────────────────────

    def _trade_pepper(self, depth, state, data):
        hist = data.setdefault("pepper_hist", [])
        mid = self._mid(depth)
        if mid:
            hist.append(mid)

        fair = data.get("pepper_fair")
        if fair is None and len(hist) >= 10:
            sorted_h = sorted(hist[:20])
            fair = sorted_h[len(sorted_h) // 2]
            data["pepper_fair"] = fair

        if fair is None:
            return [], data

        pos = state.position.get(PEPPER, 0)
        spread = max(1, round(self._vol(hist[-20:]) * 2))

        bid_px = fair - spread
        ask_px = fair + spread

        # Skew quotes to reduce inventory
        if pos > 20:
            bid_px -= 1
            ask_px -= 1
        elif pos < -20:
            bid_px += 1
            ask_px += 1

        buy_cap  = LIMIT - pos
        sell_cap = LIMIT + pos

        result = []
        if buy_cap  > 0: result.append(Order(PEPPER, int(bid_px), min(10, buy_cap)))
        if sell_cap > 0: result.append(Order(PEPPER, int(ask_px), -min(10, sell_cap)))
        return result, data

    # ── ASH COATED OSMIUM: pattern trading ────────────────────────────────────

    def _trade_osmium(self, depth, state, data):
        hist = data.setdefault("osmium_hist", [])
        mid = self._mid(depth)
        if mid:
            hist.append(mid)

        if len(hist) < 20:
            return [], data

        pos = state.position.get(OSMIUM, 0)
        fair = self._ema(hist, alpha=0.2)

        # Bollinger z-score
        recent = hist[-20:]
        mu = statistics.mean(recent)
        sd = statistics.stdev(recent) + 1e-9
        z = (hist[-1] - mu) / sd

        # Autocorrelation regime
        rets = [hist[i] - hist[i-1] for i in range(1, len(hist[-21:]))]
        acf1 = self._acf1(rets)

        result = []
        if acf1 < -0.1:   # mean-reverting regime
            if z < -1.5 and pos < LIMIT:
                qty = min(15, LIMIT - pos)
                result.append(Order(OSMIUM, int(depth.sell_orders and min(depth.sell_orders) or fair + 2), qty))
            elif z > 1.5 and pos > -LIMIT:
                qty = min(15, LIMIT + pos)
                result.append(Order(OSMIUM, int(depth.buy_orders and max(depth.buy_orders) or fair - 2), -qty))
        elif acf1 > 0.1:  # trending regime — momentum
            rets5 = hist[-1] - hist[-6]
            if rets5 > 0 and pos < LIMIT - 10:
                result.append(Order(OSMIUM, int(min(depth.sell_orders or [fair + 1])), min(10, LIMIT - pos)))
            elif rets5 < 0 and pos > -LIMIT + 10:
                result.append(Order(OSMIUM, int(max(depth.buy_orders or [fair - 1])), -min(10, LIMIT + pos)))

        return result, data

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _mid(self, depth):
        if depth.buy_orders and depth.sell_orders:
            return (max(depth.buy_orders) + min(depth.sell_orders)) / 2
        return None

    def _ema(self, prices, alpha=0.2):
        v = prices[0]
        for p in prices[1:]: v = alpha * p + (1 - alpha) * v
        return v

    def _vol(self, prices):
        if len(prices) < 2: return 1
        diffs = [abs(prices[i] - prices[i-1]) for i in range(1, len(prices))]
        return statistics.mean(diffs) if diffs else 1

    def _acf1(self, rets):
        if len(rets) < 3: return 0
        mu = statistics.mean(rets)
        d = [r - mu for r in rets]
        num = sum(d[i] * d[i-1] for i in range(1, len(d)))
        den = sum(x**2 for x in d) + 1e-9
        return num / den

    def _load(self, td):
        try: return json.loads(td) if td else {}
        except: return {}

    def _save(self, data):
        s = json.dumps(data)
        return s[:45000] if len(s) > 45000 else s
```

## Key design decisions

| Decision | Reason |
|---|---|
| Separate `_trade_pepper` / `_trade_osmium` | Easy to enable/disable per round |
| traderData keyed by product | No cross-product state pollution |
| Inventory skew on PEPPER | Prevents position drift on MM book |
| Regime-conditional OSMIUM trading | Single strategy never works in all regimes |
| `s[:45000]` traderData trim | 50k limit — leave 5k headroom |

## Common bugs to avoid

```python
# WRONG — sell order quantities must be negative
orders.append(Order(product, price, qty))  # if qty > 0 this is a BUY

# RIGHT
orders.append(Order(product, price, -qty))  # negative = sell

# WRONG — sell_orders values are already negative in the book
best_ask = min(depth.sell_orders)  # correct key access
ask_vol = depth.sell_orders[best_ask]  # this is NEGATIVE, negate it for sizing

# RIGHT
ask_vol = -depth.sell_orders[best_ask]
```
