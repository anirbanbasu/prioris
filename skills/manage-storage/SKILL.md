---
name: manage-storage
description: "Manage prioris-mcp's server-side storage — list what's been fetched and delete entries you no longer need. Triggers: manage storage, what's cached on the server, what's been fetched, clean up fetched papers, delete a cached PDF, free up disk space, prune old fetches, clear the prioris cache, remove this paper from storage. Distinct from your notes: this manages prioris-mcp's StorageBackend content cache, not the NotesBackend notes store — for notes, use manage-notes instead. Reach for this skill whenever the user asks about disk usage, stale downloads, or clearing prioris-mcp's cache specifically, even if they don't name research_list_fetched or research_delete_fetched directly. Out of scope: does NOT fetch, discuss, or summarize a paper — for that, use discuss or quick-read."
metadata:
  version: "0.1.0"
  status: active
  task_type: open-ended
---

# Manage Storage

See `../../shared/scope.md` for the plugin-wide tool constraint, `../../shared/storage-management.md` for the `research_list_fetched`/`research_delete_fetched` contracts and — importantly — the distinction between `StorageBackend` (this skill's target) and `NotesBackend` (the notes store, out of scope here), and `../../shared/data-layout.md` for the `.prioris/` layout this skill does not touch.

## Scope

This skill manages `prioris-mcp`'s `StorageBackend` — raw fetched PDFs/XML plus their parsed Markdown — not the `NotesBackend` notes store. It never fetches, parses, or discusses a paper itself; for that, use `discuss` or `quick-read`. For notes administration, use `manage-notes`. Read `../../shared/storage-management.md` before doing anything here — conflating the two stores is the single easiest way to alarm a user into thinking a storage cleanup deleted their notes, when it didn't.

## Workflow

1. **List** — call `research_list_fetched(provider, format)`, scoped to whatever the user asked about (all providers/formats if unspecified). Present entries grouped by `(provider, identifier)` rather than as a flat list — a single paper is normally stored as two entries sharing the same `format` but differing `artefact` (e.g. `pdf`/`document` + `pdf`/`markdown`), and showing them as one row listing both artefacts' size/date is easier to act on than showing the user two disconnected rows for "the same thing."
2. **Select** — work out exactly what the user wants removed: named identifier(s), an entire provider, an age/date cutoff ("clear anything older than 30 days" — convert relative phrasing to an absolute date using the current date), or everything. When an identifier is named, gather *every* entry matching it across all its formats and artefacts (per `storage-management.md`) — deleting a paper means deleting all of its stored `(format, artefact)` combinations (raw `document` and parsed `markdown`), not just whichever one happened to be listed first. If the user only wants to reclaim space from the raw fetched file while keeping the searchable parsed text (or vice versa), that's a valid narrower request — target just that `artefact` instead of `"all"`.
3. **Confirm** — list the exact `(provider, identifier, format, artefact)` entries about to be removed and get explicit confirmation before calling `research_delete_fetched`. This is destructive and the server has no undo; don't treat a vague "yeah clean some stuff up" as confirmation for a specific set — show the set first.
4. **Delete** — call `research_delete_fetched(entries=[...])`, each entry carrying the `provider`, `identifier`, `format`, and `artefact` (`"document"`, `"markdown"`, or `"all"`) determined in Select — `artefact` is required, the call fails without it. Report `deleted` and `not_found` plainly; `not_found` isn't an error, it just means that entry was already gone. Deleting `markdown` or `all` also removes that document from the server's full-text search index — mention this if the user has been using search over fetched content.

Deleting a `StorageBackend` entry never touches any note — if the user also wants to clean up notes for a paper whose storage was just cleared, point them at `manage-notes`' bulk-delete-by-paper flow as a distinct, separately-confirmed action, not something this skill does.

## Argument handling

If invoked with `$ARGUMENTS` naming identifiers, a provider, or an age/date phrase (e.g. "delete arxiv 2401.12345v2", "clear everything older than 2 weeks", "what's stored for europepmc"), parse it into the targets/filters above and proceed. A bare "manage storage" / "what's cached" with nothing further means: run List (step 1) and stop there, waiting for the user to say what to do next — never delete anything without an explicit, confirmed target.
