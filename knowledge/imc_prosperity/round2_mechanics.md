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
- Top 50% of bids across all teams → get 25% more order book quotes (extra flow fits naturally into the distribution).
- Your bid is **deducted from your Round 2 PnL** if accepted.
- If rejected (below median), you pay nothing and get standard order flow.
- During **testing**, `bid()` is ignored — you see 80% of quotes (slightly randomized).

### PnL formula
```
If bid accepted:   PnL = round2_profit - bid
If bid rejected:   PnL = round2_profit
Negative bids → treated as 0 (you can't earn from a negative bid)
```

### Optimal bidding strategy

```python
# Game-theoretic target: bid just above the median competitor bid.
# Overbidding wastes XIRECs. Underbidding loses extra volume.

# Estimate value of extra 25% flow:
# extra_value ≈ 0.25 * round1_profit_from_taking (approx)

# If extra_value > expected_median_bid → worth bidding above median
# Start with a moderate bid (e.g. 2000-5000 XIRECs) and adjust.

def bid(self):
    return 3000   # tune based on your round 1 PnL from taking
```

### Key rules
- MAF is **unique to Round 2** — `bid()` is ignored in all other rounds.
- Median is computed only from teams that submitted a trader.py (no submission = bid of 0).
- Equal bids share rank; all above median get accepted.

---

## Manual: Invest & Expand

Budget: **50,000 XIRECs** split across Research (R), Scale (S), Speed (V) as percentages 0-100 (total ≤ 100).

```
PnL = research(R%) * scale(S%) * speed(V%) - budget_used

research(x) = 200_000 * ln(1 + x) / ln(101)   # logarithmic, max 200k at x=100
scale(x)    = 7 * x / 100                       # linear, max 7 at x=100
speed       = rank-based [0.1, 0.9]             # competitive across all teams
budget_used = 50_000 * (R + S + V) / 100
```

### Strategy

```python
import numpy as np

def optimal_split(n_competitors=500, your_speed_pct=70):
    # Research is logarithmic — diminishing returns, front-load it
    # Scale is linear — straightforward
    # Speed is competitive rank — need to beat ~50% of teams

    # Approximate: spend 60% research, 30% scale, 10% speed
    # unless you believe most teams will ignore speed (then spike speed)

    R, S, V = 60, 30, 10
    budget_used = 50_000 * (R + S + V) / 100

    research = 200_000 * np.log(1 + R) / np.log(101)
    scale    = 7 * S / 100
    # speed depends on rank — assume ~0.5 for median speed
    speed    = 0.5

    gross = research * scale * speed
    net   = gross - budget_used
    return R, S, V, net

# Key insight: Speed is zero-sum. If everyone spends 10% on speed,
# the distribution is flat and rank just reflects tiny differences.
# If you're willing to sacrifice Research/Scale, a high Speed bet
# can pay off if it moves your rank from 0.5 → 0.9.
```

### Do NOT exceed 100% total
```python
assert R + S + V <= 100, "Budget constraint violated"
```
