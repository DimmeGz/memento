"""Memory tool helpers: Qdrant/Ollama clients, recall, remember, core context."""

from __future__ import annotations

import os
from typing import Any, Literal, cast

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from memento_mcp.config import Settings
from memento_vectors.facts_store import FactsStore
from memento_vectors.models import ExtractedFact
from memento_vectors.ollama_client import OllamaClient
from memento_vectors.rrf import rrf_merge

EXPLICIT_SESSION_ID = "mcp-remember"
EMPTY_MESSAGE = "(no relevant memories)"


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    return float(raw)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    return int(raw)


def create_facts_store(settings: Settings) -> FactsStore:
    client = QdrantClient(url=settings.qdrant_url)
    return FactsStore(
        client=client,
        collection_prefix=settings.qdrant_collection_prefix,
        dedup_threshold=_env_float("CONSOLIDATOR_DEDUP_THRESHOLD", 0.97),
        embedding_model_label=settings.ollama_embedding_model,
        default_importance=_env_float("CONSOLIDATOR_DEFAULT_IMPORTANCE", 0.7),
        default_decay_rate=_env_float("CONSOLIDATOR_DEFAULT_DECAY_RATE", 0.01),
    )


def create_ollama_client(settings: Settings) -> OllamaClient:
    return OllamaClient(
        base_url=settings.ollama_base_url,
        embedding_model=settings.ollama_embedding_model,
    )


def format_facts(payloads: list[dict[str, Any]]) -> str:
    if not payloads:
        return EMPTY_MESSAGE
    lines: list[str] = []
    for payload in payloads:
        scope = payload.get("scope", "?")
        fact_type = payload.get("type", "?")
        text = payload.get("text", "")
        lines.append(f"- [{scope}/{fact_type}] {text}")
    return "\n".join(lines)


def remember_fact(settings: Settings, *, fact: str, scope: str, memory_type: str) -> str:
    store = create_facts_store(settings)
    with create_ollama_client(settings) as ollama:
        vec = ollama.embed(fact)
        store.ensure_collection(len(vec), settings.project_id)
        extracted = ExtractedFact(
            text=fact,
            scope=cast(Literal["user", "project"], scope),
            type=cast(Literal["episodic", "semantic", "procedural"], memory_type),
        )
        if store.is_near_duplicate(
            vector=vec,
            user_id=settings.user_id,
            project_id=settings.project_id,
            scope=scope,
        ):
            return "already known"
        store.upsert_fact(
            vector=vec,
            user_id=settings.user_id,
            project_id=settings.project_id,
            session_id=EXPLICIT_SESSION_ID,
            fact=extracted,
        )
    return "ok"


def recall_memories(settings: Settings, *, query: str) -> str:
    store = create_facts_store(settings)
    if not store.collection_exists(settings.project_id):
        return EMPTY_MESSAGE

    recall_cfg = settings.recall
    limit = int(recall_cfg["limit"])
    rrf_k = int(recall_cfg["rrf_k"])

    with create_ollama_client(settings) as ollama:
        vec = ollama.embed(query)

        user_hits = store.search(
            vector=vec,
            project_id=settings.project_id,
            must=[
                qmodels.FieldCondition(key="scope", match=qmodels.MatchValue(value="user")),
                qmodels.FieldCondition(key="user_id", match=qmodels.MatchValue(value=settings.user_id)),
                qmodels.FieldCondition(key="valid", match=qmodels.MatchValue(value=True)),
            ],
            limit=limit,
        )
        project_hits = store.search(
            vector=vec,
            project_id=settings.project_id,
            must=[
                qmodels.FieldCondition(key="scope", match=qmodels.MatchValue(value="project")),
                qmodels.FieldCondition(key="project_id", match=qmodels.MatchValue(value=settings.project_id)),
                qmodels.FieldCondition(key="valid", match=qmodels.MatchValue(value=True)),
            ],
            limit=limit,
        )

    user_ranking = [(pid, payload) for pid, payload, _score in user_hits]
    project_ranking = [(pid, payload) for pid, payload, _score in project_hits]
    merged = rrf_merge([user_ranking, project_ranking], k=rrf_k, limit=limit)

    if not merged:
        return EMPTY_MESSAGE

    point_ids = [hit.point_id for hit in merged]
    store.touch_last_accessed(project_id=settings.project_id, point_ids=point_ids)
    return format_facts([hit.payload for hit in merged])


def get_core_context_memories(settings: Settings) -> str:
    store = create_facts_store(settings)
    cfg = settings.core_context
    importance_threshold = float(cfg["importance_threshold"])
    user_limit = int(cfg["user_limit"])
    project_limit = int(cfg["project_limit"])
    types = ("semantic", "procedural")

    user_facts = store.scroll_core_context(
        project_id=settings.project_id,
        scope="user",
        id_field="user_id",
        id_value=settings.user_id,
        importance_threshold=importance_threshold,
        types=types,
        limit=user_limit,
    )
    project_facts = store.scroll_core_context(
        project_id=settings.project_id,
        scope="project",
        id_field="project_id",
        id_value=settings.project_id,
        importance_threshold=importance_threshold,
        types=types,
        limit=project_limit,
    )
    return format_facts(user_facts + project_facts)
