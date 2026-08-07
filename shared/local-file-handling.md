# Shared: The `@file` Convention and the Local Filesystem Source

Referenced by `discuss`, `quick-read`, and `quiz-me`. See `data-layout.md` for where a fetched local file ends up cached and its `source_path` frontmatter field, and `mcp-contracts.md` for the tool signatures behind the upload (`research_localfile_begin_upload`, `research_localfile_upload_chunk`, `research_localfile_finalize_upload`) and `research_localfile_parse_full_text` this doc explains how to drive — the upload trio via `shared/scripts/pdf_chunk_upload_helper.py` rather than directly.

## When this applies

The user (or `$ARGUMENTS`) names a file directly — most often via the host agent's `@file` attachment convention, but also a plain path typed inline — rather than a topic, title, or provider identifier. That's a request for the `localfile` provider. There is nothing to search: skip straight to Fetch, below, treating the given path as already-resolved identity.

Only `discuss` and `quick-read` call the tools below directly. `quiz-me` does not — it only ever matches a `@file` against an already-cached `source_path` (see `data-layout.md`); if nothing matches, it tells the user to run `discuss` or `quick-read` on that file first rather than fetching it itself.

## Uploading the file

There is no server-side filesystem for a path to resolve against: `prioris-mcp` may be running on a different machine, in a different container, or behind streamable-http/http, none of which share a filesystem with this session. So the read happens on *your* side, not the server's, and the upload itself is driven end-to-end by `shared/scripts/pdf_chunk_upload_helper.py` (see `scripts/README.md` for how to invoke it) rather than by you calling the MCP tools directly:

1. Resolve whatever the host agent's `@file` convention (or a plainly typed path) handed you into a concrete local path on this session's filesystem.
2. Run `pdf_chunk_upload_helper.py <path> [--filename <basename>]`. It sniffs the `%PDF-` header locally before doing anything else, so a non-PDF or missing file fails fast on stderr before any MCP call is made. If it passes that check, the script itself becomes an MCP client and drives `research_localfile_begin_upload` → `research_localfile_upload_chunk` (looped, sized against the `max_chunk_bytes` the server just told it, in strict sequential order) → `research_localfile_finalize_upload` — entirely inside the script's own process. Every chunk's base64 stays there; it never becomes part of this conversation, regardless of file size.
3. On success, the script prints exactly one line of JSON to stdout — the same shape `research_localfile_fetch_full_text` returns (`id`, `location`, `format`, `size_bytes`, `served_from_storage`, `resource_uri`). Use that `id` exactly as described below.

Always let the script derive `filename` from the path's basename unless you have a specific reason to override it — it's stored purely for reference/display, never used to derive identity, and never resolved against anything server-side.

If the script reports the file doesn't exist or isn't a PDF, say so plainly and ask the user to confirm the path — that's a problem on this side, not something an MCP call could have diagnosed (it never sees a path at all). If it instead exits with an MCP-side error — recognizable from the script's error message, not a structured code (see `mcp-contracts.md`'s note on failures); informally these fall into `invalid_request`, `file_too_large`, or `not_found` for an expired session — report that plainly too rather than retrying with variations: those are properties of the file's actual content or of a slow upload outrunning the session TTL, not something fixable by re-running the same command.

## Always fetch fresh — never reuse a stale id

Unlike `arxiv`/`europepmc`, where checking `.prioris/papers/<provider>/<identifier>.md` first can skip the MCP call entirely, a local file has no identifier until you ask: identity is a hash of the content, and the server re-decodes and re-hashes whatever bytes the script just sent it on every call, by design, because the file can change on disk between calls without notice. Always re-run the upload script for a named `@file`, even if a file at that same path was fetched earlier in this session. The `id` it returns is the caller-facing identifier (opaque, unrelated to `filename` or the path) — only *after* getting that back do you know whether `.prioris/papers/localfile/<id>.md` already exists and can be reused as-is, skipping the parse step.

Only a PDF is accepted, verified by sniffing the decoded bytes' own leading bytes rather than trusting a `.pdf`-looking filename — non-PDF content fails `invalid_request` regardless of what `filename` says (and the script itself sniffs this locally first, per "Uploading the file" above, so this case is normally caught before any MCP call).

## Fetch sequence

1. Run `pdf_chunk_upload_helper.py` on the resolved path per "Uploading the file" above and parse its one line of stdout JSON to get `id`.
2. Using that `id`, check whether `.prioris/papers/localfile/<id>.md` already exists. If so, reuse its cached markdown — no need to parse again.
3. Otherwise call `research_localfile_parse_full_text(id)`, looping on `has_more` exactly as for the other providers (see `mcp-contracts.md#paging-through-full-text`), then write the concatenated markdown to `.prioris/papers/localfile/<id>.md` with frontmatter per `data-layout.md` — including `source_path` set to the local path you resolved the file from (this is bookkeeping on this side only; it's never sent to the server), so `quiz-me` and `reading-log` can later recognize this same file by path rather than by the opaque `id`.
4. Proceed with Select/Discuss/Summarize/Record exactly as for `arxiv`/`europepmc`, with `provider: localfile` and `identifier: <id>`.
