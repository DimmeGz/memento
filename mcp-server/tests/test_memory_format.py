from __future__ import annotations

from memento_mcp.memory import EMPTY_MESSAGE, format_facts


def test_format_facts_empty() -> None:
    assert format_facts([]) == EMPTY_MESSAGE


def test_format_facts_lines() -> None:
    payloads = [
        {"scope": "user", "type": "semantic", "text": "Prefers Ukrainian."},
        {"scope": "project", "type": "procedural", "text": "Run tests first."},
    ]
    out = format_facts(payloads)
    assert out.splitlines() == [
        "- [user/semantic] Prefers Ukrainian.",
        "- [project/procedural] Run tests first.",
    ]
