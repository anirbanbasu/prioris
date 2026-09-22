---
name: graph-extract
description: "Extract Concept nodes and relations from a document's or note's text into prioris-mcp's graph backend, with alias-aware duplicate avoidance and full human approval before every write. Triggers: extract concepts, build the concept graph, link this paper's ideas into the graph, find concepts in this paper, add this paper's concepts to the graph, what concepts does this note touch."
metadata:
  version: "0.1.0"
  status: active
  task_type: open-ended
---

# Graph Extract

See `../../shared/scope.md`, `../../shared/mcp-contracts.md#graph`, and `../../shared/graph-model.md` (the find-or-create pattern, relation_type vocabulary, approval gate, edge idempotency rule, and `MetadataConflictError` handling this skill follows throughout) — read `graph-model.md` in full before running this skill for the first time in a session.

## Scope

Extracts `Concept` nodes and relations from a document's full text (via `../../agents/document-reader.md`, the same mediator `discuss`/`quick-read` use — full text never loads into this conversation) or from a note's own text (read directly, since a note's text is already short and already in `NotesBackend`, not behind `document-reader`). Never writes a `research_graph_write` call without a preceding `AskUserQuestion` confirmation for that specific write. Never touches structural (`annotates`) edges — those are `graph_structural_sync.py`'s job, wired in automatically; this skill only ever writes `about`/`references` (or a user-approved override) relation types.

## Workflow

1. **Source** — resolve what to extract from: a document (`(provider, identifier[, format])`, resolved the same way `discuss`'s Select step does) or a note (a note id, or a search via `research_notes_search` to find one).
2. **Propose** — dispatch `document-reader` (document source) or read the note's `text` directly via `research_notes_read` (note source) for a proposed graph delta: candidate concepts (`label`, suggested `aliases`, `description`), candidate relations (which concept(s) relate to the source item and how), and, for a note source only, any sentence that appears to name another document already known to this plugin (candidate `references` edges — Pointer-to-Pointer, the one case requiring text understanding rather than pure structure).
3. **Find-or-create, per candidate concept** — follow `graph-model.md`'s find-or-create pattern exactly: `find_concepts` first, `research://graph/concepts` browse as fallback, `AskUserQuestion` to pick new/alias/skip — never auto-decide.
4. **Finalize, via multiple `AskUserQuestion` rounds** before anything is written:
   - Round 1: which candidates to keep (from step 3's outcome per concept).
   - Round 2: for each kept concept, its `label`/`aliases`/`description` and any extra `metadata` (provenance, confidence, source) — pre-filled with the extraction's proposal, editable.
   - Round 3: for each proposed edge, its `relation_type` (default `about`, or `references` for a Pointer-to-Pointer candidate from step 2 — offer `graph-model.md`'s committed baseline plus any entries already recorded in the untracked `.prioris/graph-relation-vocabulary.json` (read it if it exists; treat a missing file as an empty list) as options, plus "something else" if truly novel) and optional `weight`/`metadata`. If the user picks "something else", append the new relation_type to `.prioris/graph-relation-vocabulary.json` (create the file, containing a JSON array of strings, if it doesn't exist yet) — never edit `graph-model.md` itself for this; that file only changes via a separate, deliberate edit the user asks for.
5. **Write** — one `research_graph_write` call per approved concept/edge (`create_concept`/`update_concept` for the alias-onto-existing case, then `create_edge` for each relation using the resolved concept node id and the source item's `Pointer` node id, resolved via `research_graph_write(op="upsert_pointer", ref_type="document", ref_id="<provider>:<identifier>")` for a document source or `research_graph_write(op="upsert_pointer", ref_type="note", ref_id="<note id>")` for a note source, if not already known). Before each `create_edge`, follow `graph-model.md`'s idempotency rule: check `research_graph_query(op="neighbors", node_id=<from_id>, relation_type=<the resolved relation_type>, direction="out")`, paginated, for an existing edge to the same `to_id` — skip the `create_edge` call (report it as already present) if one exists. If any write raises `metadata_conflict`, follow `graph-model.md`'s conflict-handling steps (surface the key(s), ask keep/use-new/merge, re-issue) rather than letting the error reach the user raw.
6. **Report** — list what was actually written (node/edge ids from each `GraphWriteResult`), distinct from what was proposed but declined in step 4.

No automatic trigger exists for this skill — including for note-sourced extraction — because every write needs LLM judgment and human approval, neither of which a hook can provide. A note written long after its document's fetch links up identically to one written immediately after: the user (re-)invokes this skill on that note directly, whenever that happens to be.

## Argument handling

If `$ARGUMENTS` names a paper or note, use it as the Source (step 1). Otherwise ask.
