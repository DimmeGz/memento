# Claude Code integration

Merge one of the hook fragments into `.claude/settings.json` under the top-level `"hooks"` key.

## Variant A — MCP tool (recommended)

File: [`hooks.fragment.json`](hooks.fragment.json)

Requires `memento-memory` MCP server in your Claude Code config with `MEMENTO_ENV_ROOT` and `MEMENTO_WORKSPACE_ROOT`.

| Event | Action | Source field |
|-------|--------|--------------|
| `SessionStart` (matcher `startup`) | `get_core_context` → `additionalContext` | — |
| `UserPromptSubmit` | `log_message` role=user | `${prompt}` |
| `Stop` | `log_message` role=assistant | `${last_assistant_message}` |

`session_id` comes from Claude Code natively — do not generate UUIDs in agent rules.

## Variant B — HTTP

File: [`hooks.http.fragment.json`](hooks.http.fragment.json)

1. Install HTTP extra: `pip install "memento-mcp[http]"`.
2. Run `memento serve` with env vars set.
3. Merge the HTTP fragment. Update the `SessionStart` command path to the absolute path of [`memento-session-start.sh`](memento-session-start.sh).

**Limitation:** `SessionStart` supports only `command` and `mcp_tool`, not `http`. Core context injection uses the shell script that `curl`s `GET /v1/core-context` and returns `additionalContext`.

| Event | Type | Endpoint |
|-------|------|----------|
| `SessionStart` | `command` | script → `GET /v1/core-context` |
| `UserPromptSubmit` | `http` | `POST /v1/hooks/log-user` |
| `Stop` | `http` | `POST /v1/hooks/log-assistant` |

Set `MEMENTO_HTTP_URL` and optional `MEMENTO_HOOK_TOKEN` for the SessionStart script.

## Merge example

If your `.claude/settings.json` already has hooks, merge event arrays — do not overwrite unrelated hooks.

```json
{
  "hooks": {
    "SessionStart": [ ...existing..., ...from fragment... ],
    "UserPromptSubmit": [ ...from fragment... ],
    "Stop": [ ...from fragment... ]
  }
}
```

## Notes

- `UserPromptSubmit` blocks prompt processing until the hook completes (default timeout 30s). Keep logging fast.
- `Stop` fires once per turn with the full `last_assistant_message` — preferred over `MessageDisplay` for logging.
