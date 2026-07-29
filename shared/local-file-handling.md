# Shared: The `@file` Convention and the Local Filesystem Source

Referenced by `discuss`, `quick-read`, and `quiz-me`. See `data-layout.md` for where a fetched local file ends up cached and its `source_path` frontmatter field, and `mcp-contracts.md` for the two tool signatures (`research_localfile_fetch_full_text`, `research_localfile_parse_full_text`) this doc explains how to drive.

## When this applies

The user (or `$ARGUMENTS`) names a file directly — most often via the host agent's `@file` attachment convention, but also a plain path typed inline — rather than a topic, title, or provider identifier. That's a request for the `localfile` provider. There is nothing to search: skip straight to Fetch, below, treating the given path as already-resolved identity.

Only `discuss` and `quick-read` call the tools below directly. `quiz-me` does not — it only ever matches a `@file` against an already-cached `source_path` (see `data-layout.md`); if nothing matches, it tells the user to run `discuss` or `quick-read` on that file first rather than fetching it itself.

## Path handling

`research_localfile_fetch_full_text` takes `path` relative to a root directory the server operator configures (`PRIORIS_MCP_LOCAL_FILE_ROOT`) and rejects an absolute path outright. The host agent's `@file` convention, by contrast, typically hands you a path already resolved against the current working directory of this session. In the common single-machine setup, `prioris-mcp` is launched from that same project directory, so its root defaults to that same cwd — assume this by default: convert whatever path you were given into one relative to the current working directory, and pass that.

If the call still fails — `invalid_request` ("path escapes the configured root" or similar) or `not_found` — don't keep guessing at variations. Say plainly that the path doesn't resolve under wherever the server's root is configured, and ask the user to either confirm that root or re-supply the path relative to it. This is a configuration mismatch between client and server, not something fixable by trying nearby paths.

## Always fetch fresh — never reuse a stale id

Unlike `arxiv`/`europepmc`, where checking `.prioris/papers/<provider>/<identifier>.md` first can skip the MCP call entirely, a local file has no identifier until you ask: `research_localfile_fetch_full_text` re-reads and re-hashes the file's current bytes on every call, by design, because the file can change on disk between calls without notice. Always call it fresh for a named `@file`, even if a file at that same path was fetched earlier in this session. The `id` it returns is the caller-facing identifier (opaque, unrelated to the path) — only *after* getting that back do you know whether `.prioris/papers/localfile/<id>.md` already exists and can be reused as-is, skipping the parse step.

Only a PDF is accepted, verified by sniffing the file's own leading bytes rather than trusting a `.pdf` extension — a non-PDF file fails `invalid_request` regardless of its name.

## Fetch sequence

1. Call `research_localfile_fetch_full_text(path)` with the path resolved per "Path handling" above.
2. Using the returned `id`, check whether `.prioris/papers/localfile/<id>.md` already exists. If so, reuse its cached markdown — no need to parse again.
3. Otherwise call `research_localfile_parse_full_text(id)`, looping on `has_more` exactly as for the other providers (see `mcp-contracts.md#paging-through-full-text`), then write the concatenated markdown to `.prioris/papers/localfile/<id>.md` with frontmatter per `data-layout.md` — including `source_path` set to the path you were given, so `quiz-me` and `reading-log` can later recognize this same file by path rather than by the opaque `id`.
4. Proceed with Select/Discuss/Summarize/Record exactly as for `arxiv`/`europepmc`, with `provider: localfile` and `identifier: <id>`.
