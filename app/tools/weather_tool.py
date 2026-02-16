"""Weather tool for the Weather Agent."""

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
def get_weather(location: str, date: str | None = None) -> dict[str, Any]:
    """
    Retrieves the current or forecast weather for a specified location.

    Args:
        location: The city or location name (e.g. Mumbai, Delhi).
        date: Optional date for forecast (YYYY-MM-DD). If omitted, returns current weather.

    Returns:
        dict with keys: location, temperature, condition, forecast.
    """
    _ = get_settings()
    # Simulated implementation; replace with real API (e.g. OpenWeatherMap) in production.
    conditions = ["Sunny", "Partly cloudy", "Cloudy", "Rainy", "Clear"]
    condition = random.choice(conditions)
    temp_c = random.randint(18, 38)
    forecast = f"{condition}, {temp_c}°C. Highs in the low 30s, lows in the mid 20s."
    return {
        "location": location,
        "temperature": f"{temp_c}°C",
        "condition": condition,
        "forecast": forecast,
    }
