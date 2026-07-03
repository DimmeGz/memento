#!/usr/bin/env bash
# SessionStart hook for Claude Code HTTP mode (SessionStart does not support type:http).
set -euo pipefail

MEMENTO_HTTP_URL="${MEMENTO_HTTP_URL:-http://127.0.0.1:8765}"
auth_header=()
if [[ -n "${MEMENTO_HOOK_TOKEN:-}" ]]; then
  auth_header=(-H "Authorization: Bearer ${MEMENTO_HOOK_TOKEN}")
fi

response="$(curl -sfS "${MEMENTO_HTTP_URL%/}/v1/core-context" "${auth_header[@]}" 2>/dev/null || echo '{"additional_context":""}')"
context="$(echo "$response" | jq -r '.additional_context // empty')"
jq -nc --arg ctx "$context" \
  '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $ctx}}'
