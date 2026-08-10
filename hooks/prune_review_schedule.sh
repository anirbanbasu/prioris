#!/usr/bin/env bash
# Prunes .prioris/.review/schedule.json's entry for a note deleted via
# research_notes_delete, if one exists. Best-effort and silent: a quiz
# question is only one kind of note this plugin creates, so most deletes
# have nothing to prune, and this must never block or fail the delete
# itself over that.
set -euo pipefail

input="$(cat)"
note_id="$(echo "$input" | jq -r '.tool_input.note_id // empty' 2>/dev/null || true)"

if [ -z "$note_id" ]; then
  exit 0
fi

uv run --project "${CLAUDE_PLUGIN_ROOT}" python "${CLAUDE_PLUGIN_ROOT}/shared/scripts/review_schedule.py" prune "$note_id" \
  >/dev/null 2>&1 || true

exit 0
