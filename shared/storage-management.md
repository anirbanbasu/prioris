# Shared: Server-Side Storage Management

Referenced only by `manage-storage`. See `scope.md` for the plugin-wide tool constraint and `data-layout.md` for the *other* cache this doc explicitly is not about.

## Two caches, not one

`prioris-mcp` keeps its own content-addressed store of raw fetched content and parsed Markdown, keyed by `(provider, identifier, format)`, on the server's own disk (`PRIORIS_MCP_STORAGE_DIR`) — purely so a repeat fetch or parse of the same thing doesn't redo the network call or the PDF/XML conversion. This is a different cache from this plugin's own `.prioris/papers/` and `.prioris/discussions/` markdown files, which live on the client side and are what the rest of this plugin (`discuss`, `quick-read`, `quiz-me`, `reading-log`) actually reads and writes.

`research_list_fetched` and `research_delete_fetched`, below, see and touch only the server's storage. Deleting a server-side entry has no effect on `.prioris/` — the cached paper markdown and the user's discussion notes stay exactly as they were. Never imply to the user that clearing server storage also clears their local notes; if `manage-storage` offers to also clean up the matching `.prioris/` files, that is a distinct, separately-confirmed step (see `manage-storage`'s own SKILL.md), not something these two tools do for you.

## Tool contracts

- `research_list_fetched(provider?, format?) -> {entries: [{provider, identifier, format, fetched_at, size_bytes}, ...]}` — enumerates persisted entries, optionally restricted to one provider and/or one format. Never triggers a fetch; a plain read of the manifest. `identifier` here is already the externally-visible one (for `localfile`, the caller-facing id, not the internal content hash).
- `research_delete_fetched(entries: [{provider, identifier, format}, ...]) -> {deleted: [...], not_found: [...]}` — removes one or more entries in a single call. Tolerant of entries no longer present: those come back in `not_found`, not as an error, so a stale or duplicate request doesn't need special-casing.

Formats seen in practice: `pdf`, `html`, `xml` for raw fetched content, and `pdf-markdown`, `html-markdown`, `xml-markdown` for the parsed Markdown derived from each — not an enum enforced by the tool, just what the providers currently write. **A single fetched-and-parsed item is stored as at least two separate entries** (raw + markdown), each independently listed and independently deletable. When the user asks to remove "this paper" from storage, that means gathering every entry matching its identifier across all of its formats, not just the first one `research_list_fetched` happens to return — deleting only the raw entry (or only the markdown one) leaves the other behind, and a later `parse_full_text`/fetch will silently reuse whichever one survived.

## This is destructive

`research_delete_fetched` carries `destructiveHint: true` and cannot be undone from the server side — there is no separate confirmation step inside the tool itself. Always show the user the exact `(provider, identifier, format)` entries about to be removed and get explicit confirmation before calling it.
