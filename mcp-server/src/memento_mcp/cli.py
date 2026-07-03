"""CLI for deterministic Memento operations (log, core-context, HTTP serve)."""

from __future__ import annotations

import argparse
import json
import sys

from memento_mcp.config import get_settings
from memento_mcp.http_app import create_app, resolve_hook_token, resolve_http_host, resolve_http_port
from memento_mcp.services.context import get_core_context_text
from memento_mcp.services.logging import log_conversation_message
from memento_mcp.validation import ValidationError, validate_log_message


def _die(message: str, *, code: int = 1) -> None:
    sys.stderr.write(f"{message}\n")
    raise SystemExit(code)


def _cmd_log(args: argparse.Namespace) -> None:
    try:
        data = validate_log_message(
            message=args.message,
            role=args.role,
            session_id=args.session_id,
        )
    except ValidationError as exc:
        _die(str(exc), code=1)

    settings = get_settings()
    log_conversation_message(settings, data)


def _cmd_core_context(args: argparse.Namespace) -> None:
    settings = get_settings()
    text = get_core_context_text(settings)
    if args.json:
        sys.stdout.write(json.dumps({"additional_context": text}, ensure_ascii=False))
        sys.stdout.write("\n")
    else:
        sys.stdout.write(text)
        if text and not text.endswith("\n"):
            sys.stdout.write("\n")


def _cmd_serve(args: argparse.Namespace) -> None:
    try:
        import uvicorn
    except ImportError:
        _die(
            'HTTP serve requires optional dependencies. Install with: pip install "memento-mcp[http]"',
            code=1,
        )

    settings = get_settings()
    hook_token = resolve_hook_token()
    host = args.host or resolve_http_host()
    port = args.port if args.port is not None else resolve_http_port()
    app = create_app(settings, hook_token=hook_token)
    uvicorn.run(app, host=host, port=port, log_level="info")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="memento", description="Memento deterministic CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    log_parser = sub.add_parser("log", help="Log a conversation message")
    log_parser.add_argument("--role", required=True, choices=["user", "assistant"])
    log_parser.add_argument("--session-id", required=True)
    log_parser.add_argument("--message", required=True)
    log_parser.set_defaults(func=_cmd_log)

    ctx_parser = sub.add_parser("core-context", help="Print core context text")
    ctx_parser.add_argument("--json", action="store_true", help='Output {"additional_context":"..."}')
    ctx_parser.set_defaults(func=_cmd_core_context)

    serve_parser = sub.add_parser("serve", help="Start HTTP webhook server")
    serve_parser.add_argument("--host", default=None)
    serve_parser.add_argument("--port", type=int, default=None)
    serve_parser.set_defaults(func=_cmd_serve)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
