# IMC Prosperity 4 — Round 2 Mechanics

## Market Access Fee (MAF)

Round 2 introduces a `bid()` method on the Trader class:

```python
class Trader:
    def bid(self):
        return 500   # XIRECs — your blind auction bid for extra market access

    def run(self, state: TradingState):
        ...
```

### How it works
- Top 50% of bids → get 25% more order book quotes (extra flow fits naturally into the distribution).
- Your bid is **deducted from your Round 2 PnL** if accepted.
- If rejected (below median), you pay nothing and get standard order flow.
- During **testing**, `bid()` is ignored — you see 80% of quotes (slightly randomized per submission).
- Median computed from ALL submitted trader.py files; no `bid()` function = bid of 0.
- Negative bids are treated as 0.

### PnL formula
```
If bid accepted:   PnL = round2_profit - bid
If bid rejected:   PnL = round2_profit
Negative bids → treated as 0
```

### What extra market access looks like

```
Standard order book:
  ask 10 @ $9
  ask 10 @ $7
  bid 10 @ $5
  bid  5 @ $4

With extra access (25% more volume inserted at natural price levels):
  ask 10 @ $9
  ask  5 @ $8   ← extra flow
  ask 10 @ $7
  bid 10 @ $5
  bid  5 @ $4
```

### Optimal bidding strategy

Most teams either omit `bid()` entirely (counts as 0) or bid very conservatively.
The median is almost certainly low — likely under 1000 XIRECs.

```python
# Game-theoretic target: just above the estimated median.
# Overbidding guarantees access but wastes XIRECs.
# Underbidding saves XIRECs but loses 25% extra volume.

# Value of extra 25% flow ≈ 0.25 × your round2 profit from taking
# If round2 profit ~10,000 → extra value ~2,500 → bid up to ~2,500

def bid(self):
    return 500   # conservative — likely beats median easily
```

### Key rules
- MAF is **unique to Round 2** — `bid()` is ignored in all other rounds.
- `bid()` is NOT evaluated during testing — only on final Round 2 simulation.
- Teams with no trader.py submission excluded from median calculation.
- Equal bids share rank; all strictly above median are accepted.

---

## Manual: Invest & Expand

Budget: **50,000 XIRECs** split across Research (R), Scale (S), Speed (V) as integer percentages 0-100 (total ≤ 100).

```
PnL = research(R%) × scale(S%) × speed_multiplier − budget_used

research(x) = 200_000 × ln(1 + x) / ln(101)   # logarithmic, max 200k at x=100
scale(x)    = 7 × x / 100                       # linear, max 7.0 at x=100
speed       = rank-based multiplier [0.1 → 0.9] # competitive across all teams
budget_used = 50_000 × (R + S + V) / 100
```

### Speed rank mechanics
- Highest speed investment → 0.9 multiplier
- Lowest → 0.1 multiplier
- Linear interpolation between ranks
- Equal investments share the same rank

```python
# Example: investments [70, 70, 70, 50, 40, 40, 30]
# Ranks:               [ 1,  1,  1,  4,  5,  5,  7]
# Multipliers:         [0.9,0.9,0.9, ?, 0.1,0.1, ?] → interpolated
```

### Optimizer

```python
import numpy as np

def pnl(R, S, V, speed_multiplier):
    research = 200_000 * np.log(1 + R) / np.log(101)
    scale    = 7 * S / 100
    budget   = 50_000 * (R + S + V) / 100
    return research * scale * speed_multiplier - budget

# Sweep allocations — find best split given expected speed rank
best = (-1e9, 0, 0, 0)
for R in range(0, 101, 5):
    for S in range(0, 101-R, 5):
        for V in range(0, 101-R-S, 5):
            # Assume speed_multiplier depends on how aggressively others bid
            # Conservative: assume you land ~0.5 (median rank)
            net = pnl(R, S, V, speed_multiplier=0.5)
            if net > best[0]:
                best = (net, R, S, V)

print(f"Best: R={best[1]}% S={best[2]}% V={best[3]}% → PnL≈{best[0]:,.0f}")
```

### Key insights
1. **Research** has logarithmic diminishing returns — front-loading past ~40% gives little extra edge
2. **Scale** is purely linear — always efficient per XIREC
3. **Speed** is zero-sum competitive — if most teams ignore it, a small spend wins high rank cheaply
4. Unspent budget (allocations < 100%) is NOT penalized — you keep unspent XIRECs

### Example allocations

| Strategy | R | S | V | Notes |
|---|---|---|---|---|
| Balanced | 40 | 35 | 25 | Reasonable defaults |
| Speed aggressive | 30 | 30 | 40 | Bet that competitors underspend speed |
| Research heavy | 60 | 30 | 10 | If speed competition is fierce |
| Conservative | 35 | 35 | 20 | Keep 10% unspent |

### Do NOT exceed 100% total
```python
assert R + S + V <= 100, "Budget constraint violated"
```
