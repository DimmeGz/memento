"""Load workspace configuration from env and TOML."""

from __future__ import annotations

import os
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


DEFAULT_CORE_CONTEXT: dict[str, object] = {
    "user_limit": 10,
    "project_limit": 10,
    "importance_threshold": 0.75,
}


@dataclass(frozen=True, slots=True)
class Settings:
    """project_root is the client workspace; secrets load from MEMENTO_ENV_ROOT."""

    workspace_root: Path
    database_url: str
    user_id: str
    project_id: str
    core_context: dict[str, object]


_settings: Settings | None = None


def _die(message: str, *, code: int = 1) -> None:
    sys.stderr.write(f"{message}\n")
    sys.exit(code)


def _resolve_root(var_name: str) -> Path:
    raw = os.environ.get(var_name, "").strip()
    if not raw:
        _die(f"{var_name} is required and must point to an existing directory.")
    path = Path(raw).expanduser().resolve()
    if not path.is_dir():
        _die(f"{var_name} is not a directory: {path}")
    return path


def _merge_core_context(root: Path) -> dict[str, object]:
    merged = dict(DEFAULT_CORE_CONTEXT)
    cfg = root / "config.toml"
    if cfg.is_file():
        with cfg.open("rb") as fh:
            data = tomllib.load(fh)
        section = data.get("core_context")
        if isinstance(section, dict):
            merged.update(section)
    return merged


def _load_settings_impl() -> Settings:
    env_root = _resolve_root("MEMENTO_ENV_ROOT")
    project_root = _resolve_root("MEMENTO_WORKSPACE_ROOT")

    load_dotenv(env_root / ".env", override=False)

    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        _die("DATABASE_URL is required in the environment after loading .env.")

    local_path = project_root / "config.local.toml"
    if not local_path.is_file():
        _die(f"Missing config.local.toml at {local_path}")

    with local_path.open("rb") as fh:
        local = tomllib.load(fh)

    try:
        user_id = str(local["user"]["id"]).strip()
        project_id = str(local["project"]["id"]).strip()
    except (KeyError, TypeError):
        _die("config.local.toml must contain [user].id and [project].id as non-empty strings.")

    if not user_id or not project_id:
        _die("config.local.toml [user].id and [project].id must be non-empty after strip.")

    core_context = _merge_core_context(project_root)

    return Settings(
        workspace_root=project_root,
        database_url=database_url,
        user_id=user_id,
        project_id=project_id,
        core_context=core_context,
    )


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = _load_settings_impl()
    return _settings
