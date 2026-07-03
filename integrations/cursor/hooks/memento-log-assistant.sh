#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

payload="$(cat)"
text="$(echo "$payload" | jq -r '.text // .last_assistant_message // empty')"
session_id="$(echo "$payload" | jq -r '.conversation_id // .session_id // empty')"

if [[ -z "$text" || -z "$session_id" ]]; then
  exit 0
fi

if [[ -n "${MEMENTO_HTTP_URL:-}" ]]; then
  curl -sfS -X POST "${MEMENTO_HTTP_URL%/}/v1/hooks/log-assistant" \
    -H "Content-Type: application/json" \
    ${MEMENTO_HOOK_TOKEN:+-H "Authorization: Bearer ${MEMENTO_HOOK_TOKEN}"} \
    --data-binary "$payload" >/dev/null || true
else
  memento_log assistant "$session_id" "$text" || true
fi

exit 0
