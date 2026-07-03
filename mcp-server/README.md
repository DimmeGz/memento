# memento-mcp

Stdio MCP server that logs chat turns to PostgreSQL and serves memory tools backed by Qdrant and Ollama embeddings.

## Prerequisites

- Python **3.11+**
- A running PostgreSQL instance.
- Two roots are always required at runtime (see below): **`MEMENTO_ENV_ROOT`** (memento clone with **`.env`**) and **`MEMENTO_WORKSPACE_ROOT`** (the project you are working in with **`config.local.toml`**).

Shared database code lives in **`../shared/memento_core`** (`memento-core` package). Vector layer lives in **`../shared/memento_vectors`** (`memento-vectors`). Install both **before** this package.

## Environment variables

| Variable | Required | Purpose |
|----------|----------|---------|
| **`MEMENTO_ENV_ROOT`** | yes | Absolute path to the **memento** repository root. Root **`.env`** is loaded via **`memento_core.load_memento_env()`** (`DATABASE_URL` and other vars). |
| **`MEMENTO_WORKSPACE_ROOT`** | yes | Absolute path to the **current client project** root. Reads **`config.local.toml`** and optional **`config.toml`** (`[core_context]`, `[recall]`). |

When you develop **inside the memento repo itself**, set **both** variables to the **same** absolute path (the memento root).

When you use memento-mcp from **another repository**, set **`MEMENTO_ENV_ROOT`** to your memento checkout and **`MEMENTO_WORKSPACE_ROOT`** to that other repo’s root (the folder Cursor opened).

## Layout by root

**Under `MEMENTO_ENV_ROOT` (memento)**

| File | Purpose |
|------|---------|
| **`.env`** | **`DATABASE_URL`**, **`QDRANT_URL`**, **`OLLAMA_BASE_URL`**, **`OLLAMA_EMBEDDING_MODEL`**, and optional vars — copy from repository **`.env.example`** (gitignored). |

**Under `MEMENTO_WORKSPACE_ROOT` (client project)**

| File | Purpose |
|------|---------|
| **`config.local.toml`** | **`[user].id`**, **`[project].id`** (per project; gitignored in templates) |
| **`config.toml`** | Optional **`[core_context]`**, **`[recall]`** |

## Setup

Use one virtualenv at the **memento repository root** (`python3 -m venv venv`, then **`source venv/bin/activate`**). Do not install dependencies into the system interpreter.

From **`$MEMENTO`** (repo root):

```bash
python3 -m venv venv
source venv/bin/activate
pip install -e ./shared/memento_core
pip install -e ./shared/memento_vectors
pip install -e ./mcp-server
```

Confirm the interpreter is the venv:

```bash
python -c 'import sys; assert "venv" in sys.prefix'
```

Apply migrations (**`DATABASE_URL`** must be available — export from **`$MEMENTO/.env`** or load manually):

```bash
cd "$MEMENTO/shared/memento_core"
source "$MEMENTO/venv/bin/activate"
set -a && source "$MEMENTO/.env" && set +a
alembic upgrade head
```

`alembic/env.py` rewrites `postgresql://` and `postgres://` URLs to **`postgresql+psycopg://`** so migrations use **psycopg** (v3).

## Running

```bash
export MEMENTO_ENV_ROOT="$MEMENTO"
export MEMENTO_WORKSPACE_ROOT="$MEMENTO"
"$MEMENTO/venv/bin/python" -m memento_mcp
```

If either variable is missing or not a directory, the process exits with a non-zero status and an English message on stderr (no Python traceback).

## CLI (`memento`)

Entry point for deterministic operations (logging, core context, HTTP webhook):

```bash
export MEMENTO_ENV_ROOT="$MEMENTO"
export MEMENTO_WORKSPACE_ROOT="$MEMENTO"

# Log a message
memento log --role user --session-id SESSION_ID --message "Hello"

# Print core context (plain text)
memento core-context

# Print core context as JSON for hooks
memento core-context --json

# Start HTTP webhook (requires pip install "memento-mcp[http]")
memento serve --host 127.0.0.1 --port 8765
```

