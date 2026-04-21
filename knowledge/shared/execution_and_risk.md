# Execution & Risk Management — Advanced Quant Reference

## Position sizing: Kelly criterion

```python
def kelly_size(edge, odds, max_fraction=0.25):
    """
    edge  = probability of winning (0.5–1.0)
    odds  = net profit per unit risked (e.g. 1.0 = even money)
    Returns fraction of capital to bet, capped at max_fraction.
    """
    f = (edge * (odds + 1) - 1) / odds
    return max(0.0, min(f, max_fraction))

# Practical: halve Kelly for live use (half-Kelly)
# Full Kelly maximises geometric growth but has huge drawdowns
size = kelly_size(0.55, 1.0) * 0.5
```

## Stop-loss disciplines

```python
# Hard stop: exit immediately if loss exceeds threshold
HARD_STOP_PNL = -500  # per product per round

def check_stop(pnl, position, fair, product):
    if pnl < HARD_STOP_PNL:
        return True  # flatten position
    # Soft stop: stop adding if drawdown > half limit
    unrealized = position * (fair - entry_price)
    if unrealized < HARD_STOP_PNL / 2:
        return True  # stop entering new positions
    return False
```

## Adverse selection protection

```python
def is_toxic_flow(market_trades, window=3):
    """Widen spread or stop quoting if last N trades all hit same side."""
    if len(market_trades) < window:
        return False
    directions = []
    for trade in market_trades[-window:]:
        directions.append(1 if trade.buyer == "SUBMISSION" else -1)
    # All same direction = possible informed trader
    return abs(sum(directions)) == window

# If toxic: skip market making this tick
if is_toxic_flow(state.market_trades.get(product, [])):
    return []  # no quotes
```

## Inventory limits and target

```python
def inventory_target(tick, total_ticks=1000):
    """Ramp down target inventory as round ends."""
    time_left = (total_ticks - tick) / total_ticks
    if time_left > 0.2:
        return 0   # normal: target flat
    elif time_left > 0.05:
        return 0   # reduce: lean toward flat
    else:
        return 0   # end-of-round: must be flat

def urgency_size(position, ticks_left, limit=80):
    """Increase size to unwind as time runs out."""
    if ticks_left > 50:
        return 5   # normal passive size
    elif ticks_left > 10:
        return abs(position) // 2 + 1   # more aggressive
    else:
        return abs(position)   # full unwind
```

## Risk-off trigger

```python
class RiskMonitor:
    def __init__(self, max_drawdown=1000, max_pos=80):
        self.peak_pnl = 0
        self.max_drawdown = max_drawdown
        self.max_pos = max_pos

    def is_risk_off(self, current_pnl, position):
        self.peak_pnl = max(self.peak_pnl, current_pnl)
        drawdown = self.peak_pnl - current_pnl
        if drawdown > self.max_drawdown:
            return True  # stop trading
        if abs(position) >= self.max_pos * 0.95:
            return True  # near limit
        return False
```

## Spread management under uncertainty

```python
def adaptive_spread(vol_estimate, informed_probability, base_spread=2):
    """
    Widen spread when:
    - Volatility is high (inventory risk)
    - Informed trader probability is high (adverse selection)
    """
    vol_adjustment = vol_estimate * 2
    adverse_adjustment = informed_probability * 4
    return max(base_spread, vol_adjustment + adverse_adjustment)
```

## The 5 risk rules

1. **Size down in new regimes** — halve position size until you have 20+ ticks of data
2. **Never catch a falling knife** — don't buy into sustained downtrend expecting reversal
3. **Correlation risk** — if two products are correlated, combined limit is not 2×
4. **End-of-round inventory** — unrealized PnL means nothing; only settled positions count
5. **Latency cascade** — a slow algorithm that misses ticks bleeds slowly; detect timeout and reduce logic
