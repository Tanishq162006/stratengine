# IMC Prosperity 4 — Round Hints & Observations

## Round 1 Hints

_(Source: Rook-E1 in-game advisor — official IMC Prosperity 4 hints)_

### Auction mechanics (manual round)
- Clearing price rule: **maximum traded volume first, then highest price wins ties**
- Your order affects the clearing price itself — account for this when sizing
- Simulate: change size, change price, observe how clearing price responds
- Find the price level where volume concentrates — that is the defensible position
- "Look for the point where volume almost shifts the clearing level. Then add just enough to keep the level intact."

### INTARIAN_PEPPER_ROOT character
- Grows slowly — supply and demand move in a **controlled, predictable manner**
- Fewer viable market paths than volatile products → easier to estimate fair value
- Use historical data to narrow possibilities; you don't need to predict every outcome, just rule out enough
- Fair value is a **reference point**, not a conclusion — measure it against current bids/asks

### Strategic order placement
- Profit comes from being **selected**, not just being correct
- Order must be attractive enough to match but not so generous it collapses your edge
- Price, size, and timing all influence whether you get matched
- "If you want to sell, ask why a buyer would choose your offer over the one already waiting"
- Iterate one variable at a time — nudge price toward the other side until you become interesting
- Adjust size: too small = ignored, too large = scares the book or reveals your structure

### Volume as the decisive variable
- In the auction: volume decides first, price follows
- Add volume at the right level and the balance tips "quietly, decisively"
- "Too little volume and nothing happens. Too much and you give away structure."
- The useful range is **narrow** — focus required

## Round 2 Hints

_(Source: Rook-E1 in-game advisor — official IMC Prosperity 4 hints)_

### MAF — cost vs advantage framing
- "This is not a market valuation problem. It is a **cost-versus-advantage problem**."
- Calculate the break-even: at what volume does extra access equal the cost of obtaining it?
- If `fee > value of extra flow` → not worth bidding. If `fee < value` → bid.
- Include the fee in your effective cost calculation before deciding

### MAF — predicting the median (game theory)
- "The question shifts: not what is access worth to me, but **what do others think it is worth to them**"
- Underestimate the field → lose access (tempo lost, unrecoverable)
- Overestimate the field → win access but at a cost that collapses the advantage
- Cautious field compresses median downward; aggressive field pushes it up
- "Anticipate where the median lands. Then decide whether beating it at that price still creates real value."

### MAF — risk and bid placement
- You only need to finish top 50% — **not** be the highest bidder
- "Bid high = blunder dressed as caution" — if you could have secured access for fewer XIRECs, the excess was waste
- Calculate: how low can you bid while remaining confident you clear the median?
- Closer to threshold = more efficient but smaller margin for error
- "Not at the ceiling. Not recklessly close to the floor. Somewhere deliberate. Somewhere defensible."

### MAF — do NOT assume cooperation
- If many participants value access similarly, median stabilizes and looks predictable — **this is a trap**
- One participant deviating shifts the threshold you positioned against
- "How much of this strategy depends on others continuing to act as expected? That dependency is not a calculated position. It is an assumption."
- **Trust the calculation. Not the consensus.**

### Algorithm notes for Round 2
- Same products and limits as Round 1 (limit 80 each)
- With extra access: 25% more tradeable volume → larger position opportunities, more fills
- Analyze Round 1 performance data before submitting Round 2 — refine fair value estimates

## Round 3 Hints

_Paste Round 3 hints here when available._

## Cross-Round Patterns

- Phase 1 (Rounds 1-2) = qualifier: need ≥200,000 XIRECs net PnL to advance
- Phase 2 (Rounds 3-5) = final mission (leaderboard resets)
- Both rounds use INTARIAN_PEPPER_ROOT and ASH_COATED_OSMIUM — build stable, well-tuned algos
- New mechanics introduced each round (Round 2: MAF bid, Invest&Expand)
- Round 3 likely introduces new products or market structures (baskets, conversions, options historically)
