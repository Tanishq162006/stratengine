"""Tests for price_fetcher.py."""
from unittest.mock import MagicMock, patch

import httpx
import pytest

import price_fetcher


SAMPLE_CSV = """Date,Open,High,Low,Close,Volume
2023-01-03,380.0,385.5,378.2,383.8,75000000
2023-01-04,383.0,388.0,381.5,387.2,68000000
2023-01-05,386.0,389.0,382.0,384.5,72000000
"""


def _mock_response(text=SAMPLE_CSV, status=200):
    resp = MagicMock()
    resp.text = text
    resp.status_code = status
    resp.raise_for_status = MagicMock()
    return resp


def test_parse_csv_returns_rows():
    rows = price_fetcher._parse_csv(SAMPLE_CSV, "SPY")
    assert len(rows) == 3
    assert rows[0]["date"] == "2023-01-03"
    assert rows[0]["close"] == pytest.approx(383.8)
    assert rows[0]["volume"] == pytest.approx(75_000_000)


def test_parse_csv_skips_bad_rows():
    bad_csv = SAMPLE_CSV + "2023-01-06,bad,data,here,now,x\n"
    rows = price_fetcher._parse_csv(bad_csv, "SPY")
    assert len(rows) == 3


def test_parse_csv_empty_returns_empty():
    rows = price_fetcher._parse_csv("Date,Open,High,Low,Close,Volume\n", "SPY")
    assert rows == []


def test_stooq_symbol_conversion():
    assert price_fetcher._stooq_symbol("SPY") == "spy.us"
    assert price_fetcher._stooq_symbol("spy.us") == "spy.us"
    # hyphens don't suppress the .us suffix — that's expected behavior
    assert price_fetcher._stooq_symbol("BTC-USD") == "btc-usd.us"


def test_write_and_read_csv(tmp_path):
    rows = [
        {"date": "2023-01-03", "open": 380.0, "high": 385.5, "low": 378.2, "close": 383.8, "volume": 75_000_000},
    ]
    path = tmp_path / "SPY.csv"
    price_fetcher._write_csv(rows, path)
    loaded = price_fetcher._read_csv(path)
    assert len(loaded) == 1
    assert loaded[0]["close"] == pytest.approx(383.8)


def test_load_raises_when_no_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(price_fetcher, "PRICES_DIR", tmp_path)
    with pytest.raises(FileNotFoundError):
        price_fetcher.load("NONEXISTENT")


def test_fetch_saves_csv(tmp_path, monkeypatch):
    monkeypatch.setattr(price_fetcher, "PRICES_DIR", tmp_path)

    with patch("httpx.get", return_value=_mock_response()):
        rows = price_fetcher.fetch("SPY", start="2023-01-01", end="2023-01-31", save=True)

    assert len(rows) == 3
    saved = tmp_path / "SPY.csv"
    assert saved.exists()
    loaded = price_fetcher._read_csv(saved)
    assert len(loaded) == 3


def test_fetch_raises_on_empty_response(tmp_path, monkeypatch):
    monkeypatch.setattr(price_fetcher, "PRICES_DIR", tmp_path)

    with patch("httpx.get", return_value=_mock_response("Date,Open,High,Low,Close,Volume\n")):
        with pytest.raises(ValueError, match="no data"):
            price_fetcher.fetch("FAKE", save=False)


def test_fetch_many_collects_results(tmp_path, monkeypatch):
    monkeypatch.setattr(price_fetcher, "PRICES_DIR", tmp_path)
    monkeypatch.setattr(price_fetcher, "_REQUEST_DELAY", 0)

    with patch("httpx.get", return_value=_mock_response()):
        results = price_fetcher.fetch_many(["SPY", "QQQ"], save=True)

    assert "SPY" in results
    assert "QQQ" in results
    assert len(results["SPY"]) == 3


def test_fetch_many_handles_partial_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(price_fetcher, "PRICES_DIR", tmp_path)
    monkeypatch.setattr(price_fetcher, "_REQUEST_DELAY", 0)

    call_count = {"n": 0}

    def mock_get(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 2:
            raise httpx.RequestError("timeout", request=MagicMock())
        return _mock_response()

    with patch("httpx.get", side_effect=mock_get):
        results = price_fetcher.fetch_many(["SPY", "FAIL", "QQQ"], save=False)

    assert len(results["SPY"]) == 3
    assert results["FAIL"] == []
    assert len(results["QQQ"]) == 3
