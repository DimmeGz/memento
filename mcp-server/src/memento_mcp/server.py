"""Stdio MCP server exposing memory tools."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from memento_mcp.config import get_settings
from memento_mcp.memory import recall_memories, remember_fact
from memento_mcp.services.context import get_core_context_text
from memento_mcp.services.logging import log_conversation_message
from memento_mcp.validation import (
    validate_log_message,
    validate_recall_query,
    validate_remember,
)

mcp = FastMCP("memento-memory")


@mcp.tool()
def log_message(message: str, role: str, session_id: str) -> str:
    """Append a chat message: upsert conversation by session_id and insert message row."""
    data = validate_log_message(message=message, role=role, session_id=session_id)
    settings = get_settings()
    log_conversation_message(settings, data)
    return "ok"


@mcp.tool()
def remember(fact: str, scope: str, type: str) -> str:
    """Store a durable memory fact explicitly in Qdrant."""
    data = validate_remember(fact=fact, scope=scope, type=type)
    settings = get_settings()
    return remember_fact(
        settings,
        fact=data.fact,
        scope=data.scope,
        memory_type=data.memory_type,
    )


@mcp.tool()
def recall(query: str) -> str:
    """Search memories via vector similarity (user + project scope, RRF merge)."""
    q = validate_recall_query(query)
    settings = get_settings()
    return recall_memories(settings, query=q)


@mcp.tool()
def get_core_context() -> str:
    """Return high-importance semantic/procedural facts for user and project."""
    settings = get_settings()
    return get_core_context_text(settings)


def main() -> None:
    get_settings()
    mcp.run()


if __name__ == "__main__":
    main()
