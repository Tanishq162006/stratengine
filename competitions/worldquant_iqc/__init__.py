"""WorldQuant IQC plugin.

No custom backtest harness — BRAIN expressions are evaluated on the WQ
platform, not locally. This plugin intentionally returns None so the engine
falls back to the default Backtrader path for local validation scaffolding.
"""
# No plugin registered — engine uses default path.
