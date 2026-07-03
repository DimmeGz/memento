from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

starlette = pytest.importorskip("starlette")
httpx = pytest.importorskip("httpx")

from starlette.testclient import TestClient  # noqa: E402

from memento_mcp.http_app import create_app  # noqa: E402
from memento_mcp.validation import LogMessageInput  # noqa: E402


@pytest.fixture
def settings() -> MagicMock:
    return MagicMock()


@pytest.fixture
def client(settings: MagicMock) -> TestClient:
    app = create_app(settings, hook_token="")
    return TestClient(app)


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_core_context(client: TestClient, settings: MagicMock) -> None:
    with patch("memento_mcp.http_app.get_core_context_text", return_value="facts here"):
        response = client.get("/v1/core-context")
    assert response.status_code == 200
    assert response.json() == {"additional_context": "facts here"}


def test_log_endpoint(client: TestClient, settings: MagicMock) -> None:
    with patch("memento_mcp.http_app.log_conversation_message") as log_fn:
        response = client.post(
            "/v1/log",
            json={"message": "hi", "role": "user", "session_id": "s1"},
        )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    log_fn.assert_called_once_with(
        settings,
        LogMessageInput(message="hi", role="user", session_id="s1"),
    )


def test_log_user_hook(client: TestClient, settings: MagicMock) -> None:
    with patch("memento_mcp.http_app.log_conversation_message") as log_fn:
        response = client.post(
            "/v1/hooks/log-user",
            json={"prompt": "question", "session_id": "claude-sess"},
        )
    assert response.status_code == 200
    log_fn.assert_called_once_with(
        settings,
        LogMessageInput(message="question", role="user", session_id="claude-sess"),
    )


def test_log_assistant_hook_cursor(client: TestClient, settings: MagicMock) -> None:
    with patch("memento_mcp.http_app.log_conversation_message") as log_fn:
        response = client.post(
            "/v1/hooks/log-assistant",
            json={"text": "answer", "conversation_id": "cursor-conv"},
        )
    assert response.status_code == 200
    log_fn.assert_called_once_with(
        settings,
        LogMessageInput(message="answer", role="assistant", session_id="cursor-conv"),
    )


def test_log_assistant_hook_claude(client: TestClient, settings: MagicMock) -> None:
    with patch("memento_mcp.http_app.log_conversation_message") as log_fn:
        response = client.post(
            "/v1/hooks/log-assistant",
            json={"last_assistant_message": "done", "session_id": "cc-sess"},
        )
    assert response.status_code == 200
    log_fn.assert_called_once_with(
        settings,
        LogMessageInput(message="done", role="assistant", session_id="cc-sess"),
    )


def test_auth_token_required(settings: MagicMock) -> None:
    app = create_app(settings, hook_token="secret")
    client = TestClient(app)
    response = client.post(
        "/v1/log",
        json={"message": "x", "role": "user", "session_id": "s"},
    )
    assert response.status_code == 401

    with patch("memento_mcp.http_app.log_conversation_message"):
        ok = client.post(
            "/v1/log",
            json={"message": "x", "role": "user", "session_id": "s"},
            headers={"Authorization": "Bearer secret"},
        )
    assert ok.status_code == 200
