"""Shared service layer for MCP, CLI, and HTTP entry points."""

from memento_mcp.services.context import get_core_context_text
from memento_mcp.services.logging import log_conversation_message

__all__ = ["get_core_context_text", "log_conversation_message"]
