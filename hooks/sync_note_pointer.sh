#!/usr/bin/env bash
# Links a note into the graph as a Pointer, annotates-edged to its document's Pointer, whenever
# research_notes_create/research_notes_update succeeds. Best-effort and silent, same convention
# as prune_review_schedule.sh: this must never block or fail the note operation itself.
set -euo pipefail

input="$(cat)"
note_id="$(echo "$input" | jq -r '.tool_response.id // empty' 2>/dev/null || true)"
provider="$(echo "$input" | jq -r '.tool_response.provider // empty' 2>/dev/null || true)"
identifier="$(echo "$input" | jq -r '.tool_response.canonical_identifier // empty' 2>/dev/null || true)"

if [ -z "$note_id" ] || [ -z "$provider" ] || [ -z "$identifier" ]; then
  exit 0
fi

uv run --project "${CLAUDE_PLUGIN_ROOT}" python "${CLAUDE_PLUGIN_ROOT}/shared/scripts/graph_structural_sync.py" link \
  --from-ref-type note --from-ref-id "$note_id" \
  --to-ref-type document --to-ref-id "${provider}:${identifier}" \
  --relation-type annotates \
  >/dev/null 2>&1 || true

exit 0
