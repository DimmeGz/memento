# memento-mcp

Stdio MCP server that logs chat turns to PostgreSQL (`log_message`) and exposes stub tools for future memory features.

## Prerequisites

- Python **3.11+**
- CLI **`virtualenv`** on your `PATH` (installed by you or your operator — do not `pip install virtualenv` inside this repo as part of the phase-1 plan).
- A running PostgreSQL instance and a **`DATABASE_URL`** in the workspace **`.env`** (see repo root **`.env.example`**).

## Layout

Workspace root (where **`MEMENTO_WORKSPACE_ROOT`** points) must contain:

| File | Purpose |
|------|---------|
| **`.env`** | **`DATABASE_URL`** (gitignored — copy from **`.env.example`**) |
| **`config.local.toml`** | **`[user].id`**, **`[project].id`** (gitignored — copy from **`config.local.toml.example`**) |
| **`config.toml`** | Optional **`[core_context]`** (committed defaults in repo) |

## Setup

From the repository root (`$REPO`):

```bash
cd "$REPO/mcp-server"
virtualenv .venv
source .venv/bin/activate   # Windows: .\.venv\Scripts\activate
pip install -e .
```

Confirm the interpreter is the venv before running **`pip`** or **`python`**:

```bash
python -c 'import sys; assert ".venv" in sys.prefix'
```

Apply migrations (**`DATABASE_URL`** must be exported or present in **`$REPO/.env`** when using tooling that loads it):

```bash
cd "$REPO/mcp-server"
source .venv/bin/activate
export DATABASE_URL="$(grep '^DATABASE_URL=' "$REPO/.env" | sed 's/^DATABASE_URL=//')"
alembic upgrade head
```

`alembic/env.py` rewrites `postgresql://` and `postgres://` URLs to **`postgresql+psycopg://`** so migrations use the installed **psycopg** (v3) driver instead of **psycopg2**.

## Running

```bash
export MEMENTO_WORKSPACE_ROOT="$REPO"
"$REPO/mcp-server/.venv/bin/python" -m memento_mcp
```

Without **`MEMENTO_WORKSPACE_ROOT`**, the process exits with a non-zero status and an English error on stderr (no Python traceback).

## Cursor / MCP client (`mcp.json`)

Use an **absolute path** to the venv Python so the client does not rely on a global interpreter:

```json
{
  "mcpServers": {
    "memento-memory": {
      "command": "/absolute/path/to/memento/mcp-server/.venv/bin/python",
      "args": ["-m", "memento_mcp"],
      "env": {
        "MEMENTO_WORKSPACE_ROOT": "/absolute/path/to/memento"
      }
    }
  }
}
```

**`DATABASE_URL`** is read from **`$MEMENTO_WORKSPACE_ROOT/.env`** via `python-dotenv` when the server starts (override disabled). **`user_id`** / **`project_id`** come only from **`config.local.toml`**, not from **`mcp.json`**.

## Tools (phase 1)

| Tool | Behaviour |
|------|-----------|
| **`log_message`** | Validates **`message`**, **`role`** (`user` \| `assistant`), **`session_id`**; upserts **`conversations`** on **`(user_id, project_id, session_id)`** with **`status='pending'`** for new rows; **`ON CONFLICT`** updates **`updated_at`** only; inserts **`messages`**. |
| **`remember`**, **`recall`**, **`get_core_context`** | Return **`[NOT_IMPLEMENTED] …`** (argument validation only where specified; no SQL). |

## Acceptance checks

After **`alembic upgrade head`**, two **`log_message`** calls with the same **`session_id`** and distinct roles should yield **one** conversation row and **two** message rows. Example SQL:

```sql
SELECT id, user_id, project_id, session_id, status, updated_at
FROM conversations ORDER BY created_at DESC LIMIT 5;

SELECT id, conversation_id, role, left(content, 80), created_at
FROM messages ORDER BY created_at DESC LIMIT 10;
```
