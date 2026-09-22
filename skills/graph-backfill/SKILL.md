---
name: graph-backfill
description: "On-demand structural graph backfill — links documents and notes that already exist but predate (or were otherwise missed by) automatic structural graph sync into prioris-mcp's graph backend as Pointer nodes and annotates edges. Triggers: graph backfill, backfill the graph, sync the graph, link my notes into the graph, rebuild structural graph, my old papers aren't in the graph."
metadata:
  version: "0.1.0"
  status: active
  task_type: mechanical
---

# Graph Backfill

See `../../shared/scope.md` for the plugin-wide tool constraint, `../../shared/mcp-contracts.md#graph` for the `research_graph_*`/`research_list_fetched` contracts, and `../../shared/graph-model.md` for the `ref_id` convention and relation_type vocabulary this skill writes.

## Scope

Purely mechanical — this skill never extracts concepts or relations from text, and never asks the user to approve a write (every write here is a deterministic `upsert_pointer`/idempotent `create_edge`, not an LLM judgment call). For concept/relation extraction, use `graph-extract`. This is the on-demand counterpart to the automatic hooks already wired into `agents/document-reader.md` (documents, at fetch time) and `../../hooks/hooks.json` (notes, at create/update time) — reach for it only for content that predates those hooks, or a session where a hook failed silently.

## Workflow

1. **Scope the backfill** — ask (or take from `$ARGUMENTS`) whether to backfill documents, notes, or both, and whether to scope to this project (via `project_tag.py`) or every fetched/noted item on the server.
2. **Documents** — call `research_list_fetched(provider=None, format=None)`, paginating until `has_more` is false, grouped by `(provider, identifier)` (same grouping `manage-storage`'s List step already uses). For each distinct `(provider, identifier)`:
   ```
   uv run --project <plugin root> python ../../shared/scripts/graph_structural_sync.py upsert \
       --ref-type document --ref-id "<provider>:<identifier>"
   ```
3. **Notes** — call `research_notes_search` with whatever scope was chosen in step 1 (project tag in `tags_all`, or no filter for "every fetched/noted item"), paginating until `has_more` is false. For each note:
   ```
   uv run --project <plugin root> python ../../shared/scripts/graph_structural_sync.py link \
       --from-ref-type note --from-ref-id "<note id>" \
       --to-ref-type document --to-ref-id "<provider>:<canonical identifier>" \
       --relation-type annotates
   ```
4. **Report** — summarize counts (documents linked, notes linked, edges newly created vs. already present per each call's `"created"` field) — never claim a write happened that the script's own output didn't confirm.

## Argument handling

If `$ARGUMENTS` says "documents only", "notes only", or names a specific paper/identifier, scope accordingly and skip the Step 1 question. Otherwise ask.
