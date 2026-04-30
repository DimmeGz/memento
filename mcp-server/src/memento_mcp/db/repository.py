"""Synchronous Postgres persistence for MCP tools."""

from __future__ import annotations

import psycopg
from psycopg.rows import tuple_row

from memento_mcp.config import Settings


def log_message(
    settings: Settings,
    *,
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
    with psycopg.connect(settings.database_url, row_factory=tuple_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                upsert_sql,
                {
                    "user_id": settings.user_id,
                    "project_id": settings.project_id,
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
