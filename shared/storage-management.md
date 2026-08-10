# Shared: Server-Side Storage Management

Referenced only by `manage-storage`. See `scope.md` for the plugin-wide tool constraint and `data-layout.md` for the *other* cache this doc explicitly is not about.

## Two caches, not one

`prioris-mcp` keeps two entirely separate server-side stores. `StorageBackend` is a content-addressed cache of raw fetched content and parsed Markdown, keyed by `(provider, identifier, format)`, on the server's own disk (`PRIORIS_MCP_STORAGE_DIR`) — purely so a repeat fetch or parse of the same thing doesn't redo the network call or the PDF/XML conversion. `NotesBackend` (`mcp-contracts.md#notes`) is a completely different store: user-authored notes, identity-addressed and mutable, the opposite of `StorageBackend`'s write-once fetched content. `manage-storage` only ever touches `StorageBackend`.

`research_list_fetched` and `research_delete_fetched`, below, see and touch only `StorageBackend`. Deleting a `StorageBackend` entry has no effect on any note — a later `parse_full_text`/fetch simply redoes the work, and nothing about the user's own notes is touched. Never imply to the user that clearing server storage also clears their notes; for notes administration (listing, tagging, deleting notes), point them at `manage-notes` instead — a separate skill, deliberately, since the two stores serve entirely different purposes and mixing their controls into one skill risks a user thinking a storage cleanup deleted their notes when it didn't.

## Tool contracts

- `research_list_fetched(provider?, format?) -> {entries: [{provider, identifier, format, artefact, fetched_at_or_parsed_at, size_bytes}, ...]}` — enumerates persisted entries, optionally restricted to one provider and/or one format. Never triggers a fetch; a plain read of the manifest. `identifier` here is already the externally-visible one (for `localfile`, the caller-facing id, not the internal content hash). `artefact` is `"document"` (the raw fetched content) or `"markdown"` (its parsed derivative); `fetched_at_or_parsed_at` is when the document was fetched, or, for a `markdown` artefact, when it was parsed.
- `research_delete_fetched(entries: [{provider, identifier, format, artefact}, ...]) -> {deleted: [...], not_found: [...]}` — removes one or more entries in a single call. `artefact` is **required** per entry: `"document"`, `"markdown"`, or `"all"`. Tolerant of entries no longer present: those come back in `not_found`, not as an error, so a stale or duplicate request doesn't need special-casing.

`format` is always the bare source format — `pdf`, `html`, `xml` — for both the raw fetched content and its parsed Markdown; the two are distinguished by the separate `artefact` field, not by a `-markdown` suffix on `format`. **A single fetched-and-parsed item is stored as at least two separate entries** sharing the same `(provider, identifier, format)` but differing in `artefact` (`document` + `markdown`), each independently listed and independently deletable. When the user asks to remove "this paper" from storage, that means gathering every entry matching its identifier across all of its formats *and* artefacts, not just the first one `research_list_fetched` happens to return — deleting only the `document` artefact (or only `markdown`) leaves the other behind, and a later `parse_full_text`/fetch will silently reuse whichever one survived. Deletion does not cascade between artefacts: removing `document` leaves `markdown` in place and vice versa; removing `markdown` or `all` also removes that document from the server's full-text search index.

## This is destructive

`research_delete_fetched` carries `destructiveHint: true` and cannot be undone from the server side — there is no separate confirmation step inside the tool itself. Always show the user the exact `(provider, identifier, format, artefact)` entries about to be removed and get explicit confirmation before calling it.
