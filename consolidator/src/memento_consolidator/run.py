"""CLI entrypoint for the consolidation worker."""

from __future__ import annotations

import argparse
import json as _json
import logging
import sys

from pydantic import ValidationError

from memento_core.db.repository import (
    claim_pending_conversations,
    fetch_messages_for_conversation,
    mark_conversation_processed,
    reclaim_stale_in_progress,
    reset_conversation_to_pending,
)
from memento_core.env_loader import load_memento_env

from memento_vectors.facts_store import FactsStore
from memento_vectors.ollama_client import OllamaClient
from memento_consolidator.settings import load_consolidator_settings


def _build_transcript(messages: list[tuple[str, str]]) -> str:
    lines: list[str] = []
    for role, content in messages:
        lines.append(f"{role.upper()}: {content}")
    return "\n".join(lines)


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(message)s",
        stream=sys.stderr,
    )


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Consolidate pending conversations into Qdrant facts.")
    parser.add_argument(
        "--reclaim-stale",
        action="store_true",
        help="Reset in_progress conversations older than stale window back to pending.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Max conversations to claim this run (default: CONSOLIDATOR_BATCH_SIZE).",
    )
    parser.add_argument(
        "--stale-minutes",
        type=int,
        default=None,
        help="Age threshold for --reclaim-stale (default: CONSOLIDATOR_STALE_MINUTES).",
    )
    args = parser.parse_args(argv)

    _configure_logging()
    log = logging.getLogger("memento-consolidator")

    try:
        load_memento_env()
        settings = load_consolidator_settings()
    except RuntimeError as e:
        log.error("%s", e)
        return 1

    stale_minutes = args.stale_minutes if args.stale_minutes is not None else settings.stale_minutes
    batch_size = args.batch_size if args.batch_size is not None else settings.batch_size

    if args.reclaim_stale:
        n = reclaim_stale_in_progress(settings.database_url, stale_minutes=stale_minutes)
        log.info("Reclaimed %d stale in_progress conversation(s).", n)

    try:
        claimed = claim_pending_conversations(settings.database_url, limit=batch_size)
    except Exception:
        log.exception("Failed to claim pending conversations.")
        return 1

    if not claimed:
        log.info("No pending conversations to process.")
        return 0

    initialized_projects: set[str] = set()
    vector_size: int | None = None

    from qdrant_client import QdrantClient

    qdrant = QdrantClient(url=settings.qdrant_url)
    store = FactsStore(
        client=qdrant,
        collection_prefix=settings.qdrant_collection_prefix,
        dedup_threshold=settings.dedup_threshold,
        embedding_model_label=settings.ollama_embedding_model,
        default_importance=settings.default_importance,
        default_decay_rate=settings.default_decay_rate,
    )

    with OllamaClient(
        base_url=settings.ollama_base_url,
        chat_model=settings.ollama_chat_model,
        embedding_model=settings.ollama_embedding_model,
    ) as ollama:
        for row in claimed:
            cid = row.id
            try:
                messages = fetch_messages_for_conversation(settings.database_url, cid)
                transcript = _build_transcript(messages)
                if settings.transcript_max_chars is not None and len(transcript) > settings.transcript_max_chars:
                    transcript = transcript[-settings.transcript_max_chars :]

                try:
                    facts = ollama.extract_facts(transcript)
                except (ValidationError, _json.JSONDecodeError, ValueError) as e:
                    log.warning(
                        "Conversation %s: model returned unparseable output (%s); marking processed with 0 facts.",
                        cid,
                        e,
                    )
                    mark_conversation_processed(settings.database_url, cid)
                    continue
                log.info(
                    "Conversation %s: extracted %d fact(s) (session=%s user=%s project=%s).",
                    cid,
                    len(facts),
                    row.session_id,
                    row.user_id,
                    row.project_id,
                )

                for fact in facts:
                    imp = fact.importance if fact.importance is not None else settings.default_importance
                    if imp < settings.min_importance:
                        log.info(
                            "Skipped low-importance fact (%.2f < %.2f) for conversation %s.",
                            imp,
                            settings.min_importance,
                            cid,
                        )
                        continue

                    vec = ollama.embed(fact.text)
                    if row.project_id not in initialized_projects:
                        vector_size = len(vec)
                        store.ensure_collection(vector_size, row.project_id)
                        initialized_projects.add(row.project_id)
                    elif len(vec) != vector_size:
                        raise RuntimeError(
                            f"Embedding length mismatch: expected {vector_size}, got {len(vec)}."
                        )

                    if store.is_near_duplicate(
                        vector=vec,
                        user_id=row.user_id,
                        project_id=row.project_id,
                        scope=fact.scope,
                    ):
                        log.info("Skipped near-duplicate fact for conversation %s.", cid)
                        continue

                    store.upsert_fact(
                        vector=vec,
                        user_id=row.user_id,
                        project_id=row.project_id,
                        session_id=row.session_id,
                        fact=fact,
                    )

                mark_conversation_processed(settings.database_url, cid)
                log.info("Conversation %s marked processed.", cid)
            except Exception:
                log.exception("Failed processing conversation %s; resetting to pending.", cid)
                try:
                    reset_conversation_to_pending(settings.database_url, cid)
                except Exception:
                    log.exception("Could not reset conversation %s to pending.", cid)
                continue

    return 0


def main() -> None:
    raise SystemExit(run())
