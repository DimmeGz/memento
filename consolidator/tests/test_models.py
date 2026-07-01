from __future__ import annotations

import json

import pytest

from memento_consolidator.models import ExtractedFact, parse_facts_json


def test_parse_facts_json_array() -> None:
    raw = json.dumps(
        [
            {"text": "User prefers Ukrainian.", "scope": "user", "type": "semantic", "importance": 0.9},
            {"text": "Repo uses FastAPI.", "scope": "project", "type": "semantic"},
        ]
    )
    facts = parse_facts_json(raw)
    assert len(facts) == 2
    assert facts[0] == ExtractedFact(
        text="User prefers Ukrainian.",
        scope="user",
        type="semantic",
        importance=0.9,
    )


def test_parse_facts_json_wrapped() -> None:
    raw = json.dumps(
        {
            "facts": [
                {"text": "Run tests before push.", "scope": "project", "type": "procedural"},
            ]
        }
    )
    facts = parse_facts_json(raw)
    assert len(facts) == 1
    assert facts[0].text == "Run tests before push."
