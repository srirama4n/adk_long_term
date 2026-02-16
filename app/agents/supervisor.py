"""
Supervisor (orchestrator) agent: routes user messages to Weather or Finance sub-agents.

All user communication goes through the Supervisor; sub-agents never interact with the user directly.
"""

from __future__ import annotations

from app.agents.weather_agent import get_weather_agent
from app.agents.finance_agent import get_finance_agent
from app.config import get_settings

try:
    from google.adk.agents import LlmAgent
except ImportError:
    from google.adk.agents.llm_agent import Agent as LlmAgent


def get_supervisor_agent() -> LlmAgent:
    """Build Supervisor with WeatherAgent and FinanceAgent as sub-agents."""
    settings = get_settings()
    weather_agent = get_weather_agent()
    finance_agent = get_finance_agent()
    return LlmAgent(
        name="Supervisor",
        model=settings.gemini_model,
        description="Orchestrates user requests. Routes weather questions to WeatherAgent and finance/stock questions to FinanceAgent.",
        instruction=(
            "You are the main assistant. You NEVER respond to the user directly with weather or stock data yourself.\n"
            "1. Classify the user intent: weather_query (weather, forecast, temperature), finance_query (stock, price, ticker), or general_query (greetings, other).\n"
            "2. If weather_query: delegate to WeatherAgent. If finance_query: delegate to FinanceAgent. If general_query: respond briefly and helpfully.\n"
            "3. After the sub-agent responds, return that response to the user in a clear, friendly way. Do not add extra tool calls; the sub-agent already produced the answer.\n"
            "Always delegate weather and finance questions to the appropriate sub-agent."
        ),
        sub_agents=[weather_agent, finance_agent],
    )
