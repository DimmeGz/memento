# memento-vectors

Shared vector layer for memento: Ollama embeddings, Qdrant facts store, and RRF merge helper.

Used by **mcp-server** (`remember`, `recall`, `get_core_context`) and **consolidator** (background fact extraction).

## Install

From the memento repo root with `venv` activated:

```bash
pip install -e ./shared/memento_vectors
```

## Modules

| Module | Purpose |
|--------|---------|
| `memento_vectors.models` | `ExtractedFact`, `parse_facts_json` |
| `memento_vectors.ollama_client` | `OllamaClient` — chat extraction + embeddings |
| `memento_vectors.facts_store` | `FactsStore` — Qdrant collection lifecycle, dedup, upsert, search, scroll |
| `memento_vectors.rrf` | `rrf_merge` — Reciprocal Rank Fusion for multi-source recall |

## Environment

Reads the same Qdrant/Ollama variables as consolidator and MCP (from root `.env` via `MEMENTO_ENV_ROOT`):

- `QDRANT_URL`, `QDRANT_COLLECTION_PREFIX`
- `OLLAMA_BASE_URL`, `OLLAMA_EMBEDDING_MODEL` (MCP); `OLLAMA_CONSOLIDATION_MODEL` (consolidator chat)
