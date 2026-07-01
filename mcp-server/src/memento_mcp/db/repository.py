"""Thin MCP facade over ``memento_core`` persistence."""

from __future__ import annotations

from memento_core.db.repository import log_message as core_log_message

from memento_mcp.config import Settings


def log_message(
    settings: Settings,
    *,
    session_id: str,
    role: str,
    content: str,
) -> None:
    core_log_message(
        settings.database_url,
        user_id=settings.user_id,
        project_id=settings.project_id,
        session_id=session_id,
        role=role,
        content=content,
    )
