"""Weather sub-agent: answers weather queries using get_weather tool."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.config import get_settings
from app.tools.weather_tool import get_weather

try:
    from google.adk.agents import LlmAgent
except ImportError:
    from google.adk.agents.llm_agent import Agent as LlmAgent


class WeatherOutput(BaseModel):
    """Structured weather response."""

    location: str = Field(description="City or location name")
    temperature: str = Field(description="Temperature with unit")
    condition: str = Field(description="Weather condition")
    forecast: str = Field(description="Short forecast text")


def get_weather_agent() -> LlmAgent:
    settings = get_settings()
    return LlmAgent(
        name="WeatherAgent",
        model=settings.gemini_model,
        description="Handles weather queries. Use for questions about current weather or forecast for a location.",
        instruction=(
            "You are a weather assistant. When the user asks about weather:\n"
            "1. Extract the location (city name) and optional date from the message.\n"
            "2. Call get_weather(location, date) with those arguments.\n"
            "3. Respond with a JSON object containing: location, temperature, condition, forecast.\n"
            "Always use the get_weather tool; then format the tool result into the required JSON structure."
        ),
        tools=[get_weather],
        output_schema=WeatherOutput,
    )
