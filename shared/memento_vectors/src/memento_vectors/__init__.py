"""Shared Ollama embeddings and Qdrant facts store for memento."""

from memento_vectors.facts_store import FactsStore
from memento_vectors.models import ExtractedFact, parse_facts_json
from memento_vectors.ollama_client import OllamaClient
from memento_vectors.rrf import rrf_merge

__all__ = [
    "ExtractedFact",
    "FactsStore",
    "OllamaClient",
    "parse_facts_json",
    "rrf_merge",
]
