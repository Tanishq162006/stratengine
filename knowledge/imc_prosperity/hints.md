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

_(Source: Rook-E1 in-game advisor — official IMC Prosperity 4 hints)_

### VEV Options — Implied Volatility and Moneyness (Rook-E1 Card 1)
- VEV vouchers are European call options. Surface price conceals the real information — extract **Implied Volatility** via Black-Scholes for each voucher.
- Run BS across ALL available vouchers. Observe how IV varies across strikes (moneyness) and time.
- Map IV against **moneyness** = (strike − underlying_mid) / underlying_mid. The resulting shape is the "IV structure" (volatility smile/skew).
- Every deviation from a clean, smooth curve is a signal — a voucher priced inconsistently with its neighbors.
- IV structure reveals the market's current POSITION, not its forecast. Understand it before acting.

### VEV Options — Positioning With IV and Moneyness (Rook-E1 Card 2)
- Ask: does the IV distribution hold (smooth curve)?
  - **Consistent structure** → market pricing uncertainty evenly → use one shared IV for all strikes
  - **Outlier strike** → either market overestimates uncertainty (sell that voucher) or underestimates it (buy it)
- A voucher implying significantly MORE IV than its neighbors → **overpriced vol → SELL**
- A voucher implying significantly LESS IV than its neighbors → **underpriced vol → BUY**
- Like a hanging piece in chess: not every deviation is an opportunity — some are traps or noise.
- Rule: **Buy underpriced vol. Sell overpriced vol. Hold if edge is insufficient.**

### VEV Options — Volume (Sizing) (Rook-E1 Card 3)
- Volume = commitment. Commitment without calibration is not strategy.
- Size PROPORTIONALLY to deviation magnitude: small deviation → small position, large deviation → larger position.
- Larger volume amplifies returns when right AND amplifies losses when wrong.
- Run honest conviction assessment: How confident is the reading? How much can you afford to lose if structure shifts?
- Rule: **Volume should reflect the strength of your conviction. Nothing more. Nothing less.**

### VEV Options — TTE and Black-Scholes (UPDATED from official wiki)
- **CONFIRMED**: TTE = 5 trading days at Round 3 start (live competition).
- Historical training data has DIFFERENT TTE: day 0=8d, day 1=7d, day 2=6d
  (these are tutorial / Round 1 / Round 2 historical days, NOT Round 3)
- Each Solvenarian day = 48 hours, IMC simulator day = 10,000 timestamps.
- TTE decrements by 1 day each time `state.timestamp` resets to 0.
- **Live Round 3 schedule:**
  - Day 0 of Round 3 (live start): TTE = 5/252
  - Day 1: TTE = 4/252
  - Day 2: TTE = 3/252
- Use r=0 (no risk-free rate in IMC).
- **IV evolution across historical days (NOT Round 3 — these are days 0/1/2 of training):**
  - Historical day 0 (TTE=8/252): IV ≈ 0.23
  - Historical day 1 (TTE=7/252): IV ≈ 0.213
  - Historical day 2 (TTE=6/252): IV ≈ 0.20
- **At live Round 3 (TTE=5/252) prior:** σ ≈ 0.20 (extrapolated)
- Smile is essentially FLAT across liquid strikes at TTE=6+. May steepen as
  TTE → 0 due to gamma sensitivity.
- Empirical deltas match BS within 0.01 — pricing is correct, deltas reliable.

### VEV Options — Practical Implementation
1. Calculate IV for EACH voucher from its observable mid price.
2. Fit smooth curve (polynomial or running mean) to IV vs moneyness.
3. Identify outlier vouchers where actual_IV deviates from fitted_IV by > threshold.
4. Buy underpriced (actual_IV << fitted) / Sell overpriced (actual_IV >> fitted).
5. Size proportional to deviation: qty ∝ |actual_IV - fitted_IV| / sigma_of_deviations.
6. Delta-hedge using VELVETFRUIT_EXTRACT to stay delta-neutral across the options book.

### HYDROGEL_PACK
- Stable value product ~10,000 XIRECs. Position limit 200.
- Range in data: 9891–10079. Treat like INTARIAN_PEPPER_ROOT — pure inventory-skewed market making.
- Fair value = rolling mid or hard-coded 10000. Spread 2-4 ticks. Skew aggressively on inventory.

### VELVETFRUIT_EXTRACT
- Underlying for VEV options. Position limit 200. Price ~5250, range 5198–5300.
- Use as delta-hedge instrument for options book. Also market-make independently.
- Key: VELVETFRUIT_EXTRACT mid is THE input S to Black-Scholes for all VEV vouchers.

