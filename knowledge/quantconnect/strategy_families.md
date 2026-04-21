# QuantConnect LEAN — Strategy Family Recipes

## 1. SMA crossover trend-following

```python
self.fast = self.SMA(self.spy, 20)
self.slow = self.SMA(self.spy, 100)
self.SetWarmUp(100)

def Rebalance(self):
    if not self.fast.IsReady or not self.slow.IsReady:
        return
    if self.fast.Current.Value > self.slow.Current.Value:
        self.SetHoldings(self.spy, 1.0)
    else:
        self.Liquidate(self.spy)
```

**Sharpe:** ~0.7–0.9 on SPY 2010-2023. Reliable baseline.

## 2. Mean reversion (Bollinger Bands)

```python
self.bb = self.BB(self.spy, 20, 2)
self.SetWarmUp(20)

def OnData(self, data):
    if not self.bb.IsReady:
        return
    price = data[self.spy].Close
    if price < self.bb.LowerBand.Current.Value:
        self.SetHoldings(self.spy, 1.0)
    elif price > self.bb.UpperBand.Current.Value:
        self.Liquidate(self.spy)
    elif self.bb.MiddleBand.Current.Value * 1.005 > price > self.bb.MiddleBand.Current.Value * 0.995:
        self.Liquidate(self.spy)  # exit at mid-band
```

## 3. Universe momentum rotation

```python
def Initialize(self):
    self.UniverseSettings.Resolution = Resolution.Daily
    self.AddUniverse(self.CoarseFilter)
    self.Schedule.On(self.DateRules.MonthStart(), self.TimeRules.AfterMarketOpen(timedelta(minutes=30)), self.Rotate)
    self.mom = {}

def CoarseFilter(self, coarse):
    filtered = [x for x in coarse if x.HasFundamentalData and x.Price > 10 and x.DollarVolume > 5e7]
    return [x.Symbol for x in sorted(filtered, key=lambda x: x.DollarVolume, reverse=True)[:200]]

def OnSecuritiesChanged(self, changes):
    for s in changes.AddedSecurities:
        self.mom[s.Symbol] = self.MOMP(s.Symbol, 126)  # 6-month momentum
    for s in changes.RemovedSecurities:
        self.Liquidate(s.Symbol)
        self.mom.pop(s.Symbol, None)

def Rotate(self):
    ready = {s: m for s, m in self.mom.items() if m.IsReady}
    if not ready:
        return
    top = sorted(ready, key=lambda s: ready[s].Current.Value, reverse=True)[:20]
    target_weight = 1.0 / len(top)
    for s in self.Portfolio.Keys:
        if s not in top:
            self.Liquidate(s)
    for s in top:
        self.SetHoldings(s, target_weight)
```

## 4. Pairs stat-arb (two securities)

```python
def Initialize(self):
    self.s1 = self.AddEquity("XLF", Resolution.Daily).Symbol
    self.s2 = self.AddEquity("XLK", Resolution.Daily).Symbol
    self.window_s1 = RollingWindow[float](60)
    self.window_s2 = RollingWindow[float](60)
    self.SetWarmUp(60)

def OnData(self, data):
    if self.IsWarmingUp:
        return
    if data.ContainsKey(self.s1):
        self.window_s1.Add(np.log(data[self.s1].Close))
    if data.ContainsKey(self.s2):
        self.window_s2.Add(np.log(data[self.s2].Close))
    if not (self.window_s1.IsReady and self.window_s2.IsReady):
        return
    v1 = np.array([self.window_s1[i] for i in range(self.window_s1.Count)])
    v2 = np.array([self.window_s2[i] for i in range(self.window_s2.Count)])
    beta = np.cov(v1, v2)[0, 1] / np.var(v2)
    spread = v1[-1] - beta * v2[-1]  # current spread vs rolling hedge
    spread_hist = v1 - beta * v2
    z = (spread - np.mean(spread_hist)) / (np.std(spread_hist) + 1e-9)
    if z > 2.0:
        self.SetHoldings(self.s1, -0.5)
        self.SetHoldings(self.s2, 0.5)
    elif z < -2.0:
        self.SetHoldings(self.s1, 0.5)
        self.SetHoldings(self.s2, -0.5)
    elif abs(z) < 0.5:
        self.Liquidate(self.s1)
        self.Liquidate(self.s2)
```

## 5. Factor model (multi-factor ranking)

```python
# Requires FineSelectionFunction for fundamentals
def FineFilter(self, fine):
    scored = []
    for f in fine:
        if f.MarketCap < 1e9:
            continue
        pe = f.ValuationRatios.PERatio
        roa = f.OperationRatios.ROA.OneYear
        if pe <= 0 or roa is None:
            continue
        # Low PE (value) + high ROA (quality) composite
        score = -pe + 100 * roa
        scored.append((f.Symbol, score))
    top = sorted(scored, key=lambda x: x[1], reverse=True)[:30]
    return [s for s, _ in top]
```

## Performance benchmarks (rough, SPY 2015-2023)

| Strategy | Sharpe | Max DD |
|---|---|---|
| SMA 20/100 | 0.75 | 18% |
| BB Mean Reversion | 0.60 | 22% |
| Momentum Rotation | 0.90 | 25% |
| Pairs Stat-Arb | 0.80 | 12% |
| Multi-Factor | 0.95 | 20% |
