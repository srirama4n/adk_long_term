"""Re-export ContextConfig from agent_context. Use ContextConfig.from_settings(get_settings()) in app."""

from agent_context.config import ContextConfig

__all__ = ["ContextConfig"]