### Bio-Pod Manual Challenge — CONFIRMED STRUCTURE
- N counterparties (secret N), each with independent reserve price ~ Uniform{670,675,...,920} (51 values, step 5).
- You trade with **ALL counterparties whose reserve < your bid** (not just one). Sell all at 920 next day.
- Each Guardener accepts the **lowest bid that exceeds their reserve**. So bid1 (lower) catches low-reserve counterparties; bid2 (higher) catches mid-reserve counterparties that bid1 misses.
- 4100 competing teams.

**Bid structure:**
- Bid1 = Low bid: catches reserves in {670,...,bid1−1}. You pay bid1 per unit. Profit = 920−bid1 per unit.
- Bid2 = High bid: catches reserves in {bid1,...,bid2−1}. You pay bid2 per unit. Profit = 920−bid2 per unit.
  - If bid2 > avg_b2 → clean trade. If bid2 ≤ avg_b2 → penalty = ((920−avg_b2)/(920−bid2))³ applied to PnL.

**Joint optimization (maximize total expected profit):**
```
E = (bid1−670)/5 × (920−bid1)  +  (bid2−bid1)/5 × (920−bid2)
Continuous optimum: bid1* = 753,  bid2* = 837  → E = 4167 units
```

**⚠️ CRITICAL: bid1=795 (single-bid optimum) is WRONG for two-bid structure.**
- bid1=795, bid2=840 → E=3845 (−8% vs optimal)
- bid1=753, bid2=837 → E=4167 (joint optimum)

**Recommended bids:**
- **Bid 1 = 753** (or 755 if integers must be step-5)
- **Bid 2 = 840** (one step above Nash equilibrium ~837, small buffer against competitive penalty)

**Why bid2=840 not 837?** At bid2=avg_b2 penalty factor = 1 (no penalty). But with 4100 teams and heterogeneous strategies, avg_b2 may drift slightly. 840 provides 3 XIREC buffer. Cost: 1 less counterparty on bid2 vs 837. Worth it.

## Round 4 Hints

_(Source: Rook-E1 in-game advisor — official IMC Prosperity 4 hints)_

### Exotic Options — Binary Put and Knock-Out Put (Rook-E1)

**Binary put structure:**
- Defined by a single threshold. Above threshold = 0 payoff. Below threshold = full payoff.
- "That abrupt discontinuity creates a fundamentally different risk profile compared to a standard put."
- Risk is concentrated entirely at the threshold, not distributed across a range.
- Pricing: `N(-d2)` in Black-Scholes (cash-or-nothing, pays 1 if S_T < K).

**Knock-out put structure:**
- Value can be "eliminated entirely depending on the path the underlying takes."
- Path-dependent: a position that looks sound at entry can cease to exist before resolution.
- The trigger is a barrier level — if S touches barrier at ANY point, option is knocked out.
- "I have run that scenario 212 times. It still bothers me." = path dependency is the key risk.
- Pricing: `bs_knockout_put(S,K,T,σ,B)` = vanilla_put - (B/S)^{2λ} * put(B²/S, K, T, σ) at r=0.

**Hedging advice (actionable):**
- Use vanilla options to offset the extreme scenarios of exotic payoffs.
- A vanilla position can "soften the abrupt payoff cliff of the binary."
- A vanilla position can "provide a buffer against the knock-out trigger before it becomes irreversible."
- "A payoff you can model clearly under adverse conditions is worth considerably more than an elegant one that fails without warning."
- Restructuring changes the payoff shape but improves risk visibility — worth it.

**Strategic principle:**
- "When payoffs are discontinuous, risk management becomes structural rather than occasional."
- Do not rely on reactive stop-losses near a binary threshold.
- Construct positions so the adverse scenario is bounded and visible before entry.

**Implementation notes:**
- Binary put replication via vanilla put spread: `(put(K) - put(K-δ)) / δ → binary_put(K)` as δ→0
- Use call-put parity to derive puts from our VEV calls if no put products exist
- Vertical call spread can bound the payoff of any exotic position

## Cross-Round Patterns

- Phase 1 (Rounds 1-2) = qualifier: need ≥200,000 XIRECs net PnL to advance
- Phase 2 (Rounds 3-5) = final mission (leaderboard resets)
- Both rounds use INTARIAN_PEPPER_ROOT and ASH_COATED_OSMIUM — build stable, well-tuned algos
- New mechanics introduced each round (Round 2: MAF bid, Invest&Expand)
- Round 3 likely introduces new products or market structures (baskets, conversions, options historically)
