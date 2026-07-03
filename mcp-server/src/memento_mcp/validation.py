"""Shared validation for MCP tools, CLI, and HTTP handlers."""

from __future__ import annotations

from dataclasses import dataclass

ALLOWED_SCOPES = frozenset({"user", "project"})
ALLOWED_MEMORY_TYPES = frozenset({"episodic", "semantic", "procedural"})
ALLOWED_ROLES = frozenset({"user", "assistant"})


class ValidationError(ValueError):
    """Invalid user input."""


@dataclass(frozen=True, slots=True)
class LogMessageInput:
    message: str
    role: str
    session_id: str


@dataclass(frozen=True, slots=True)
class RememberInput:
    fact: str
    scope: str
    memory_type: str


def validate_log_message(*, message: str, role: str, session_id: str) -> LogMessageInput:
    msg = message.strip()
    sid = session_id.strip()
    rl = role.strip().lower()
    if not msg:
        raise ValidationError("message must be non-empty after strip.")
    if not sid:
        raise ValidationError("session_id must be non-empty after strip.")
    if rl not in ALLOWED_ROLES:
        raise ValidationError("role must be 'user' or 'assistant'.")
    return LogMessageInput(message=msg, role=rl, session_id=sid)


def validate_remember(*, fact: str, scope: str, type: str) -> RememberInput:
    text = fact.strip()
    if not text:
        raise ValidationError("fact must be non-empty after strip.")
    sc = scope.strip().lower()
    if sc not in ALLOWED_SCOPES:
        raise ValidationError("scope must be 'user' or 'project'.")
    mt = type.strip().lower()
    if mt not in ALLOWED_MEMORY_TYPES:
        raise ValidationError("type must be 'episodic', 'semantic', or 'procedural'.")
    return RememberInput(fact=text, scope=sc, memory_type=mt)


def validate_recall_query(query: str) -> str:
    q = query.strip()
    if not q:
        raise ValidationError("query must be non-empty after strip.")
    return q
