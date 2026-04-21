"""IMC Prosperity simulator harness.

Replays a Trader class against OHLCV price data, constructing synthetic
TradingState objects each tick and collecting PnL. Outputs STRATENGINE_STATS
so the standard evaluator pipeline can score IMC Prosperity submissions.

Usage (standalone script — called by evaluator):
    python imc_simulator.py --code trader.py --data prices.csv \\
        --start 2024-04-08 --end 2024-04-14 --products KELP,SQUID_INK
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import sys
import tempfile
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Minimal datamodel shim (mirrors the real IMC Prosperity datamodel)
# ---------------------------------------------------------------------------

class Order:
    def __init__(self, symbol: str, price: int, quantity: int):
        self.symbol = symbol
        self.price = price
        self.quantity = quantity

    def __repr__(self):
        return f"Order({self.symbol}, {self.price}, {self.quantity})"


class OrderDepth:
    def __init__(self):
        self.buy_orders: Dict[int, int] = {}
        self.sell_orders: Dict[int, int] = {}


class ConversionObservation:
    def __init__(self, bid, ask, transport, export_tariff, import_tariff, sunlight=1000, sugar=300):
        self.bidPrice = bid
        self.askPrice = ask
        self.transportFees = transport
        self.exportTariff = export_tariff
        self.importTariff = import_tariff
        self.sunlightIndex = sunlight
        self.sugarPrice = sugar


class Observation:
    def __init__(self):
        self.conversionObservations: Dict[str, ConversionObservation] = {}


class TradingState:
    def __init__(
        self,
        timestamp: int,
        order_depths: Dict[str, OrderDepth],
        position: Dict[str, int],
        observations: Observation,
        trader_data: str = "",
        own_trades: Dict[str, list] = None,
        market_trades: Dict[str, list] = None,
        listings: Dict[str, object] = None,
    ):
        self.timestamp = timestamp
        self.order_depths = order_depths
        self.position = position
        self.observations = observations
        self.traderData = trader_data
        self.own_trades = own_trades or {}
        self.market_trades = market_trades or {}
        self.listings = listings or {}


# ---------------------------------------------------------------------------
# Simulation engine
# ---------------------------------------------------------------------------

POSITION_LIMITS: Dict[str, int] = {
    "AMETHYSTS": 20, "STARFRUIT": 20, "RESIN": 50, "KELP": 50,
    "SQUID_INK": 50, "CROISSANTS": 250, "JAMS": 350, "DJEMBES": 60,
    "PICNIC_BASKET1": 60, "PICNIC_BASKET2": 100, "ORCHIDS": 100,
    "VOLCANIC_ROCK": 400, "MAGNIFICENT_MACARONS": 75,
}

# Synthetic spread around mid price (ticks)
DEFAULT_SPREAD_TICKS = 2
DEFAULT_DEPTH_SIZE = 10


def _make_order_book(mid: float, spread: int = DEFAULT_SPREAD_TICKS, size: int = DEFAULT_DEPTH_SIZE) -> OrderDepth:
    depth = OrderDepth()
    mid_int = round(mid)
    half = spread // 2 or 1
    # Three levels on each side
    for i in range(1, 4):
        bid = mid_int - half * i
        ask = mid_int + half * i
        depth.buy_orders[bid] = size // i
        depth.sell_orders[ask] = -(size // i)
    return depth


def _fill_orders(
    orders: List[Order],
    depth: OrderDepth,
    position: int,
    limit: int,
) -> tuple[int, float]:
    """Match orders against the synthetic book. Returns (new_position, realized_pnl)."""
    pnl = 0.0
    pos = position
    for order in orders:
        qty = order.quantity
        px = order.price
        if qty > 0:  # buy order — match against ask side
            for ask_px in sorted(depth.sell_orders):
                if ask_px > px:
                    break
                available = -depth.sell_orders[ask_px]
                fill = min(qty, available, limit - pos)
                if fill <= 0:
                    break
                pnl -= fill * ask_px
                pos += fill
                qty -= fill
        elif qty < 0:  # sell order — match against bid side
            qty = -qty
            for bid_px in sorted(depth.buy_orders, reverse=True):
                if bid_px < px:
                    break
                available = depth.buy_orders[bid_px]
                fill = min(qty, available, pos + limit)
                if fill <= 0:
                    break
                pnl += fill * bid_px
                pos -= fill
                qty -= fill
    return pos, pnl


@dataclass
class SimResult:
    total_pnl: float
    sharpe: float
    max_drawdown: float
    total_return: float
    turnover: float
    tick_count: int
    violations: List[str] = field(default_factory=list)


def _load_trader(code_path: Path):
    """Dynamically load a Trader class from a Python file."""
    spec = importlib.util.spec_from_file_location("trader_module", code_path)
    mod = importlib.util.module_from_spec(spec)
    # Inject the shim datamodel so `from datamodel import ...` works
    sys.modules["datamodel"] = sys.modules[__name__]
    spec.loader.exec_module(mod)
    return mod.Trader


def _load_prices(csv_path: Path, products: list[str], start: str, end: str) -> Dict[str, list]:
    """Load price data per product. If CSV has a 'product' column, filter; else use close for all."""
    prices: Dict[str, list] = {p: [] for p in products}
    with csv_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    has_product_col = "product" in (rows[0] if rows else {})
    for row in rows:
        date = row.get("date", row.get("timestamp", ""))
        if date < start or date > end:
            continue
        close = float(row.get("close", row.get("mid", 0)) or 0)
        if has_product_col:
            p = row.get("product", "").upper()
            if p in prices:
                prices[p].append(close)
        else:
            for p in products:
                prices[p].append(close)
    return prices


def run_simulation(
    trader_class,
    price_series: Dict[str, list],
    products: list[str],
) -> SimResult:
    trader = trader_class()
    positions: Dict[str, int] = {p: 0 for p in products}
    trader_data = ""
    tick_pnls: list[float] = []
    cumulative_pnl = 0.0
    peak_pnl = 0.0
    max_dd = 0.0
    total_volume = 0.0
    violations: list[str] = []

    # Determine tick count from longest price series
    n_ticks = max((len(v) for v in price_series.values()), default=0)
    if n_ticks == 0:
        return SimResult(0, 0, 0, 0, 0, 0, ["no price data"])

    for tick in range(n_ticks):
        # Build order depths
        order_depths: Dict[str, OrderDepth] = {}
        for p in products:
            series = price_series.get(p, [])
            if tick < len(series):
                mid = series[tick]
                order_depths[p] = _make_order_book(mid)

        state = TradingState(
            timestamp=tick * 100,
            order_depths=order_depths,
            position=dict(positions),
            observations=Observation(),
            trader_data=trader_data,
        )

        try:
            result = trader.run(state)
            if isinstance(result, tuple) and len(result) == 3:
                orders_by_product, conversions, trader_data = result
            elif isinstance(result, tuple) and len(result) == 2:
                orders_by_product, trader_data = result
                conversions = 0
            else:
                orders_by_product = result or {}
                conversions = 0
                trader_data = ""
        except Exception as e:
            violations.append(f"tick {tick} error: {e}")
            break

        tick_pnl = 0.0
        for p, orders in (orders_by_product or {}).items():
            limit = POSITION_LIMITS.get(p, 20)
            depth = order_depths.get(p)
            if depth is None:
                continue
            new_pos, pnl = _fill_orders(orders or [], depth, positions.get(p, 0), limit)
            # Position limit violation check
            if abs(new_pos) > limit:
                violations.append(f"tick {tick} {p} position {new_pos} exceeds limit {limit}")
                new_pos = max(-limit, min(limit, new_pos))
            vol = abs(new_pos - positions.get(p, 0))
            total_volume += vol
            positions[p] = new_pos
            tick_pnl += pnl

        # Mark-to-market unrealized
        for p in products:
            series = price_series.get(p, [])
            if tick < len(series):
                mid = series[tick]
                tick_pnl += positions.get(p, 0) * (mid - (series[tick - 1] if tick > 0 else mid))

        tick_pnls.append(tick_pnl)
        cumulative_pnl += tick_pnl
        if cumulative_pnl > peak_pnl:
            peak_pnl = cumulative_pnl
        dd = (peak_pnl - cumulative_pnl) / (abs(peak_pnl) + 1e-9)
        if dd > max_dd:
            max_dd = dd

    if len(tick_pnls) < 2:
        return SimResult(cumulative_pnl, 0, max_dd, 0, 0, n_ticks, violations)

    import statistics
    mean_pnl = statistics.mean(tick_pnls)
    std_pnl = statistics.stdev(tick_pnls)
    sharpe = (mean_pnl / std_pnl) * math.sqrt(252 * 390) if std_pnl > 0 else 0.0

    # Turnover as fraction of hypothetical capital (product of limit * fair_value)
    hyp_capital = sum(POSITION_LIMITS.get(p, 20) * 10000 for p in products) or 1
    turnover = total_volume / (hyp_capital * n_ticks + 1e-9)

    total_return = cumulative_pnl / (hyp_capital or 1)

    return SimResult(
        total_pnl=cumulative_pnl,
        sharpe=min(max(sharpe, -10.0), 10.0),
        max_drawdown=min(max_dd, 1.0),
        total_return=total_return,
        turnover=turnover,
        tick_count=n_ticks,
        violations=violations,
    )


# ---------------------------------------------------------------------------
# CLI entry point (called by evaluator._run_script)
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--code", required=True, help="Path to Trader Python file")
    parser.add_argument("--data", required=True, help="Price CSV path")
    parser.add_argument("--start", default="2024-04-08")
    parser.add_argument("--end", default="2024-04-14")
    parser.add_argument("--products", default="AMETHYSTS,STARFRUIT,KELP,RESIN,SQUID_INK")
    parser.add_argument("--cash", type=float, default=0.0)
    args = parser.parse_args()

    products = [p.strip().upper() for p in args.products.split(",") if p.strip()]
    code_path = Path(args.code)
    data_path = Path(args.data)

    try:
        trader_class = _load_trader(code_path)
    except Exception as e:
        print(f"Failed to load Trader: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

    try:
        price_series = _load_prices(data_path, products, args.start, args.end)
    except Exception as e:
        print(f"Failed to load prices: {e}", file=sys.stderr)
        sys.exit(1)

    result = run_simulation(trader_class, price_series, products)

    stats = {
        "sharpe": result.sharpe,
        "max_drawdown": result.max_drawdown,
        "total_return": result.total_return,
        "turnover": result.turnover,
        "total_pnl": result.total_pnl,
        "tick_count": result.tick_count,
        "violations": result.violations,
    }
    print(f"STRATENGINE_STATS: {json.dumps(stats)}")
    if result.violations:
        print(f"[imc_simulator] {len(result.violations)} violation(s):", file=sys.stderr)
        for v in result.violations[:5]:
            print(f"  {v}", file=sys.stderr)


if __name__ == "__main__":
    main()
