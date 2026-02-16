"""Finance tool for the Finance Agent."""

from __future__ import annotations

import random
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    reraise=True,
)
def get_stock_price(stock_symbol: str) -> dict[str, Any]:
    """
    Retrieves the current stock price and change for a given symbol.

    Args:
        stock_symbol: Ticker symbol (e.g. AAPL, GOOGL, MSFT).

    Returns:
        dict with keys: symbol, price, change.
    """
    _ = get_settings()
    # Simulated implementation; replace with real API (e.g. Alpha Vantage, Yahoo Finance) in production.
    base_prices = {"AAPL": 185.0, "GOOGL": 175.0, "MSFT": 420.0, "AMZN": 195.0}
    base = base_prices.get(stock_symbol.upper(), 100.0)
    price = round(base * (1 + random.uniform(-0.02, 0.02)), 2)
    change_pct = round((price - base) / base * 100, 2)
    return {
        "symbol": stock_symbol.upper(),
        "price": f"${price:.2f}",
        "change": f"{change_pct:+.2f}%",
    }
