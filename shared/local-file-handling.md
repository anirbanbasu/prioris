# Shared: The `@file` Convention and the Local Filesystem Source

Referenced by `discuss`, `quick-read`, and `quiz-me`. See `data-layout.md` for providers and what little remains under `.prioris/`, and `mcp-contracts.md` for the tool signatures behind the upload (`research_localfile_begin_upload`, `research_localfile_upload_chunk`, `research_localfile_finalize_upload`) and `research_localfile_parse_full_text` — driven via `shared/scripts/pdf_chunk_upload_helper.py` and `../../agents/document-reader.md` rather than called directly.

## When this applies

The user (or `$ARGUMENTS`) names a file directly — most often via the host agent's `@file` attachment convention, but also a plain path typed inline — rather than a topic, title, or provider identifier. That's a request for the `localfile` provider. There is nothing to search: skip straight to Fetch, below, treating the given path as already-resolved identity.

All three skills that accept a local file (`discuss`, `quick-read`, `quiz-me`) follow the same sequence below — none of them call an MCP tool directly for a local file; the upload script handles the three-phase upload, and `document-reader` handles fetch/parse.

## Uploading the file

There is no server-side filesystem for a path to resolve against: `prioris-mcp` may be running on a different machine, in a different container, or behind streamable-http/http, none of which share a filesystem with this session. So the read happens on *your* side, not the server's, and the upload itself is driven end-to-end by `shared/scripts/pdf_chunk_upload_helper.py` (see `scripts/README.md` for how to invoke it) rather than by you calling the MCP tools directly:

1. Resolve whatever the host agent's `@file` convention (or a plainly typed path) handed you into a concrete local path on this session's filesystem.
2. Run `pdf_chunk_upload_helper.py <path> [--filename <basename>]`. It sniffs the `%PDF-` header locally before doing anything else, so a non-PDF or missing file fails fast on stderr before any MCP call is made. If it passes that check, the script itself becomes an MCP client and drives `research_localfile_begin_upload` → `research_localfile_upload_chunk` (looped, sized against the `max_chunk_bytes` the server just told it, in strict sequential order) → `research_localfile_finalize_upload` — entirely inside the script's own process. Every chunk's base64 stays there; it never becomes part of this conversation, regardless of file size.
3. On success, the script prints exactly one line of JSON to stdout — the same shape `research_localfile_fetch_full_text` returns (`id`, `location`, `format`, `size_bytes`, `served_from_storage`, `resource_uri`). Use that `id` exactly as described below.

Always let the script derive `filename` from the path's basename unless you have a specific reason to override it — it's stored purely for reference/display, never used to derive identity, and never resolved against anything server-side.

If the script reports the file doesn't exist or isn't a PDF, say so plainly and ask the user to confirm the path — that's a problem on this side, not something an MCP call could have diagnosed (it never sees a path at all). If it instead exits with an MCP-side error — recognizable from the script's error message, not a structured code (see `mcp-contracts.md`'s note on failures); informally these fall into `invalid_request`, `file_too_large`, or `not_found` for an expired session — report that plainly too rather than retrying with variations: those are properties of the file's actual content or of a slow upload outrunning the session TTL, not something fixable by re-running the same command.

## Always re-run the upload — never reuse a stale id

Unlike `arxiv`/`europepmc`, where an identifier is known before any fetch, a local file has no identifier until you ask: identity is a hash of the content, and the server re-decodes and re-hashes whatever bytes the script just sent it on every call, by design, because the file can change on disk between calls without notice. Always re-run the upload script for a named `@file`, even if a file at that same path was uploaded earlier in this session — there is nothing to check locally first. If the file's content hasn't changed, the server's own `StorageBackend` already has a persisted entry for the resulting `id`, so `document-reader`'s fetch/parse step reuses it exactly as it does for `arxiv`/`europepmc` — a re-upload never means a redundant parse.

Only a PDF is accepted, verified by sniffing the decoded bytes' own leading bytes rather than trusting a `.pdf`-looking filename — non-PDF content fails `invalid_request` regardless of what `filename` says (and the script itself sniffs this locally first, per "Uploading the file" above, so this case is normally caught before any MCP call).

## Fetch sequence

1. Run `pdf_chunk_upload_helper.py` on the resolved path per "Uploading the file" above and parse its one line of stdout JSON to get `id`.
2. Hand `../../agents/document-reader.md` the resolved `(provider: "localfile", identifier: id)` exactly as for `arxiv`/`europepmc` — see the calling skill's own Fetch/Generate step for what it asks `document-reader` to return. There is nothing to cache or check locally first: `document-reader` calls `research_localfile_parse_full_text(id)` directly, looping on `has_more` itself (see `mcp-contracts.md#paging-through-full-text`), and returns only the distilled result the calling step needs — never the full parsed text.
3. Proceed with the calling skill's next step (Select/Discuss/Record for `discuss`, per-section Generate for `quick-read`, question-bank Generate for `quiz-me`) exactly as for `arxiv`/`europepmc`, with `provider: localfile` and `identifier: id`.
