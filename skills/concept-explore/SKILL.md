---
name: concept-explore
description: "Traverse and analyze prioris-mcp's graph backend — neighbors, paths, centrality, communities, reachability, link prediction — scoped to a project, a specific paper/concept, or (explicitly, rarely) the whole corpus. Triggers: explore the graph, what's central in my research, find a path between these concepts, what clusters exist, what does this concept connect to, suggest a missing connection, visualize the graph, export the graph."
metadata:
  version: "0.1.0"
  status: active
  task_type: open-ended
---

# Concept Explore

See `../../shared/scope.md`, `../../shared/mcp-contracts.md#graph`, and `../../shared/graph-model.md` for shared context. Covers the full `research_graph_analyze` algorithm surface, not just visualization — renamed from an earlier "concept-map" working title for that reason.

## Scope

Read-only in practice, with one narrow exception: seed resolution (Step 1) may call `upsert_pointer` as an idempotent, metadata-free node-id lookup for a document that has a note but was never synced to the graph — this can materialize a `Pointer` as a side effect, same as `graph-backfill` would eventually create for that item, just earlier and without a batch-run context. No `Concept`/edge write of any kind happens here: a `predict_links` suggestion is presented as something to formalize via `graph-extract`/`manage-graph`, never written here directly. Every `research_graph_analyze` op is seed-bounded (explicit `node_ids`, or a `from_id`/`to_id` pair for `paths`) — there is no whole-graph algorithm call in the underlying API, so Scope (step 1 below) always resolves to a concrete seed set or routes to the export script instead.

## Workflow

1. **Scope**, via `AskUserQuestion` (single-select), before anything else:
   - **This project** (default/recommended) — `research_notes_search(tags_all=[<project_tag>])` (compute `<project_tag>` once via `../../shared/scripts/project_tag.py`) for every `(provider, canonical_identifier)` in this project, then `research_graph_write(op="upsert_pointer", ref_type="document", ref_id="<provider>:<identifier>")` per item **with no `metadata` argument** (avoids triggering `metadata_conflict` on what is conceptually a read) to resolve each to a node id. That id list is the seed set.
   - **A specific paper or concept** — resolve via `find_concepts`/`research://graph/concepts` (concept) or the same `upsert_pointer`-as-lookup trick above (paper), then use that (possibly single-element) seed set.
   - **Whole graph** — flag this option's copy as expensive/rare ("scans everything ever fetched or noted, not just this project"). Routes to Step 5 (export/visualize) instead of trying to force every node id through `research_graph_analyze`'s seed-bounded ops, which would defeat the cost guard those ops are built around.
2. **Determine the ask, translate to an op**:
   - "what connects to X" → `research_graph_query(op="neighbors", node_id=X, ...)` or, for more than one hop, `op="subgraph", node_ids=[X], depth=N`.
   - "what's central here" → `research_graph_analyze(op="betweenness_centrality"` or `"pagerank", node_ids=<seeds>, depth=N)`.
   - "what clusters exist" → `op="communities", node_ids=<seeds>, depth=N`.
   - "path between X and Y" → `op="paths", from_id=X, to_id=Y, max_depth=N`.
   - "what does this eventually touch" → `op="reachable", node_ids=[X], max_depth=N` (only `node_ids[0]` is used — a single seed, never a list here).
   - "suggest a connection I might be missing" → `op="predict_links", node_ids=<seeds>, max_depth=N` — present each suggestion plainly as a suggestion, with a pointer to `graph-extract`/`manage-graph` to formalize any the user likes; never call `create_edge` from this skill.
3. **Pick `depth`/`max_depth` sensibly** — default 2 for a "this project" or "specific paper" scope (deep enough to reach concepts a couple of hops from a Pointer, shallow enough to stay fast); ask if the user wants deeper.
4. **Present results** grounded in what the op actually returned — node labels (concept `label`, or `ref_type:ref_id` for a pointer) and edge `relation_type`s, not bare ids.
5. **Whole-graph export/visualize** (from Step 1's "whole graph" branch, or a direct "export"/"visualize" ask):
   ```
   uv run --project <plugin root> python ../../shared/scripts/graph_export.py export --format cypher_json --out <path>
   uv run --project <plugin root> python ../../shared/scripts/graph_export.py visualize --out <path>.png
   ```
   Ask which the user wants (a raw export to open elsewhere, or a rendered PNG) if not already clear from their request.

## Argument handling

If `$ARGUMENTS` names a scope and/or an ask clearly enough to skip Step 1/2's questions (e.g. "what's central in my project's graph", "path between attention and retrieval-augmented generation"), do so. Otherwise ask Step 1 first.
