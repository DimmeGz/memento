# memento-mcp

Stdio MCP server that logs chat turns to PostgreSQL (`log_message`) and exposes stub tools for future memory features.

## Prerequisites

- Python **3.11+**
- CLI **`virtualenv`** on your `PATH` (installed by you or your operator — do not `pip install virtualenv` inside this repo as part of the phase-1 plan).
- A running PostgreSQL instance.
- Two roots are always required at runtime (see below): **`MEMENTO_ENV_ROOT`** (memento clone with **`.env`**) and **`MEMENTO_WORKSPACE_ROOT`** (the project you are working in with **`config.local.toml`**).

## Environment variables

| Variable | Required | Purpose |
|----------|----------|---------|
| **`MEMENTO_ENV_ROOT`** | yes | Absolute path to the **memento** repository root. **`load_dotenv`** reads **`{MEMENTO_ENV_ROOT}/.env`** (`DATABASE_URL`). |
| **`MEMENTO_WORKSPACE_ROOT`** | yes | Absolute path to the **current client project** root. Reads **`config.local.toml`** and optional **`config.toml`** (`[core_context]`). |

When you develop **inside the memento repo itself**, set **both** variables to the **same** absolute path (the memento root).

When you use memento-mcp from **another repository**, set **`MEMENTO_ENV_ROOT`** to your memento checkout and **`MEMENTO_WORKSPACE_ROOT`** to that other repo’s root (the folder Cursor opened).

## Layout by root

**Under `MEMENTO_ENV_ROOT` (memento)**

| File | Purpose |
|------|---------|
| **`.env`** | **`DATABASE_URL`** (gitignored in memento — copy from **`.env.example`**) |

**Under `MEMENTO_WORKSPACE_ROOT` (client project)**

| File | Purpose |
|------|---------|
| **`config.local.toml`** | **`[user].id`**, **`[project].id`** (per project; gitignored in templates) |
| **`config.toml`** | Optional **`[core_context]`** |

## Setup

From the memento repository root (`$MEMENTO`):

```bash
cd "$MEMENTO/mcp-server"
virtualenv .venv
source .venv/bin/activate   # Windows: .\.venv\Scripts\activate
pip install -e .
```

Confirm the interpreter is the venv before running **`pip`** or **`python`**:

```bash
python -c 'import sys; assert ".venv" in sys.prefix'
```

Apply migrations (**`DATABASE_URL`** comes from **`$MEMENTO/.env`**):

```bash
cd "$MEMENTO/mcp-server"
source .venv/bin/activate
export DATABASE_URL="$(grep '^DATABASE_URL=' "$MEMENTO/.env" | sed 's/^DATABASE_URL=//')"
alembic upgrade head
```

`alembic/env.py` rewrites `postgresql://` and `postgres://` URLs to **`postgresql+psycopg://`** so migrations use the installed **psycopg** (v3) driver instead of **psycopg2**.

## Running

```bash
export MEMENTO_ENV_ROOT="$MEMENTO"
export MEMENTO_WORKSPACE_ROOT="$MEMENTO"
"$MEMENTO/mcp-server/.venv/bin/python" -m memento_mcp
```

If either variable is missing or not a directory, the process exits with a non-zero status and an English message on stderr (no Python traceback).

## Cursor / MCP client (`mcp.json`)

Use an **absolute path** to the venv Python so the client does not rely on a global interpreter. **`env`** must include **both** roots:

```json
{
  "mcpServers": {
    "memento-memory": {
      "command": "/absolute/path/to/memento/mcp-server/.venv/bin/python",
      "args": ["-m", "memento_mcp"],
      "env": {
        "MEMENTO_ENV_ROOT": "/absolute/path/to/memento",
        "MEMENTO_WORKSPACE_ROOT": "/absolute/path/to/your-open-project"
      }
    }
  }
}
```

For **memento-only** use, set **`MEMENTO_WORKSPACE_ROOT`** and **`MEMENTO_ENV_ROOT`** to the **same** memento path.

Some Cursor builds expand **`${workspaceFolder}`** inside MCP **`env`** values; if yours does, you can set **`MEMENTO_WORKSPACE_ROOT`** to **`${workspaceFolder}`** so the client project tracks the open workspace. If substitution is not supported, use an absolute path to that project’s root.

**`DATABASE_URL`** is loaded only from **`$MEMENTO_ENV_ROOT/.env`**. **`user_id`** / **`project_id`** come only from **`$MEMENTO_WORKSPACE_ROOT/config.local.toml`**, not from **`mcp.json`**.

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
