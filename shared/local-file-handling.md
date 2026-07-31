# Shared: The `@file` Convention and the Local Filesystem Source

Referenced by `discuss`, `quick-read`, and `quiz-me`. See `data-layout.md` for where a fetched local file ends up cached and its `source_path` frontmatter field, and `mcp-contracts.md` for the two tool signatures (`research_localfile_fetch_full_text`, `research_localfile_parse_full_text`) this doc explains how to drive.

## When this applies

The user (or `$ARGUMENTS`) names a file directly — most often via the host agent's `@file` attachment convention, but also a plain path typed inline — rather than a topic, title, or provider identifier. That's a request for the `localfile` provider. There is nothing to search: skip straight to Fetch, below, treating the given path as already-resolved identity.

Only `discuss` and `quick-read` call the tools below directly. `quiz-me` does not — it only ever matches a `@file` against an already-cached `source_path` (see `data-layout.md`); if nothing matches, it tells the user to run `discuss` or `quick-read` on that file first rather than fetching it itself.

## Reading and encoding the file

`research_localfile_fetch_full_text` takes the file's own bytes, base64-encoded (`content_base64`) plus an optional `filename` hint — not a path. There is no server-side filesystem for a path to resolve against: `prioris-mcp` may be running on a different machine, in a different container, or behind streamable-http/http, none of which share a filesystem with this session. So the read happens on *your* side, not the server's:

1. Resolve whatever the host agent's `@file` convention (or a plainly typed path) handed you into a concrete local path on this session's filesystem.
2. Base64-encode that file's raw bytes using `shared/scripts/encode_local_pdf.py` (see `scripts/README.md` for how to invoke it) rather than shell `base64` — its flags aren't portable (`-i` on macOS/BSD vs `-w0` on GNU coreutils), which is exactly the kind of platform-guessing this script exists to avoid. It prints the base64 string on stdout — pass it directly as `content_base64`. It also sniffs the `%PDF-` header locally before printing anything, so a non-PDF or missing file fails fast with a plain message on stderr, before you've spent an MCP call on it.
3. Pass the original filename (basename is enough) as `filename` — it's stored purely for reference/display, never used to derive identity, and never resolved against anything server-side.

If the script reports the file doesn't exist or isn't a PDF, say so plainly and ask the user to confirm the path — that's a problem on this side, not something the MCP call can diagnose for you (it never sees a path at all). If the MCP call itself then fails `invalid_request` (not valid base64 — shouldn't happen via the script, but possible if you constructed `content_base64` some other way) or `file_too_large`, report that plainly too rather than retrying with variations — those are properties of the file's actual content, not something fixable by re-encoding it differently.

## Always fetch fresh — never reuse a stale id

Unlike `arxiv`/`europepmc`, where checking `.prioris/papers/<provider>/<identifier>.md` first can skip the MCP call entirely, a local file has no identifier until you ask: identity is a hash of the content you send, and `research_localfile_fetch_full_text` re-decodes and re-hashes whatever bytes you just read on every call, by design, because the file can change on disk between calls without notice. Always re-read the file and call it fresh for a named `@file`, even if a file at that same path was fetched earlier in this session. The `id` it returns is the caller-facing identifier (opaque, unrelated to `filename` or the path) — only *after* getting that back do you know whether `.prioris/papers/localfile/<id>.md` already exists and can be reused as-is, skipping the parse step.

Only a PDF is accepted, verified by sniffing the decoded bytes' own leading bytes rather than trusting a `.pdf`-looking filename — non-PDF content fails `invalid_request` regardless of what `filename` says.

## Fetch sequence

1. Read the file at the resolved path and base64-encode it per "Reading and encoding the file" above, then call `research_localfile_fetch_full_text(content_base64, filename=<basename>)`.
2. Using the returned `id`, check whether `.prioris/papers/localfile/<id>.md` already exists. If so, reuse its cached markdown — no need to parse again.
3. Otherwise call `research_localfile_parse_full_text(id)`, looping on `has_more` exactly as for the other providers (see `mcp-contracts.md#paging-through-full-text`), then write the concatenated markdown to `.prioris/papers/localfile/<id>.md` with frontmatter per `data-layout.md` — including `source_path` set to the local path you resolved the file from (this is bookkeeping on this side only; it's never sent to the server), so `quiz-me` and `reading-log` can later recognize this same file by path rather than by the opaque `id`.
4. Proceed with Select/Discuss/Summarize/Record exactly as for `arxiv`/`europepmc`, with `provider: localfile` and `identifier: <id>`.
