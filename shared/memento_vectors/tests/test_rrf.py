from __future__ import annotations

from memento_vectors.rrf import rrf_merge


def test_rrf_merge_single_list() -> None:
    ranking = [
        ("a", {"text": "first"}),
        ("b", {"text": "second"}),
    ]
    merged = rrf_merge([ranking], k=60, limit=2)
    assert [h.point_id for h in merged] == ["a", "b"]
    assert merged[0].score > merged[1].score


def test_rrf_merge_boosts_shared_ids() -> None:
    user = [("shared", {"text": "both"}), ("u-only", {"text": "user"})]
    project = [("shared", {"text": "both"}), ("p-only", {"text": "project"})]
    merged = rrf_merge([user, project], k=60, limit=3)
    assert merged[0].point_id == "shared"
    assert merged[0].score > merged[1].score


def test_rrf_merge_respects_limit() -> None:
    ranking = [(str(i), {"text": str(i)}) for i in range(5)]
    merged = rrf_merge([ranking], k=60, limit=2)
    assert len(merged) == 2
