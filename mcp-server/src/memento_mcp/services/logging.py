"""Conversation logging service."""

from __future__ import annotations

from memento_mcp.config import Settings
from memento_mcp.db.repository import log_message as persist_log_message
from memento_mcp.validation import LogMessageInput


def log_conversation_message(settings: Settings, data: LogMessageInput) -> None:
    persist_log_message(
        settings,
        session_id=data.session_id,
        role=data.role,
        content=data.message,
    )
