"""HTTP client for Ollama chat and embeddings."""

from __future__ import annotations

import json
from typing import Any

import httpx

from memento_consolidator.models import ExtractedFact, parse_facts_json

_SYSTEM_PROMPT = """You are a memory consolidation assistant. Given a dialogue transcript, extract \
standalone factual memories worth storing long-term.

Rules:
- Output ONLY valid JSON: an array of objects. No markdown fences, no commentary.
- Each object fields: "text" (string, the fact), "scope" ("user" or "project"), \
"type" ("episodic", "semantic", or "procedural"), optional "importance" (0..1 float).
- "user" scope: facts about the human (preferences, identity, habits).
- "project" scope: facts about the codebase, team conventions, or technical context tied to the project.
- Skip trivial greetings or one-off noise. Merge duplicates mentally.
- Do NOT extract bugs, errors, or problems that were identified AND resolved within the same conversation.
- Only extract facts that represent the FINAL, stable state at the end of the conversation.
- Skip debugging steps, error messages, intermediate attempts, and temporary workarounds.
- Before storing a fact ask yourself: "Would this still be true and useful in a month?" If no — skip it.
- "episodic" type is for significant decisions or milestones, NOT for transient issues or resolved problems.
- Assign "importance" honestly: stable architectural/preference facts 0.7–1.0; one-time events 0.3–0.5.
"""


class OllamaClient:
    def __init__(
        self,
        *,
        base_url: str,
        chat_model: str,
        embedding_model: str,
        timeout_s: float = 600.0,
    ) -> None:
        self._chat_model = chat_model
        self._embedding_model = embedding_model
        self._client = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout_s)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> OllamaClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def extract_facts(self, transcript: str) -> list[ExtractedFact]:
        body: dict[str, Any] = {
            "model": self._chat_model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Transcript:\n\n{transcript}\n\nReturn JSON array only.",
                },
            ],
            "stream": False,
            "format": "json",
        }
        r = self._client.post("/api/chat", json=body)
        r.raise_for_status()
        payload = r.json()
        msg = payload.get("message") or {}
        content = msg.get("content")
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError(f"Unexpected Ollama chat response: {payload!r}")
        facts = parse_facts_json(content.strip())
        return facts

    def embed(self, text: str) -> list[float]:
        # Ollama v0.5+ uses POST /api/embed with "input" (string or list).
        body = {"model": self._embedding_model, "input": text}
        r = self._client.post("/api/embed", json=body)
        if r.status_code == 404:
            body_legacy = {"model": self._embedding_model, "prompt": text}
            r = self._client.post("/api/embeddings", json=body_legacy)
        r.raise_for_status()
        data = r.json()
        emb = data.get("embedding")
        if isinstance(emb, list):
            return [float(x) for x in emb]
        embeds = data.get("embeddings")
        if isinstance(embeds, list) and embeds and isinstance(embeds[0], list):
            return [float(x) for x in embeds[0]]
        raise RuntimeError(f"Unexpected Ollama embed response: {json.dumps(data)[:500]}")
