"""Finance sub-agent: answers stock price queries using get_stock_price tool."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.config import get_settings
from app.tools.finance_tool import get_stock_price

try:
    from google.adk.agents import LlmAgent
except ImportError:
    from google.adk.agents.llm_agent import Agent as LlmAgent


class FinanceOutput(BaseModel):
    """Structured finance/stock response."""

    symbol: str = Field(description="Stock ticker symbol")
    price: str = Field(description="Current price")
    change: str = Field(description="Price change percentage")


def get_finance_agent() -> LlmAgent:
    settings = get_settings()
    return LlmAgent(
        name="FinanceAgent",
        model=settings.gemini_model,
        description="Handles finance and stock price queries. Use for questions about stock prices, ticker symbols.",
        instruction=(
            "You are a finance assistant. When the user asks about a stock:\n"
            "1. Extract the stock symbol (e.g. AAPL, GOOGL) from the message.\n"
            "2. Call get_stock_price(stock_symbol) with that symbol.\n"
            "3. Respond with a JSON object containing: symbol, price, change.\n"
            "Always use the get_stock_price tool; then format the tool result into the required JSON structure."
        ),
        tools=[get_stock_price],
        output_schema=FinanceOutput,
    )
