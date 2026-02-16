"""Procedure sub-agent: saves how-to procedures to procedural memory via save_procedure tool."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.config import get_settings
from app.tools.procedure_tool import save_procedure

try:
    from google.adk.agents import LlmAgent
except ImportError:
    from google.adk.agents.llm_agent import Agent as LlmAgent


class ProcedureSavedOutput(BaseModel):
    """Structured response when a procedure is saved."""

    name: str = Field(description="Name of the saved procedure")
    steps_count: int = Field(description="Number of steps")
    message: str = Field(description="Confirmation message for the user")


def get_procedure_agent() -> LlmAgent:
    settings = get_settings()
    return LlmAgent(
        name="ProcedureAgent",
        model=settings.gemini_model,
        description=(
            "Handles saving how-to procedures. Use when the user wants to remember a procedure, "
            "steps, or how to do something (e.g. 'remember how to X', 'save these steps', 'here is how I do Y')."
        ),
        instruction=(
            "You are a procedure assistant. When the user asks to remember a procedure or 'how to do' something:\n"
            "1. Extract a short, clear name for the procedure (e.g. check_weather, order_coffee).\n"
            "2. Extract the ordered list of steps from the user's message. Each step should be one clear sentence or phrase.\n"
            "3. Call save_procedure(name, steps, description) with that name and steps. Use description if the user gave context.\n"
            "4. Respond with a brief confirmation that the procedure was saved, using the required JSON structure (name, steps_count, message).\n"
            "Always call save_procedure exactly once per user request. If the user message is vague, infer a reasonable name and steps from context."
        ),
        tools=[save_procedure],
        output_schema=ProcedureSavedOutput,
    )
