"""Structured facts returned by the consolidation LLM."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, TypeAdapter


class ExtractedFact(BaseModel):
    """One remembered fact from dialogue consolidation."""

    text: str = Field(..., min_length=1)
    scope: Literal["user", "project"]
    type: Literal["episodic", "semantic", "procedural"]
    importance: float | None = Field(default=None, ge=0.0, le=1.0)


_FACT_LIST_ADAPTER = TypeAdapter(list[ExtractedFact])


def parse_facts_json(raw: str) -> list[ExtractedFact]:
    """Parse model output: either a JSON array of facts or ``{\"facts\": [...]}``."""

    import json

    data = json.loads(raw)
    if isinstance(data, dict) and "facts" in data:
        data = data["facts"]
    elif isinstance(data, dict):
        data = [data]
    return _FACT_LIST_ADAPTER.validate_python(data)
