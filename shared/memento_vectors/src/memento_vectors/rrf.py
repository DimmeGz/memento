"""Reciprocal Rank Fusion for merging ranked search results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class RankedHit:
    """One search hit with point id, payload, and fused RRF score."""

    point_id: str
    payload: dict[str, Any]
    score: float


def rrf_merge(
    rankings: list[list[tuple[str, dict[str, Any]]]],
    *,
    k: int = 60,
    limit: int | None = None,
) -> list[RankedHit]:
    """
    Merge multiple ranked lists using Reciprocal Rank Fusion.

    Each ranking is ``[(point_id, payload), ...]`` ordered best-first.
    Duplicate point ids across lists accumulate RRF scores.
    """
    scores: dict[str, float] = {}
    payloads: dict[str, dict[str, Any]] = {}

    for ranking in rankings:
        for rank, (point_id, payload) in enumerate(ranking, start=1):
            scores[point_id] = scores.get(point_id, 0.0) + 1.0 / (k + rank)
            payloads[point_id] = payload

    merged = [
        RankedHit(point_id=pid, payload=payloads[pid], score=score)
        for pid, score in scores.items()
    ]
    merged.sort(key=lambda h: h.score, reverse=True)
    if limit is not None:
        merged = merged[:limit]
    return merged
