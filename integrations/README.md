# Client integrations

Deterministic Memento operations (`log_message`, `get_core_context`) run via IDE hooks, CLI, or HTTP — not via agent rules. Semantic memory (`recall`, `remember`) stays in MCP tools.

## Session ID mapping

| Client | Native field | Used as `session_id` |
|--------|--------------|----------------------|
| Cursor | `conversation_id` | yes |
| Claude Code | `session_id` | yes |

Do not generate UUID `session_id` in agent rules when hooks are enabled.

## Required environment

All entry points need the same roots as MCP:

| Variable | Purpose |
|----------|---------|
| `MEMENTO_ENV_ROOT` | Memento checkout (loads `.env`) |
| `MEMENTO_WORKSPACE_ROOT` | Open project (reads `config.local.toml`) |

For CLI/hook scripts:

| Variable | Purpose |
|----------|---------|
| `MEMENTO_VENV` | Path to venv (e.g. `/path/to/memento/venv`) — scripts call `$MEMENTO_VENV/bin/memento` |
| `MEMENTO_HTTP_URL` | Optional. If set, hooks use HTTP instead of CLI (e.g. `http://127.0.0.1:8765`) |
| `MEMENTO_HOOK_TOKEN` | Optional Bearer token when HTTP auth is enabled |

## Cursor

1. Copy hook scripts into your project:

```bash
mkdir -p .cursor/hooks
cp integrations/cursor/hooks/*.sh .cursor/hooks/
chmod +x .cursor/hooks/*.sh
```

2. Merge [`integrations/cursor/hooks.json`](cursor/hooks.json) into `.cursor/hooks.json` (or copy if new).

3. Export env vars in your shell profile or Cursor MCP env:

```bash
export MEMENTO_ENV_ROOT="/absolute/path/to/memento"
export MEMENTO_WORKSPACE_ROOT="/absolute/path/to/your-project"
export MEMENTO_VENV="/absolute/path/to/memento/venv"
```

Hooks:

| Event | Script | Action |
|-------|--------|--------|
| `sessionStart` | `memento-session-start.sh` | Inject `additional_context` |
| `beforeSubmitPrompt` | `memento-log-user.sh` | Log user turn |
| `afterAgentResponse` | `memento-log-assistant.sh` | Log assistant turn |

User prompts are skipped when empty, slash commands (`/foo`), or meta-prompts like «залогуй діалог».

## Claude Code

See [`claude-code/README.md`](claude-code/README.md).

### Variant A — MCP tool (recommended)

Merge [`claude-code/hooks.fragment.json`](claude-code/hooks.fragment.json) into `.claude/settings.json` under `"hooks"`. Requires `memento-memory` MCP server connected.

### Variant B — HTTP

1. Start webhook: `memento serve` (requires `pip install "memento-mcp[http]"`).
2. Merge [`claude-code/hooks.http.fragment.json`](claude-code/hooks.http.fragment.json).
3. Update the `SessionStart` command path to `integrations/claude-code/memento-session-start.sh` (SessionStart does not support `type: http`).

## HTTP-only clients

Any client can POST to:

| Method | Path | Body |
|--------|------|------|
| `POST` | `/v1/log` | `{"message","role","session_id"}` |
| `GET` | `/v1/core-context` | — |
| `POST` | `/v1/hooks/log-user` | raw hook JSON with `prompt` + `session_id`/`conversation_id` |
| `POST` | `/v1/hooks/log-assistant` | raw hook JSON with `last_assistant_message`/`text` + `session_id`/`conversation_id` |

Start server:

```bash
export MEMENTO_ENV_ROOT="/path/to/memento"
export MEMENTO_WORKSPACE_ROOT="/path/to/project"
memento serve --host 127.0.0.1 --port 8765
```

See [mcp-server/README.md](../mcp-server/README.md) for auth (`MEMENTO_HOOK_TOKEN`).
