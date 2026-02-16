"""
Supervisor (orchestrator) agent: routes user messages to Weather or Finance sub-agents.

All user communication goes through the Supervisor; sub-agents never interact with the user directly.
"""

from __future__ import annotations

from app.agents.finance_agent import get_finance_agent
from app.agents.procedure_agent import get_procedure_agent
from app.agents.weather_agent import get_weather_agent
from app.config import get_settings

try:
    from google.adk.agents import LlmAgent
except ImportError:
    from google.adk.agents.llm_agent import Agent as LlmAgent


def get_supervisor_agent() -> LlmAgent:
    """Build Supervisor with WeatherAgent, FinanceAgent, and ProcedureAgent as sub-agents."""
    settings = get_settings()
    weather_agent = get_weather_agent()
    finance_agent = get_finance_agent()
    procedure_agent = get_procedure_agent()
    return LlmAgent(
        name="Supervisor",
        model=settings.gemini_model,
        description="Orchestrates user requests. Routes weather to WeatherAgent, finance/stock to FinanceAgent, and procedure-saving to ProcedureAgent.",
        instruction=(
            "You are the main assistant. You NEVER respond to the user directly with weather or stock data yourself.\n"
            "1. Classify the user intent: weather_query (weather, forecast, temperature), finance_query (stock, price, ticker), procedure_query (remember a procedure, save how-to, save these steps), or general_query (greetings, other).\n"
            "2. If weather_query: delegate to WeatherAgent. If finance_query: delegate to FinanceAgent. If procedure_query: delegate to ProcedureAgent.\n"
            "3. If general_query and the user asks how to do something, what their saved procedure is, or for the steps of a procedure (e.g. 'how do I check the weather?', 'what are the steps for check_weather?'): use the [Saved procedures] context in the message and respond with the relevant procedure name and steps. If no [Saved procedures] context or no matching procedure, say you don't have that procedure saved and they can save one by describing it.\n"
            "4. For other general_query: respond briefly and helpfully.\n"
            "5. After a sub-agent responds, return that response to the user in a clear, friendly way. Do not add extra tool calls; the sub-agent already produced the answer.\n"
            "Always delegate weather, finance, and procedure-saving questions to the appropriate sub-agent."
        ),
        sub_agents=[weather_agent, finance_agent, procedure_agent],
    )
