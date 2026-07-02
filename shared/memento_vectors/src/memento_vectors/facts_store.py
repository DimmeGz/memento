"""Qdrant facts collection: ensure schema, dedup, upsert, search, scroll."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from memento_vectors.models import ExtractedFact


def _sanitize(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", name)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class FactsStore:
    def __init__(
        self,
        *,
        client: QdrantClient,
        collection_prefix: str,
        dedup_threshold: float,
        embedding_model_label: str,
        default_importance: float,
        default_decay_rate: float,
    ) -> None:
        self._client = client
        self._prefix = collection_prefix
        self._dedup_threshold = dedup_threshold
        self._embedding_model_label = embedding_model_label
        self._default_importance = default_importance
        self._default_decay_rate = default_decay_rate

    def collection_for(self, project_id: str) -> str:
        """Return the Qdrant collection name for a given project."""
        return _sanitize(f"{self._prefix}_{project_id}")

    def collection_exists(self, project_id: str) -> bool:
        collection = self.collection_for(project_id)
        names = {c.name for c in self._client.get_collections().collections}
        return collection in names

    def ensure_collection(self, vector_size: int, project_id: str) -> None:
        collection = self.collection_for(project_id)
        names = {c.name for c in self._client.get_collections().collections}
        if collection in names:
            info = self._client.get_collection(collection)
            params = info.config.params.vectors
            if isinstance(params, qmodels.VectorParams):
                existing = params.size
                if existing != vector_size:
                    raise RuntimeError(
                        f"Qdrant collection {collection!r} has vector size {existing}, "
                        f"but embeddings have size {vector_size}."
                    )
            return

        self._client.create_collection(
            collection_name=collection,
            vectors_config=qmodels.VectorParams(size=vector_size, distance=qmodels.Distance.COSINE),
        )

    def build_payload(
        self,
        *,
        user_id: str,
        project_id: str,
        session_id: str,
        fact: ExtractedFact,
        now: str | None = None,
    ) -> dict[str, object]:
        ts = now or _utc_now_iso()
        imp = fact.importance if fact.importance is not None else self._default_importance
        return {
            "user_id": user_id,
            "project_id": project_id,
            "scope": fact.scope,
            "type": fact.type,
            "valid": True,
            "importance": imp,
            "decay_rate": self._default_decay_rate,
            "embedding_model": self._embedding_model_label,
            "created_at": ts,
            "last_accessed_at": ts,
            "source_session": session_id,
            "text": fact.text,
        }

    def is_near_duplicate(
        self,
        *,
        vector: list[float],
        user_id: str,
        project_id: str,
        scope: str,
    ) -> bool:
        collection = self.collection_for(project_id)
        must: list[qmodels.Condition] = [
            qmodels.FieldCondition(key="scope", match=qmodels.MatchValue(value=scope)),
            qmodels.FieldCondition(key="valid", match=qmodels.MatchValue(value=True)),
        ]
        if scope == "user":
            must.append(qmodels.FieldCondition(key="user_id", match=qmodels.MatchValue(value=user_id)))
        flt = qmodels.Filter(must=must)
        result = self._client.query_points(
            collection_name=collection,
            query=vector,
            query_filter=flt,
            limit=1,
            with_payload=False,
        )
        if not result.points:
            return False
        return float(result.points[0].score) >= self._dedup_threshold

    def upsert_fact(
        self,
        *,
        vector: list[float],
        user_id: str,
        project_id: str,
        session_id: str,
        fact: ExtractedFact,
    ) -> UUID:
        collection = self.collection_for(project_id)
        now = _utc_now_iso()
        point_id = uuid4()
        payload = self.build_payload(
            user_id=user_id,
            project_id=project_id,
            session_id=session_id,
            fact=fact,
            now=now,
        )
        self._client.upsert(
            collection_name=collection,
            points=[
                qmodels.PointStruct(id=str(point_id), vector=vector, payload=payload),
            ],
        )
        return point_id

    def search(
        self,
        *,
        vector: list[float],
        project_id: str,
        must: list[qmodels.Condition],
        limit: int,
    ) -> list[tuple[str, dict[str, Any], float]]:
        """Vector search; returns ``[(point_id, payload, score), ...]`` best-first."""
        collection = self.collection_for(project_id)
        flt = qmodels.Filter(must=must)
        result = self._client.query_points(
            collection_name=collection,
            query=vector,
            query_filter=flt,
            limit=limit,
            with_payload=True,
        )
        hits: list[tuple[str, dict[str, Any], float]] = []
        for point in result.points:
            payload = dict(point.payload or {})
            hits.append((str(point.id), payload, float(point.score)))
        return hits

    def scroll_core_context(
        self,
        *,
        project_id: str,
        scope: str,
        id_field: str,
        id_value: str,
        importance_threshold: float,
        types: tuple[str, ...],
        limit: int,
    ) -> list[dict[str, Any]]:
        """Scroll valid facts for core context, sorted by importance desc."""
        if not self.collection_exists(project_id):
            return []

        collection = self.collection_for(project_id)
        must: list[qmodels.Condition] = [
            qmodels.FieldCondition(key="scope", match=qmodels.MatchValue(value=scope)),
            qmodels.FieldCondition(key=id_field, match=qmodels.MatchValue(value=id_value)),
            qmodels.FieldCondition(key="valid", match=qmodels.MatchValue(value=True)),
            qmodels.FieldCondition(key="type", match=qmodels.MatchAny(any=list(types))),
            qmodels.FieldCondition(
                key="importance",
                range=qmodels.Range(gte=importance_threshold),
            ),
        ]
        flt = qmodels.Filter(must=must)

        payloads: list[dict[str, Any]] = []
        offset = None
        while True:
            records, next_offset = self._client.scroll(
                collection_name=collection,
                scroll_filter=flt,
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for record in records:
                if record.payload:
                    payloads.append(dict(record.payload))
            if next_offset is None:
                break
            offset = next_offset

        payloads.sort(key=lambda p: float(p.get("importance", 0.0)), reverse=True)
        return payloads[:limit]

    def touch_last_accessed(self, *, project_id: str, point_ids: list[str]) -> None:
        """Best-effort update of last_accessed_at for recalled facts."""
        if not point_ids:
            return
        collection = self.collection_for(project_id)
        self._client.set_payload(
            collection_name=collection,
            payload={"last_accessed_at": _utc_now_iso()},
            points=point_ids,
        )
