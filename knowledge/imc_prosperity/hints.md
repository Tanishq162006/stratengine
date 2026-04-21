# IMC Prosperity 4 — Round Hints & Observations

## Round 1 Hints

_Paste Round 1 hints here when available._

## Round 2 Hints

### MAF bid() strategy
- Top 50% of bids get extra market access (25% more order book volume)
- Median is computed from ALL submitted trader.py files; no bid() = bid of 0
- **You only need to beat the median — not maximize your bid**
- Negative bids are treated as 0
- MAF is a one-time deduction: `final_PnL = round2_profit - bid_if_accepted`
- During testing: only 80% of quotes available (slightly randomized per submission)
- Extra quotes fit perfectly into existing book distribution — same price/volume pattern

**Optimal MAF reasoning:**
Most teams will bid conservatively or not at all (bid=0). A bid of ~100-500 XIRECs likely beats the median easily. Overbidding (e.g. 10,000) guarantees access but costs you. Target: just above estimated median.

**Expected median estimate:** Most participants bid 0 (no bid function) or low amounts. A bid of 200-500 XIRECs is likely sufficient to land in top 50%.

### Invest & Expand optimal allocation
PnL formula: `Research(r) × Scale(s) × Speed_multiplier − Budget_used`

Where:
- `research(x) = 200_000 * log(1+x) / log(101)` — logarithmic, diminishing returns
- `scale(x) = 7 * x / 100` — perfectly linear
- `speed` = rank-based multiplier 0.1–0.9 based on your % vs all players

**Key insight:** Speed is rank-based (competitive), Scale is linear (predictable), Research is logarithmic (heavy diminishing returns above ~40%).

**Optimal strategy reasoning:**
- Research has logarithmic returns → don't go all-in on research past ~40-50%
- Scale is linear → pure value per XIREC, always good
- Speed is zero-sum competitive → if everyone underspends speed, you can win it cheaply
- Budget_used = sum of your allocations × 500 XIRECs per percent
- Target: high speed (beat competitors), moderate scale, moderate research

**Example allocation to model:** Speed=40%, Scale=35%, Research=25% — adjust based on expected competitor behavior

### Algorithm notes
- Same products and limits as Round 1 (limit 80 each)
- With extra market access: 25% more tradeable volume → larger position opportunities
- Refine algorithm from Round 1 performance data before submitting

## Round 3 Hints

_Paste Round 3 hints here when available._

## Cross-Round Patterns

- Phase 1 (Rounds 1-2) = qualifier: need ≥200,000 XIRECs net PnL to advance
- Phase 2 (Rounds 3-5) = final mission (leaderboard resets)
- Both rounds use INTARIAN_PEPPER_ROOT and ASH_COATED_OSMIUM — build stable, well-tuned algos
- New mechanics introduced each round (Round 2: MAF bid, Invest&Expand)
- Round 3 likely introduces new products or market structures (baskets, conversions, options historically)
