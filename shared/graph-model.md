# Shared: Graph Model — Conventions for `prioris-mcp`'s Graph Backend

Referenced by `graph-backfill`, `graph-extract`, `manage-graph`, `concept-explore`, `agents/document-reader.md`, and `hooks/hooks.json`. See `mcp-contracts.md#graph` for the `research_graph_*` tool/resource contracts this doc assumes, and (in the pinned `prioris-mcp` checkout) `docs/requirement-specification/search/03-graph-search.md` for the full backend design this plugin builds on top of.

## Current scope: `document` and `note` pointers only

`Pointer.ref_type` supports `chunk`/`document`/`note` server-side, but this plugin does not currently create `chunk`-level pointers: no `prioris-mcp` tool or resource enumerates a document's chunk ids up front (`chunk_id` only ever surfaces incidentally inside a `research_search_fetched(mode="vector")` match, generated asynchronously by a separate indexing pipeline, not at fetch/parse time). Building `chunk —[exists-in]→ document` edges would require a chunk-enumeration capability that doesn't exist yet — deferred, not descoped permanently.

## `ref_id` convention for documents

A document `Pointer`'s `ref_id` is always `f"{provider}:{canonical_identifier}"` (e.g. `"arxiv:2401.12345"`), using the same canonical identifier `research_notes_create`/`research_notes_search` already carry — never the raw, provider-native identifier a user might type. Every component resolving a document to a graph node id (structural sync, `graph-extract`, `concept-explore`'s seed resolution, `rmotd`'s stub-promotion check) uses this exact format, so the same document always upserts onto the same `Pointer` node regardless of which component touches it first. A note `Pointer`'s `ref_id` is simply the note's own `id` — no transformation.

## Idempotency: `upsert_pointer` is safe to repeat, edges are not

`upsert_pointer` is unique on `(ref_type, ref_id)` and always safe to call again. `create_edge` is **not** deduplicated by the engine — there is no `(from, to, relation_type)` uniqueness; the graph is a true multigraph, and calling `create_edge` twice for "the same" relationship creates two edges. **Every call site that writes an edge must check for an existing one first** — `neighbors(node_id=<the "from" node>, relation_type=<R>, direction="out")`, paginated, looking for the intended `to_id` — before calling `create_edge`. `shared/scripts/graph_structural_sync.py`'s `link` subcommand implements this check for Pointer↔Pointer structural edges (`annotates`/`references`) and should be reused via `Bash` for those. It cannot resolve a `Concept` node id, so any edge with a Concept endpoint (every `about` edge, and any concept-to-concept edge `manage-graph` writes) must inline the same check instead — `research_graph_query(op="neighbors", node_id=<from_id>, relation_type=<R>, direction="out")`, paginated, checking for the intended `to_id` before calling `create_edge`. `skills/graph-extract/SKILL.md`'s Write step is the canonical spelling of the inline version.

## Fixed `relation_type` vocabulary

Unlike concepts (`find_concepts`/`research://graph/concepts`), the server has **no vocabulary-browsing aid for relation types** (an explicitly deferred follow-up per the backend's own ADR-00034) — vocabulary drift has to be prevented here, by convention, not by querying the server. Every skill/script in this plugin writing an edge uses one of these, verbatim:

- `annotates` — `note → document` (or `note → chunk`, once chunk pointers exist). Written only by `graph_structural_sync.py`.
- `references` — `document → document`, when one document's note text names another already-`Pointer`-linked document. Written only by `graph-extract` (requires reading the note's text — see its SKILL.md).
- `about` — `document → concept` or `note → concept`, the default relation `graph-extract` proposes between a fetched item and a concept it discusses. The user may override this per-edge during `graph-extract`'s approval step if a more specific relation_type fits better (e.g. `introduces`, `critiques`) — any override still gets added to this list the next time this doc is updated.

Adding a new `relation_type` is a `graph-model.md` edit, not a runtime decision a skill makes silently — if `graph-extract` or `manage-graph` proposes one not listed here, add it to this list in the same change.

## Concept find-or-create pattern

Mirrors `notes-model.md`'s find-or-create pattern for notes:

1. `research_graph_query(op="find_concepts", query=<candidate label>, limit=20)` — fuzzy (rapidfuzz) candidates against every existing concept's `label`+`aliases`.
2. If no candidate looks right, additionally browse `research://graph/concepts{?text,match,offset,limit}` (unfiltered/prefix/contains/suffix browse) — the fallback for synonym/cross-lingual duplicates fuzzy matching can't reach.
3. Present candidates (if any) plus a "new concept" option via `AskUserQuestion` — never silently pick one. The dedup judgment is always the user's, never automatic (per the backend's own design: `find_concepts` is a recall-oriented surfacer, not a duplicate-blocking gate).
4. **New concept**: `research_graph_write(op="create_concept", label=..., aliases=[...], description=...)`. **Alias onto existing**: `research_graph_write(op="update_concept", node_id=<existing>, aliases=[...existing.aliases, <new label>])` — never overwrite `label` itself when aliasing; the existing concept's canonical `label` stays put, the new name joins `aliases`.

## Approval gate

Every `research_graph_write` call in `graph-extract`, `manage-graph`, and `rmotd`'s stub-concept writes is preceded by an explicit `AskUserQuestion` confirmation — no exceptions, no confidence threshold that skips it. The graph is corpus-wide and shared across every project; a silent bad write skews graph-based exploration for everything downstream, not just the session that made it.

## `MetadataConflictError` handling

`upsert_pointer`, `update_concept`, and `update_edge` merge `metadata` per-key against whatever is already there and raise `MetadataConflictError` (surfaces as a `ToolError` whose message contains `metadata_conflict`) if a key exists on both sides with a different value. Never let this reach the user as a raw tool failure — catch it, name the conflicting key(s) and both values via `AskUserQuestion` (keep existing / use new / merge into a list, if the value is naturally list-like), then re-issue the write with the resolved value.

## Stub-concept convention (`rmotd`)

A candidate paper `rmotd` surfaces but hasn't fetched gets a `Concept` node (not a `Pointer` — nothing exists in `StorageBackend` yet), tagged `metadata.stub_identifier = "<provider>:<canonical_identifier>"` (same format as the document `ref_id` convention above, so the two are trivially comparable once the paper is actually fetched). There is no automatic check at fetch time — `agents/document-reader.md` has no graph-read tool access and only ever performs the structural `upsert` (see its own "Structural graph sync" section). A stub is discovered and promoted manually: the user (or a skill acting on their behalf) invokes `manage-graph`'s promote step directly once they know or suspect a stub exists for a paper they've just fetched; see that step for the title-based lookup-then-verify sequence.

`metadata.stub_identifier` is a **verification** key, not a lookup key — the graph backend's `find_concepts`/`research://graph/concepts` only match on `label`/`aliases`, so a stub is always found by its title first, then confirmed by comparing `metadata.stub_identifier`; see `manage-graph`'s promote step for the exact sequence.
