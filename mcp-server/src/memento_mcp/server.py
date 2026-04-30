"""Stdio MCP server exposing memory tools."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from memento_mcp.config import get_settings
from memento_mcp.db.repository import log_message as persist_log_message

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
    """Store a durable memory fact (not implemented in phase 1)."""
    if not fact.strip():
        raise ValueError("fact must be non-empty after strip.")
    sc = scope.strip().lower()
    if sc not in ALLOWED_SCOPES:
        raise ValueError("scope must be 'user' or 'project'.")
    mt = type.strip().lower()
    if mt not in ALLOWED_MEMORY_TYPES:
        raise ValueError("type must be 'episodic', 'semantic', or 'procedural'.")
    return "[NOT_IMPLEMENTED] remember"


@mcp.tool()
def recall(query: str) -> str:
    """Search memories (not implemented in phase 1)."""
    if not query.strip():
        raise ValueError("query must be non-empty after strip.")
    return "[NOT_IMPLEMENTED] recall"


@mcp.tool()
def get_core_context() -> str:
    """Return consolidated core context (not implemented in phase 1)."""
    return "[NOT_IMPLEMENTED] get_core_context"


def main() -> None:
    get_settings()
    mcp.run()


if __name__ == "__main__":
    main()
