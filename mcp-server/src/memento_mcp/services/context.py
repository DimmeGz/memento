"""Core context service."""

from __future__ import annotations

from memento_mcp.config import Settings
from memento_mcp.memory import get_core_context_memories


def get_core_context_text(settings: Settings) -> str:
    return get_core_context_memories(settings)
