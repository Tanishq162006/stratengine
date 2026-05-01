"""Tests for imc_simulator.py."""
import math
import pytest

from competitions.imc_prosperity.simulator import (
    Order,
    _make_order_book,
    _fill_orders,
    _load_prices,
    run_simulation,
    SimResult,
)


# ---------------------------------------------------------------------------
# Order book helpers
# ---------------------------------------------------------------------------

def test_make_order_book_has_both_sides():
    depth = _make_order_book(10000, spread=2)
    assert depth.buy_orders
    assert depth.sell_orders
    # Best bid < mid < best ask
    assert max(depth.buy_orders) < 10000
    assert min(depth.sell_orders) > 10000


def test_fill_orders_buy_matches_ask():
    depth = _make_order_book(10000, spread=2, size=20)
    pos, pnl = _fill_orders([Order("X", 10002, 5)], depth, position=0, limit=20)
    assert pos > 0
    assert pnl < 0  # spent cash to buy


def test_fill_orders_sell_matches_bid():
    depth = _make_order_book(10000, spread=2, size=20)
    pos, pnl = _fill_orders([Order("X", 9998, -5)], depth, position=0, limit=20)
    assert pos < 0
    assert pnl > 0  # received cash from sell


def test_fill_orders_respects_position_limit():
    depth = _make_order_book(10000, spread=2, size=100)
    # Start at limit=5, try to buy 10 more
    pos, _ = _fill_orders([Order("X", 10002, 10)], depth, position=0, limit=5)
    assert pos <= 5


def test_fill_orders_no_cross_on_wrong_price():
    depth = _make_order_book(10000, spread=2, size=20)
    # Bid below best ask — should not fill anything
    pos, pnl = _fill_orders([Order("X", 9990, 5)], depth, position=0, limit=20)
    assert pos == 0
    assert pnl == 0.0


# ---------------------------------------------------------------------------
# Price loader
# ---------------------------------------------------------------------------

def test_load_prices_single_symbol(tmp_path):
    csv = tmp_path / "prices.csv"
    csv.write_text("date,open,high,low,close,volume\n"
                   "2024-04-08,100,105,98,102,1000\n"
                   "2024-04-09,102,108,101,106,1200\n")
    result = _load_prices(csv, ["SPY"], "2024-04-08", "2024-04-09")
    assert len(result["SPY"]) == 2
    assert result["SPY"][0] == pytest.approx(102.0)


def test_load_prices_filtered_by_date(tmp_path):
    csv = tmp_path / "prices.csv"
    csv.write_text("date,open,high,low,close,volume\n"
                   "2024-04-07,99,100,98,99,500\n"
                   "2024-04-08,100,105,98,102,1000\n"
                   "2024-04-09,102,108,101,106,1200\n"
                   "2024-04-10,106,110,105,109,900\n")
    result = _load_prices(csv, ["SPY"], "2024-04-08", "2024-04-09")
    assert len(result["SPY"]) == 2


# ---------------------------------------------------------------------------
# Full simulation
# ---------------------------------------------------------------------------

class DoNothingTrader:
    def run(self, state):
        return {}, 0, ""


class SimpleMMTrader:
    """Buy cheap, sell expensive around 10000."""
    def run(self, state):
        orders = {}
        for product, depth in state.order_depths.items():
            pos = state.position.get(product, 0)
            product_orders = []
            for ask_px in sorted(depth.sell_orders):
                if ask_px < 10001 and pos < 20:
                    product_orders.append(Order(product, ask_px, min(5, 20 - pos)))
                    break
            for bid_px in sorted(depth.buy_orders, reverse=True):
                if bid_px > 9999 and pos > -20:
                    product_orders.append(Order(product, bid_px, -min(5, pos + 20)))
                    break
            orders[product] = product_orders
        return orders, 0, ""


def test_simulation_do_nothing_zero_pnl():
    price_series = {"AMETHYSTS": [10000.0] * 50}
    result = run_simulation(DoNothingTrader, price_series, ["AMETHYSTS"])
    assert isinstance(result, SimResult)
    assert result.total_pnl == pytest.approx(0.0, abs=1.0)
    assert result.tick_count == 50


def test_simulation_produces_sharpe():
    price_series = {"AMETHYSTS": [10000.0 + (i % 3) for i in range(100)]}
    result = run_simulation(SimpleMMTrader, price_series, ["AMETHYSTS"])
    assert isinstance(result, SimResult)
    assert math.isfinite(result.sharpe)
    assert 0.0 <= result.max_drawdown <= 1.0


def test_simulation_empty_price_series():
    result = run_simulation(DoNothingTrader, {"AMETHYSTS": []}, ["AMETHYSTS"])
    assert "no price data" in result.violations


def test_simulation_handles_trader_exception():
    class CrashTrader:
        def run(self, state):
            raise RuntimeError("intentional crash")

    price_series = {"AMETHYSTS": [10000.0] * 10}
    result = run_simulation(CrashTrader, price_series, ["AMETHYSTS"])
    assert any("error" in v for v in result.violations)
