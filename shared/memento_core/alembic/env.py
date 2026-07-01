"""Alembic migration environment."""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None


def _sqlalchemy_url(raw: str) -> str:
    """Use psycopg (v3) with Alembic; plain postgresql:// defaults to psycopg2."""
    if raw.startswith("postgresql+psycopg"):
        return raw
    if raw.startswith("postgresql://"):
        return "postgresql+psycopg://" + raw.removeprefix("postgresql://")
    if raw.startswith("postgres://"):
        return "postgresql+psycopg://" + raw.removeprefix("postgres://")
    return raw


def run_migrations_offline() -> None:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL must be set for offline migrations.")
    url = _sqlalchemy_url(url)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL must be set for alembic migrations.")

    db_url = _sqlalchemy_url(db_url)

    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = db_url

    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
