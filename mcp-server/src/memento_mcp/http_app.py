"""HTTP webhook for client hooks and universal integrations."""

from __future__ import annotations

import json
import os
from typing import Any

from memento_mcp.config import Settings
from memento_mcp.services.context import get_core_context_text
from memento_mcp.services.logging import log_conversation_message
from memento_mcp.validation import ValidationError, validate_log_message

try:
    from starlette.applications import Starlette
    from starlette.middleware import Middleware
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import JSONResponse, Response
    from starlette.routing import Route
except ImportError as exc:  # pragma: no cover - exercised via cli serve guard
    raise ImportError(
        'HTTP support requires optional dependencies. Install with: pip install "memento-mcp[http]"'
    ) from exc


def _json_response(data: dict[str, Any], *, status_code: int = 200) -> JSONResponse:
    return JSONResponse(data, status_code=status_code)


def _error_response(message: str, *, status_code: int) -> JSONResponse:
    return _json_response({"error": message}, status_code=status_code)


def _extract_session_id(payload: dict[str, Any]) -> str:
    for key in ("session_id", "conversation_id"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _extract_user_message(payload: dict[str, Any]) -> str:
    prompt = payload.get("prompt")
    if isinstance(prompt, str) and prompt.strip():
        return prompt.strip()
    message = payload.get("message")
    if isinstance(message, str) and message.strip():
        return message.strip()
    return ""


def _extract_assistant_message(payload: dict[str, Any]) -> str:
    for key in ("last_assistant_message", "text", "message"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def create_app(settings: Settings, *, hook_token: str = "") -> Starlette:
    class AuthMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next: Any) -> Response:
            if request.url.path == "/health":
                return await call_next(request)

            client_host = request.client.host if request.client else ""
            if hook_token:
                auth = request.headers.get("authorization", "")
                expected = f"Bearer {hook_token}"
                if auth != expected:
                    return _error_response("unauthorized", status_code=401)
            elif client_host not in {"127.0.0.1", "::1", "testclient"}:
                return _error_response("forbidden", status_code=403)

            return await call_next(request)

    async def health(_request: Request) -> Response:
        return _json_response({"status": "ok"})

    async def core_context(_request: Request) -> Response:
        text = get_core_context_text(settings)
        return _json_response({"additional_context": text})

    async def log_endpoint(request: Request) -> Response:
        try:
            payload = await request.json()
        except json.JSONDecodeError:
            return _error_response("invalid JSON body", status_code=400)
        if not isinstance(payload, dict):
            return _error_response("body must be a JSON object", status_code=400)

        try:
            data = validate_log_message(
                message=str(payload.get("message", "")),
                role=str(payload.get("role", "")),
                session_id=str(payload.get("session_id", "")),
            )
        except ValidationError as exc:
            return _error_response(str(exc), status_code=400)

        log_conversation_message(settings, data)
        return _json_response({"status": "ok"})

    async def log_user_hook(request: Request) -> Response:
        try:
            payload = await request.json()
        except json.JSONDecodeError:
            return _error_response("invalid JSON body", status_code=400)
        if not isinstance(payload, dict):
            return _error_response("body must be a JSON object", status_code=400)

        session_id = _extract_session_id(payload)
        message = _extract_user_message(payload)
        try:
            data = validate_log_message(message=message, role="user", session_id=session_id)
        except ValidationError as exc:
            return _error_response(str(exc), status_code=400)

        log_conversation_message(settings, data)
        return _json_response({"status": "ok"})

    async def log_assistant_hook(request: Request) -> Response:
        try:
            payload = await request.json()
        except json.JSONDecodeError:
            return _error_response("invalid JSON body", status_code=400)
        if not isinstance(payload, dict):
            return _error_response("body must be a JSON object", status_code=400)

        session_id = _extract_session_id(payload)
        message = _extract_assistant_message(payload)
        try:
            data = validate_log_message(message=message, role="assistant", session_id=session_id)
        except ValidationError as exc:
            return _error_response(str(exc), status_code=400)

        log_conversation_message(settings, data)
        return _json_response({"status": "ok"})

    routes = [
        Route("/health", health, methods=["GET"]),
        Route("/v1/core-context", core_context, methods=["GET"]),
        Route("/v1/log", log_endpoint, methods=["POST"]),
        Route("/v1/hooks/log-user", log_user_hook, methods=["POST"]),
        Route("/v1/hooks/log-assistant", log_assistant_hook, methods=["POST"]),
    ]
    return Starlette(routes=routes, middleware=[Middleware(AuthMiddleware)])


def resolve_hook_token() -> str:
    return os.environ.get("MEMENTO_HOOK_TOKEN", "").strip()


def resolve_http_host(default: str = "127.0.0.1") -> str:
    return os.environ.get("MEMENTO_HTTP_HOST", default).strip() or default


def resolve_http_port(default: int = 8765) -> int:
    raw = os.environ.get("MEMENTO_HTTP_PORT", "").strip()
    if not raw:
        return default
    return int(raw)