Exit codes: `0` ok, `1` validation/config error, `2` usage error.

## HTTP webhook

Optional HTTP server for Claude Code `type: http` hooks, OpenWebUI sidecar, or team deployment.

Install: `pip install "memento-mcp[http]"`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/v1/core-context` | Returns `{"additional_context":"..."}` |
| `POST` | `/v1/log` | Body: `{"message","role","session_id"}` |
| `POST` | `/v1/hooks/log-user` | Raw hook JSON → extracts `prompt` + session id |
| `POST` | `/v1/hooks/log-assistant` | Raw hook JSON → extracts assistant text + session id |

### HTTP environment variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `MEMENTO_HOOK_TOKEN` | no | If set, requires `Authorization: Bearer …` on all endpoints except `/health` |
| `MEMENTO_HTTP_HOST` | no | Default bind host for `memento serve` (default `127.0.0.1`) |
| `MEMENTO_HTTP_PORT` | no | Default port for `memento serve` (default `8765`) |

If `MEMENTO_HOOK_TOKEN` is empty, only `127.0.0.1` / `::1` clients are allowed (local dev).

Settings are resolved once at server startup (`get_settings()` fail-fast before `uvicorn.run`).

## Client hook templates

See [`../integrations/README.md`](../integrations/README.md) for Cursor and Claude Code hook installation.

## Cursor / MCP client (`mcp.json`)

Use an **absolute path** to the venv Python:

```json
{
  "mcpServers": {
    "memento-memory": {
      "command": "/absolute/path/to/memento/venv/bin/python",
      "args": ["-m", "memento_mcp"],
      "env": {
        "MEMENTO_ENV_ROOT": "/absolute/path/to/memento",
        "MEMENTO_WORKSPACE_ROOT": "/absolute/path/to/your-open-project"
      }
    }
  }
}
```

**`DATABASE_URL`** is loaded from **`$MEMENTO_ENV_ROOT/.env`**. **`user_id`** / **`project_id`** come only from **`$MEMENTO_WORKSPACE_ROOT/config.local.toml`**, not from **`mcp.json`**.

## Tools

| Tool | Behaviour |
|------|-----------|
| **`log_message`** | Validates **`message`**, **`role`** (`user` \| `assistant`), **`session_id`**; upserts **`conversations`** on **`(user_id, project_id, session_id)`** with **`status='pending'`** for new rows; **`ON CONFLICT`** updates **`updated_at`** only; inserts **`messages`**. |
| **`remember`** | Embeds **`fact`** via Ollama, deduplicates near-identical vectors, upserts into Qdrant with **`scope`** (`user` \| `project`) and **`type`** (`episodic` \| `semantic` \| `procedural`). Returns **`ok`** or **`already known`**. |
| **`recall`** | Vector search over user-scoped and project-scoped facts; merges with RRF; updates **`last_accessed_at`**; returns formatted bullet list. |
| **`get_core_context`** | Returns high-importance **`semantic`** and **`procedural`** facts for user and project (limits and threshold from **`[core_context]`** in **`config.toml`**). |

## Acceptance checks

After **`alembic upgrade head`**, two **`log_message`** calls with the same **`session_id`** and distinct roles should yield **one** conversation row and **two** message rows. Example SQL:

```sql
SELECT id, user_id, project_id, session_id, status, updated_at
FROM conversations ORDER BY created_at DESC LIMIT 5;

SELECT id, conversation_id, role, left(content, 80), created_at
FROM messages ORDER BY created_at DESC LIMIT 10;
```

## Consolidator

Background worker and Qdrant pipeline live in **`../consolidator`**. See **`../consolidator/README.md`** and repository **`.env.example`**.
