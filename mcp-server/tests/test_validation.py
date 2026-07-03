from __future__ import annotations

import pytest

from memento_mcp.validation import ValidationError, validate_log_message, validate_recall_query, validate_remember


def test_validate_log_message_ok() -> None:
    data = validate_log_message(message=" hello ", role="User", session_id=" sid ")
    assert data.message == "hello"
    assert data.role == "user"
    assert data.session_id == "sid"


@pytest.mark.parametrize(
    ("message", "role", "session_id", "match"),
    [
        ("", "user", "s1", "message must be non-empty"),
        ("hi", "system", "s1", "role must be"),
        ("hi", "user", "", "session_id must be non-empty"),
    ],
)
def test_validate_log_message_errors(message: str, role: str, session_id: str, match: str) -> None:
    with pytest.raises(ValidationError, match=match):
        validate_log_message(message=message, role=role, session_id=session_id)


def test_validate_remember_ok() -> None:
    data = validate_remember(fact=" fact ", scope="Project", type="Semantic")
    assert data.fact == "fact"
    assert data.scope == "project"
    assert data.memory_type == "semantic"


def test_validate_recall_query_ok() -> None:
    assert validate_recall_query("  q  ") == "q"


def test_validate_recall_query_empty() -> None:
    with pytest.raises(ValidationError, match="query must be non-empty"):
        validate_recall_query("   ")
