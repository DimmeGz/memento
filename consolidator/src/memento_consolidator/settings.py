"""Load consolidator configuration from environment (after root ``.env``)."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _f(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    return float(raw)


def _i(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    return int(raw)


def _opt_int(name: str) -> int | None:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    return int(raw)


def _req(name: str) -> str:
    v = os.environ.get(name, "").strip()
    if not v:
        raise RuntimeError(f"{name} must be set in the root memento .env for consolidator.")
    return v


@dataclass(frozen=True, slots=True)
class ConsolidatorSettings:
    database_url: str
    qdrant_url: str
    qdrant_collection_prefix: str
    ollama_base_url: str
    ollama_chat_model: str
    ollama_embedding_model: str
    dedup_threshold: float
    batch_size: int
    stale_minutes: int
    default_importance: float
    default_decay_rate: float
    min_importance: float
    transcript_max_chars: int | None


def load_consolidator_settings() -> ConsolidatorSettings:
    database_url = _req("DATABASE_URL")
    return ConsolidatorSettings(
        database_url=database_url,
        qdrant_url=os.environ.get("QDRANT_URL", "http://127.0.0.1:6333").strip(),
        qdrant_collection_prefix=os.environ.get("QDRANT_COLLECTION_PREFIX", "facts").strip(),
        ollama_base_url=os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").strip(),
        ollama_chat_model=_req("OLLAMA_CONSOLIDATION_MODEL"),
        ollama_embedding_model=_req("OLLAMA_EMBEDDING_MODEL"),
        dedup_threshold=_f("CONSOLIDATOR_DEDUP_THRESHOLD", 0.97),
        batch_size=_i("CONSOLIDATOR_BATCH_SIZE", 10),
        stale_minutes=_i("CONSOLIDATOR_STALE_MINUTES", 30),
        default_importance=_f("CONSOLIDATOR_DEFAULT_IMPORTANCE", 0.7),
        default_decay_rate=_f("CONSOLIDATOR_DEFAULT_DECAY_RATE", 0.01),
        min_importance=_f("CONSOLIDATOR_MIN_IMPORTANCE", 0.5),
        transcript_max_chars=_opt_int("CONSOLIDATOR_TRANSCRIPT_MAX_CHARS"),
    )
