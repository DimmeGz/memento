# Memento

Long-term memory for LLM assistants. Memento logs chat turns, extracts structured facts from conversations, and (planned) injects relevant context back into future sessions.

Designed for local development first, with a path toward a shared team deployment. Integrates with **Cursor**, **Claude Code**, and **OpenWebUI** via the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/).

## How it works

```
Cursor / Claude Code / OpenWebUI
              │
    MCP Memory Server (always on)
    ├── log_message()       → PostgreSQL (raw logs, pending queue)
    ├── remember()          → Qdrant (explicit facts)
    ├── recall()            → Qdrant (hybrid search)
    └── get_core_context()  → Qdrant (always-on prompt context)
              │
    Memory Consolidator (cron / worker)
    └── pending dialogues → Ollama → dedupe → Qdrant facts
```

**Two services:**

| Service | Role |
|---------|------|
| **mcp-server** | Stdio MCP server exposed to the IDE. Logs messages and serves memory tools. |
| **consolidator** | Background worker. Claims `pending` conversations from PostgreSQL, extracts facts via Ollama, embeds and upserts into Qdrant. |

Shared persistence and migrations live in **memento-core**.

## Memory model

Three memory types:

| Type | Description |
|------|-------------|
| **Episodic** | Specific events from conversations |
| **Semantic** | Generalized facts about a user or project |
| **Procedural** | Rules, workflows, and instructions |

Facts are scoped for isolation:

| Scope | Description |
|-------|-------------|
| `user` | Facts about the person, independent of project |
| `project` | Facts tied to a codebase or team (visible to colleagues on the same project) |
| `shared` | Planned — team-wide conventions across projects |

## Tech stack

- **Python 3.11+**
- **PostgreSQL** — raw message logs, conversation queue
- **Qdrant** — vector store with payload filtering
- **Ollama** — local LLM for fact extraction and embeddings
- **MCP** — client integration (`mcp>=1.2`, FastMCP)
- **Alembic + SQLAlchemy 2 + psycopg 3** — schema and migrations

Planned search: hybrid BM25 + vector retrieval with Reciprocal Rank Fusion (RRF). See [memory-system-architecture-concept.md](memory-system-architecture-concept.md) for the full design.

## Repository layout

```
memento/
├── shared/memento_core/   # PostgreSQL access, Alembic migrations
├── shared/memento_vectors/ # Ollama embeddings, Qdrant facts store, RRF
├── mcp-server/            # memento-mcp — MCP server
├── consolidator/          # memento-consolidator — background worker
├── config.toml            # [core_context] limits (committed)
├── config.local.toml      # [user].id, [project].id (gitignored)
├── .env                   # secrets and service URLs (gitignored)
└── memory-system-architecture-concept.md
```

Package-specific setup and usage:

- [mcp-server/README.md](mcp-server/README.md)
- [consolidator/README.md](consolidator/README.md)
- [shared/memento_core/README.md](shared/memento_core/README.md)
- [shared/memento_vectors/README.md](shared/memento_vectors/README.md)

## Prerequisites

- Python **3.11+**
- Running **PostgreSQL** instance
- **Qdrant** (for consolidator and MCP memory tools)
- **Ollama** with consolidation and embedding models pulled locally (for consolidator and MCP)

## Quick start

Use one virtualenv at the repository root:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -e ./shared/memento_core
pip install -e ./shared/memento_vectors
pip install -e ./mcp-server
pip install -e ./consolidator
```

Copy and fill in configuration:

```bash
cp .env.example .env
cp config.local.toml.example config.local.toml
# Edit .env — set DATABASE_URL, QDRANT_URL, Ollama models, etc.
# Edit config.local.toml — set stable user and project IDs
```

Apply database migrations:

```bash
export MEMENTO_ENV_ROOT="$(pwd)"
set -a && source .env && set +a
cd shared/memento_core && alembic upgrade head
```

Run the MCP server:

```bash
export MEMENTO_ENV_ROOT="$(pwd)"
export MEMENTO_WORKSPACE_ROOT="$(pwd)"   # same path when developing inside this repo
python -m memento_mcp
```

Run the consolidator (after logging at least one conversation via MCP):

```bash
export MEMENTO_ENV_ROOT="$(pwd)"
memento-consolidator
```

## Configuration

Two roots are required at runtime:

| Variable | Purpose |
|----------|---------|
| **`MEMENTO_ENV_ROOT`** | Absolute path to this memento checkout. Loads root `.env` (`DATABASE_URL`, Qdrant, Ollama). |
| **`MEMENTO_WORKSPACE_ROOT`** | Absolute path to the project you are working in. Reads `config.local.toml` and optional `config.toml`. |

When developing inside the memento repo itself, set both to the same path. When using memento from another repository, point `MEMENTO_ENV_ROOT` here and `MEMENTO_WORKSPACE_ROOT` at the opened project.

`user_id` and `project_id` are read from `config.local.toml` only — they are not MCP tool parameters, so clients cannot override them.

### Environment variables

See [.env.example](.env.example). Key entries:

| Variable | Required by | Description |
|----------|-------------|-------------|
| `DATABASE_URL` | MCP, consolidator | PostgreSQL connection string |
| `QDRANT_URL` | MCP, consolidator | Qdrant HTTP endpoint |
| `QDRANT_COLLECTION_PREFIX` | MCP, consolidator | Collection name prefix (default `facts`) |
| `OLLAMA_BASE_URL` | MCP, consolidator | Ollama HTTP endpoint |
| `OLLAMA_CONSOLIDATION_MODEL` | consolidator | Chat model for fact extraction |
| `OLLAMA_EMBEDDING_MODEL` | MCP, consolidator | Embedding model |

## MCP tools

| Tool | Status |
|------|--------|
| `log_message(message, role, session_id)` | Implemented — upserts conversation, inserts message row |
| `remember(fact, scope, type)` | Implemented — embed, dedup, upsert to Qdrant |
| `recall(query)` | Implemented — vector search (user + project), RRF merge |
| `get_core_context()` | Implemented — high-importance semantic/procedural facts |

### Cursor integration

Add to your MCP config (use absolute paths):

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

## Implementation status

| Component | Status |
|-----------|--------|
| Dialogue logging (MCP → PostgreSQL) | Done |
| Consolidator (PostgreSQL → Ollama → Qdrant) | Done |
| `recall`, `remember`, `get_core_context` | Done |
| Hybrid BM25 + vector search | Planned |
| Shared scope, fact invalidation, activity decay | Roadmap |

For architecture details, data flows, metadata schema, and future plans, see [memory-system-architecture-concept.md](memory-system-architecture-concept.md).
