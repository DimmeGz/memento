"""Qdrant facts collection: ensure schema, dedup, upsert."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from uuid import UUID, uuid4

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from memento_consolidator.models import ExtractedFact


def _sanitize(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", name)


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
        now = datetime.now(timezone.utc).isoformat()
        imp = fact.importance if fact.importance is not None else self._default_importance
        point_id = uuid4()
        payload: dict[str, object] = {
            "user_id": user_id,
            "project_id": project_id,
            "scope": fact.scope,
            "type": fact.type,
            "valid": True,
            "importance": imp,
            "decay_rate": self._default_decay_rate,
            "embedding_model": self._embedding_model_label,
            "created_at": now,
            "last_accessed_at": now,
            "source_session": session_id,
            "text": fact.text,
        }
        self._client.upsert(
            collection_name=collection,
            points=[
                qmodels.PointStruct(id=str(point_id), vector=vector, payload=payload),
            ],
        )
        return point_id
