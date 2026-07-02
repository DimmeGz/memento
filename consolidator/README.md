# memento-consolidator

Worker that claims pending conversations from PostgreSQL, extracts structured facts via Ollama, deduplicates with Qdrant cosine similarity, and upserts into the `facts` collection.

Install (repo-root `venv` activated):

```bash
pip install -e ./shared/memento_core
pip install -e ./shared/memento_vectors
pip install -e ./consolidator
```

Requires root `.env` at `MEMENTO_ENV_ROOT` — see repository `.env.example`.

Run:

```bash
export MEMENTO_ENV_ROOT=/absolute/path/to/memento
source /absolute/path/to/memento/venv/bin/activate
memento-consolidator --help
```

Optional flags: `--reclaim-stale`, `--batch-size`, `--stale-minutes`.

## Smoke checklist

1. Root **`venv`** active; **`pip install -e ./shared/memento_core`**, **`pip install -e ./shared/memento_vectors`**, then **`pip install -e ./consolidator`** (and MCP if needed).
2. PostgreSQL up; **`alembic upgrade head`** from **`shared/memento_core`** with **`DATABASE_URL`** loaded from root **`.env`**.
3. Qdrant listening on **`QDRANT_URL`**; Ollama running with **`OLLAMA_CONSOLIDATION_MODEL`** and **`OLLAMA_EMBEDDING_MODEL`** pulled locally.
4. Append at least one turn via MCP **`log_message`** so a **`pending`** row exists.
5. **`memento-consolidator`** — expect logs, **`processed`** status on the conversation, and new points in collection **`QDRANT_COLLECTION`** (default **`facts`**).
