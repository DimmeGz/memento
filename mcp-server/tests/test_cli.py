from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from memento_mcp.cli import main
from memento_mcp.validation import LogMessageInput


@pytest.fixture
def mock_settings() -> MagicMock:
    return MagicMock()


def test_cli_log_success(mock_settings: MagicMock) -> None:
    with (
        patch("memento_mcp.cli.get_settings", return_value=mock_settings),
        patch("memento_mcp.cli.log_conversation_message") as log_fn,
    ):
        main(["log", "--role", "user", "--session-id", "sess-1", "--message", "hello"])
    log_fn.assert_called_once_with(
        mock_settings,
        LogMessageInput(message="hello", role="user", session_id="sess-1"),
    )


def test_cli_core_context_plain(mock_settings: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
    with (
        patch("memento_mcp.cli.get_settings", return_value=mock_settings),
        patch("memento_mcp.cli.get_core_context_text", return_value="ctx line"),
    ):
        main(["core-context"])
    assert capsys.readouterr().out == "ctx line\n"


def test_cli_core_context_json(mock_settings: MagicMock, capsys: pytest.CaptureFixture[str]) -> None:
    with (
        patch("memento_mcp.cli.get_settings", return_value=mock_settings),
        patch("memento_mcp.cli.get_core_context_text", return_value="ctx"),
    ):
        main(["core-context", "--json"])
    assert capsys.readouterr().out == '{"additional_context": "ctx"}\n'


def test_cli_log_validation_error(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["log", "--role", "user", "--session-id", "s", "--message", "   "])
    assert exc.value.code == 1
    assert "message must be non-empty" in capsys.readouterr().err
