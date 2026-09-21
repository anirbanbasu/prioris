---
name: manage-graph
description: "Add, edit, remove, and merge Concept nodes and relations in prioris-mcp's graph backend by hand, and promote a stub Concept (created by rmotd for an unfetched candidate paper) to a real Pointer once it's fetched. Triggers: manage the graph, edit this concept, delete this concept, merge these two concepts, remove this relation, clean up the graph, promote this stub concept, fix a duplicate concept."
metadata:
  version: "0.1.0"
  status: active
  task_type: open-ended
---

# Manage Graph

See `../../shared/scope.md`, `../../shared/mcp-contracts.md#graph`, and `../../shared/graph-model.md` (approval gate, `MetadataConflictError` handling, and the stub-concept convention this skill's promote operation resolves) for shared context this skill assumes throughout.

## Scope

Manual/direct graph administration — the `manage-notes`/`manage-storage` counterpart for the graph. Never extracts concepts or relations from text (`graph-extract`'s job); this skill only edits/removes/merges what already exists, or promotes a known stub. `research_graph_write` carries `destructiveHint: True` (it bundles every delete op) — every operation below confirms the exact target and its blast radius before writing, never a generic "are you sure?".

## Workflow

1. **Find the target** — `find_concepts`/`research://graph/concepts` browse for a concept by name, or `get_node`/`neighbors` if the user already has a node id (e.g. from `concept-explore`). Show the current state (label/aliases/description/metadata for a concept; from/to/relation_type/weight for an edge) before offering any change.
2. **Add** — `create_concept`/`create_edge` directly, same find-or-create discipline as `graph-extract` step 3 if adding a concept (never blindly create a near-duplicate). Before any `create_edge`, check `research_graph_query(op="neighbors", node_id=<from_id>, relation_type=<relation_type>, direction="out")`, paginated, for an existing edge to the same `to_id` per `graph-model.md`'s idempotency rule; skip the `create_edge` call (report it as already present) if one exists.
3. **Edit** — `update_concept`/`update_edge` with only the changed fields; confirm the diff (old value → new value per field) before writing. Handle `metadata_conflict` per `graph-model.md`.
4. **Delete** — show the exact node/edge (and, for a node, how many incident edges `delete_node`'s cascade will also remove — `neighbors(node_id, direction="both")`, count the matches) before confirming. One `AskUserQuestion` confirmation naming the count, then `delete_node`/`delete_edge`.
5. **Merge concept A into B** — confirm both concepts (A being absorbed, B surviving) and that every one of A's edges will be recreated on B first. Then:
   1. `update_concept(B, aliases=[...B.aliases, A.label])` (skip if `A.label` is already in `B.aliases`).
   2. ```
      uv run --project <plugin root> python ../../shared/scripts/graph_edge_migrate.py migrate \
          --from-node-id <A> --to-node-id <B> --delete-old
      ```
   3. Report the migrated edge count and confirm A no longer exists.
6. **Promote a stub Concept to a Pointer** — triggered either by the user directly, or by `agents/document-reader.md` surfacing a `metadata.stub_identifier` match after a fetch (see `graph-model.md`). Confirm the stub concept and the real `Pointer` it's being promoted to, and how many edges will move. Then:
   1. `research_graph_write(op="upsert_pointer", ref_type="document", ref_id=<the now-fetched document's ref_id>)` to get the real `Pointer` node id (idempotent — `agents/document-reader.md`'s own fetch-time upsert has usually already created it).
   2. ```
      uv run --project <plugin root> python ../../shared/scripts/graph_edge_migrate.py migrate \
          --from-node-id <stub concept id> --to-node-id <pointer id> --delete-old
      ```
   3. Report the migrated edge count and confirm the stub no longer exists.

## Argument handling

If `$ARGUMENTS` names a concept, node id, or an explicit operation ("merge X into Y", "delete concept Z", "promote the stub for arxiv:..."), go straight to the matching step above. Otherwise ask what to manage.
