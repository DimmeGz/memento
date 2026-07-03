#!/usr/bin/env bash
# Shared helpers for Memento Cursor hooks.
set -euo pipefail

MEMENTO_BIN="${MEMENTO_VENV:+$MEMENTO_VENV/bin/memento}"
MEMENTO_BIN="${MEMENTO_BIN:-memento}"

memento_log() {
  local role="$1"
  local session_id="$2"
  local message="$3"
  if [[ -n "${MEMENTO_HTTP_URL:-}" ]]; then
    curl -sfS -X POST "${MEMENTO_HTTP_URL%/}/v1/log" \
      -H "Content-Type: application/json" \
      ${MEMENTO_HOOK_TOKEN:+-H "Authorization: Bearer ${MEMENTO_HOOK_TOKEN}"} \
      -d "$(jq -nc --arg m "$message" --arg r "$role" --arg s "$session_id" \
        '{message:$m, role:$r, session_id:$s}')" >/dev/null
  else
    "$MEMENTO_BIN" log --role "$role" --session-id "$session_id" --message "$message"
  fi
}

should_skip_user_prompt() {
  local prompt="$1"
  if [[ -z "$prompt" ]]; then
    return 0
  fi
  if [[ "$prompt" =~ ^/[[:alnum:]_-]+ ]]; then
    return 0
  fi
  if [[ "$prompt" =~ [Зз]алогуй[[:space:]]+діалог ]]; then
    return 0
  fi
  if [[ "$prompt" =~ [Ll]og[[:space:]]+(the[[:space:]]+)?(dialog|conversation) ]]; then
    return 0
  fi
  return 1
}
