"""Free daily OHLCV fetcher via Stooq (no API key required).

Saves per-symbol CSV files to data/prices/<SYMBOL>.csv compatible with the
decision_scorer historical scenario logic.

Usage:
    from price_fetcher import fetch, fetch_many
    df = fetch("SPY", start="2018-01-01", end="2023-12-31")
"""
from __future__ import annotations

import csv
import io
import time
from datetime import date, datetime
from pathlib import Path
from typing import Sequence

import httpx

PRICES_DIR = Path(__file__).parent / "data" / "prices"
STOOQ_URL = "https://stooq.com/q/d/l/"
_REQUEST_DELAY = 1.2  # seconds between requests to avoid rate-limiting


def _stooq_symbol(symbol: str) -> str:
    """Convert ticker to Stooq format (lowercase, append .us for equities)."""
    s = symbol.lower()
    if "." not in s:
        s = s + ".us"
    return s


def fetch(
    symbol: str,
    start: str = "2015-01-01",
    end: str | None = None,
    save: bool = True,
) -> list[dict]:
    """Fetch daily OHLCV for `symbol` from Stooq.

    Returns list of dicts with keys: date, open, high, low, close, volume.
    Saves to data/prices/<SYMBOL>.csv if save=True.
    """
    end_str = end or date.today().isoformat()
    params = {
        "s": _stooq_symbol(symbol),
        "d1": start.replace("-", ""),
        "d2": end_str.replace("-", ""),
        "i": "d",
    }
    resp = httpx.get(STOOQ_URL, params=params, timeout=30, follow_redirects=True)
    resp.raise_for_status()

    rows = _parse_csv(resp.text, symbol)
    if not rows:
        raise ValueError(f"Stooq returned no data for {symbol!r} ({start} → {end_str})")

    if save:
        PRICES_DIR.mkdir(parents=True, exist_ok=True)
        out_path = PRICES_DIR / f"{symbol.upper()}.csv"
        _write_csv(rows, out_path)

    return rows


def fetch_many(
    symbols: Sequence[str],
    start: str = "2015-01-01",
    end: str | None = None,
    save: bool = True,
) -> dict[str, list[dict]]:
    """Fetch multiple symbols with rate-limit delay between requests."""
    results: dict[str, list[dict]] = {}
    for i, sym in enumerate(symbols):
        if i > 0:
            time.sleep(_REQUEST_DELAY)
        try:
            results[sym] = fetch(sym, start=start, end=end, save=save)
        except Exception as e:
            results[sym] = []
            print(f"[price_fetcher] {sym}: {e}")
    return results


def load(symbol: str) -> list[dict]:
    """Load cached CSV from data/prices/<SYMBOL>.csv."""
    path = PRICES_DIR / f"{symbol.upper()}.csv"
    if not path.exists():
        raise FileNotFoundError(f"No cached data for {symbol}. Run fetch() first.")
    return _read_csv(path)


def _parse_csv(text: str, symbol: str) -> list[dict]:
    rows: list[dict] = []
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        date_str = row.get("Date", "").strip()
        if not date_str or date_str.startswith("No"):
            continue
        try:
            rows.append({
                "date": date_str,
                "open": float(row.get("Open", 0) or 0),
                "high": float(row.get("High", 0) or 0),
                "low": float(row.get("Low", 0) or 0),
                "close": float(row.get("Close", 0) or 0),
                "volume": float(row.get("Volume", 0) or 0),
            })
        except (ValueError, TypeError):
            continue
    rows.sort(key=lambda r: r["date"])
    return rows


def _write_csv(rows: list[dict], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "open", "high", "low", "close", "volume"])
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [
            {
                "date": r["date"],
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
                "volume": float(r["volume"]),
            }
            for r in reader
        ]
