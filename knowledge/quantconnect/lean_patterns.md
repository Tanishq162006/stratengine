# QuantConnect LEAN — Key Patterns and Gotchas

## Mandatory warm-up pattern

```python
def Initialize(self):
    self.SetWarmUp(200)   # enough bars for your slowest indicator
    self.sma200 = self.SMA(self.spy, 200)

def OnData(self, data):
    if self.IsWarmingUp or not self.sma200.IsReady:
        return
    # Safe to use indicator values now
```

Never skip `IsReady` gate — first bars feed garbage values.

## Portfolio target approach (preferred)

```python
# Let LEAN handle sizing math — SetHoldings calculates qty automatically
self.SetHoldings("SPY", 1.0)    # 100% long
self.SetHoldings("SPY", -0.5)   # 50% short
self.SetHoldings("SPY", 0.0)    # flat
self.Liquidate("SPY")           # close position immediately
```

Only roll your own `MarketOrder(symbol, qty)` when you need explicit lot control.

## Scheduled rebalancing

```python
# Daily, 15 min after open (avoids gap fills)
self.Schedule.On(
    self.DateRules.EveryDay(self.spy),
    self.TimeRules.AfterMarketOpen(self.spy, 15),
    self.Rebalance
)

# Monthly rotation
self.Schedule.On(
    self.DateRules.MonthStart(self.spy),
    self.TimeRules.AfterMarketOpen(self.spy, 30),
    self.Rotate
)
```

## Dynamic universe selection

```python
def CoarseSelectionFunction(self, coarse):
    # Filter for liquid, priced names — run monthly or weekly
    filtered = [x for x in coarse
                if x.HasFundamentalData
                and x.Price > 5
                and x.DollarVolume > 1e7]
    sorted_by_vol = sorted(filtered, key=lambda x: x.DollarVolume, reverse=True)
    return [x.Symbol for x in sorted_by_vol[:100]]

def OnSecuritiesChanged(self, changes):
    for s in changes.RemovedSecurities:
        self.Liquidate(s.Symbol)
    for s in changes.AddedSecurities:
        self.sma[s.Symbol] = self.SMA(s.Symbol, 20, Resolution.Daily)
```

## Rolling window for custom indicators

```python
def Initialize(self):
    self.window = RollingWindow[float](20)
    self.Consolidate(self.spy, timedelta(days=1), self.OnDailyBar)

def OnDailyBar(self, bar):
    self.window.Add(bar.Close)
    if not self.window.IsReady:
        return
    values = [self.window[i] for i in range(self.window.Count)]
    std = np.std(values)
    # Use std for Bollinger-style gating
```

## Risk overlay pattern

```python
def Initialize(self):
    self.peak_value = self.Portfolio.TotalPortfolioValue
    self.halt = False

def OnEndOfDay(self, symbol):
    value = self.Portfolio.TotalPortfolioValue
    self.peak_value = max(self.peak_value, value)
    drawdown = (self.peak_value - value) / self.peak_value
    if drawdown > 0.05:   # 5% drawdown → halt new trades
        self.halt = True
        self.Liquidate()

def Rebalance(self):
    if self.halt:
        return
    # Normal logic here
```

## Framework (Alpha + Portfolio + Risk + Execution)

```python
class MyAlgo(QCAlgorithm):
    def Initialize(self):
        ...
        self.AddAlpha(MomentumAlphaModel())
        self.SetPortfolioConstruction(EqualWeightingPortfolioConstructionModel())
        self.SetRiskManagement(MaximumDrawdownPercentPerSecurity(0.05))
        self.SetExecution(ImmediateExecutionModel())
```

Use framework for multi-asset strategies — avoids spaghetti in OnData.

## Common mistakes

- Using `History()` inside `OnData` every bar → latency balloon. Cache via rolling windows.
- `datetime.now()` → always wrong in backtest. Use `self.Time`.
- Hard-coding tickers for strategies meant to scale → use `AddUniverse`.
- Missing `SetWarmUp` when using indicators with 200+ day windows.
- Not setting `SetBrokerageModel` — default has no realistic fills/slippage.
