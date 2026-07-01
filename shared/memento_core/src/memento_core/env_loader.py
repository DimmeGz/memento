"""Load the single root `.env` for all memento processes."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def _die(message: str, *, code: int = 1) -> None:
    sys.stderr.write(f"{message}\n")
    sys.exit(code)


def load_memento_env(*, override: bool = False) -> Path:
    """
    Resolve MEMENTO_ENV_ROOT to the memento repo root and load ``{root}/.env``.

    Does not exit on missing DATABASE_URL; callers validate variables they need.
    """
    raw = os.environ.get("MEMENTO_ENV_ROOT", "").strip()
    if not raw:
        _die("MEMENTO_ENV_ROOT is required and must point to the memento repository root.")

    root = Path(raw).expanduser().resolve()
    if not root.is_dir():
        _die(f"MEMENTO_ENV_ROOT is not a directory: {root}")

    env_file = root / ".env"
    if env_file.is_file():
        load_dotenv(env_file, override=override)

    return root


def require_env_var(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        _die(f"{name} is required in the environment after loading root .env.")
    return value


def require_database_url() -> str:
    return require_env_var("DATABASE_URL")
