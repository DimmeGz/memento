"""Synchronous Postgres persistence."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import psycopg
from psycopg.rows import tuple_row


@dataclass(frozen=True, slots=True)
class ConversationRow:
    id: UUID
    user_id: str
    project_id: str
    session_id: str


def log_message(
    database_url: str,
    *,
    user_id: str,
    project_id: str,
    session_id: str,
    role: str,
    content: str,
) -> None:
    upsert_sql = """
        INSERT INTO conversations (user_id, project_id, session_id, status)
        VALUES (%(user_id)s, %(project_id)s, %(session_id)s, 'pending')
        ON CONFLICT (user_id, project_id, session_id)
        DO UPDATE SET updated_at = NOW()
        RETURNING id
    """
    insert_msg_sql = """
        INSERT INTO messages (conversation_id, role, content)
        VALUES (%(conversation_id)s, %(role)s, %(content)s)
    """
    with psycopg.connect(database_url, row_factory=tuple_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                upsert_sql,
                {
                    "user_id": user_id,
                    "project_id": project_id,
                    "session_id": session_id,
                },
            )
            row = cur.fetchone()
            if row is None:
                raise RuntimeError("Conversation upsert returned no row.")
            conversation_id = row[0]
            cur.execute(
                insert_msg_sql,
                {
                    "conversation_id": conversation_id,
                    "role": role,
                    "content": content,
                },
            )
        conn.commit()


def claim_pending_conversations(database_url: str, *, limit: int) -> list[ConversationRow]:
    sql = """
        WITH picked AS (
            SELECT id FROM conversations
            WHERE status = 'pending'
            ORDER BY updated_at ASC NULLS FIRST
            FOR UPDATE SKIP LOCKED
            LIMIT %(limit)s
        )
        UPDATE conversations AS c
        SET status = 'in_progress', updated_at = NOW()
        FROM picked AS p
        WHERE c.id = p.id
        RETURNING c.id, c.user_id, c.project_id, c.session_id
    """
    rows: list[ConversationRow] = []
    with psycopg.connect(database_url, row_factory=tuple_row) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(sql, {"limit": limit})
                for r in cur.fetchall():
                    rows.append(
                        ConversationRow(
                            id=r[0],
                            user_id=r[1],
                            project_id=r[2],
                            session_id=r[3],
                        )
                    )
    return rows


def fetch_messages_for_conversation(database_url: str, conversation_id: UUID) -> list[tuple[str, str]]:
    sql = """
        SELECT role, content FROM messages
        WHERE conversation_id = %(cid)s
        ORDER BY created_at ASC NULLS FIRST
    """
    with psycopg.connect(database_url, row_factory=tuple_row) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"cid": conversation_id})
            return [(str(r[0]), str(r[1])) for r in cur.fetchall()]


def mark_conversation_processed(database_url: str, conversation_id: UUID) -> None:
    sql = """
        UPDATE conversations
        SET status = 'processed', updated_at = NOW()
        WHERE id = %(cid)s AND status = 'in_progress'
    """
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"cid": conversation_id})
        conn.commit()


def reset_conversation_to_pending(database_url: str, conversation_id: UUID) -> None:
    sql = """
        UPDATE conversations
        SET status = 'pending', updated_at = NOW()
        WHERE id = %(cid)s AND status = 'in_progress'
    """
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"cid": conversation_id})
        conn.commit()


def reclaim_stale_in_progress(database_url: str, *, stale_minutes: int) -> int:
    sql = """
        UPDATE conversations
        SET status = 'pending', updated_at = NOW()
        WHERE status = 'in_progress'
          AND updated_at < NOW() - %(mins)s * INTERVAL '1 minute'
    """
    with psycopg.connect(database_url) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(sql, {"mins": stale_minutes})
                return int(cur.rowcount)
