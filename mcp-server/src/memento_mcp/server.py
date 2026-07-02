"""Stdio MCP server exposing memory tools."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from memento_mcp.config import get_settings
from memento_mcp.db.repository import log_message as persist_log_message
from memento_mcp.memory import (
    get_core_context_memories,
    recall_memories,
    remember_fact,
)

ALLOWED_SCOPES = frozenset({"user", "project"})
ALLOWED_MEMORY_TYPES = frozenset({"episodic", "semantic", "procedural"})
ALLOWED_ROLES = frozenset({"user", "assistant"})

mcp = FastMCP("memento-memory")


@mcp.tool()
def log_message(message: str, role: str, session_id: str) -> str:
    """Append a chat message: upsert conversation by session_id and insert message row."""
    msg = message.strip()
    sid = session_id.strip()
    rl = role.strip().lower()
    if not msg:
        raise ValueError("message must be non-empty after strip.")
    if not sid:
        raise ValueError("session_id must be non-empty after strip.")
    if rl not in ALLOWED_ROLES:
        raise ValueError("role must be 'user' or 'assistant'.")

    settings = get_settings()
    persist_log_message(settings, session_id=sid, role=rl, content=msg)
    return "ok"


@mcp.tool()
def remember(fact: str, scope: str, type: str) -> str:
    """Store a durable memory fact explicitly in Qdrant."""
    text = fact.strip()
    if not text:
        raise ValueError("fact must be non-empty after strip.")
    sc = scope.strip().lower()
    if sc not in ALLOWED_SCOPES:
        raise ValueError("scope must be 'user' or 'project'.")
    mt = type.strip().lower()
    if mt not in ALLOWED_MEMORY_TYPES:
        raise ValueError("type must be 'episodic', 'semantic', or 'procedural'.")

    settings = get_settings()
    return remember_fact(settings, fact=text, scope=sc, memory_type=mt)


@mcp.tool()
def recall(query: str) -> str:
    """Search memories via vector similarity (user + project scope, RRF merge)."""
    q = query.strip()
    if not q:
        raise ValueError("query must be non-empty after strip.")

    settings = get_settings()
    return recall_memories(settings, query=q)


@mcp.tool()
def get_core_context() -> str:
    """Return high-importance semantic/procedural facts for user and project."""
    settings = get_settings()
    return get_core_context_memories(settings)


def main() -> None:
    get_settings()
    mcp.run()


if __name__ == "__main__":
    main()
