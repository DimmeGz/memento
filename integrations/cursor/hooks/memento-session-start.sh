#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

payload="$(cat)"
text="$("$MEMENTO_BIN" core-context --json 2>/dev/null || true)"
if [[ -z "$text" && -n "${MEMENTO_HTTP_URL:-}" ]]; then
  text="$(curl -sfS "${MEMENTO_HTTP_URL%/}/v1/core-context" \
    ${MEMENTO_HOOK_TOKEN:+-H "Authorization: Bearer ${MEMENTO_HOOK_TOKEN}"} 2>/dev/null || true)"
fi
if [[ -z "$text" ]]; then
  echo '{"additional_context":""}'
else
  echo "$text"
fi
