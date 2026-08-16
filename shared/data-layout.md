# Shared: Providers and What Remains Under `.prioris/`

Referenced by `discuss`, `quick-read`, `quiz-me`, `reading-log`, and `manage-notes`. See `scope.md` for the plugin-wide scope and tool constraint, `mcp-contracts.md` for the MCP tool signatures (including `#notes`), `notes-model.md` for the tag scheme, and `local-file-handling.md` for the `@file` convention specific to the `localfile` provider.

## Providers

The companion MCP server (`prioris-mcp`, published at https://pypi.org/project/prioris-mcp/) exposes three sources, each with its own tool family — there is no source-generic search or fetch tool:

- **`arxiv`** — preprints (CS, physics, math, stats, q-bio, etc.). Full text available as `pdf` or `html`. Searchable.
- **`europepmc`** — published biomedical/life-science literature. Full text, when available at all, is JATS `xml` only — no format choice. Searchable.
- **`localfile`** — a PDF the user already has on disk, referenced directly (typically via the `@file` convention) rather than found through search. No search, metadata, or identifier-resolution capability exists for this source — see `local-file-handling.md`.

For a paper the user names by topic, title, or identifier, once expanding past local matches, `discuss`/`quick-read`/`quiz-me` ask via `AskUserQuestion` which of `arxiv`/`europepmc`/both/OpenAlex semantic search (`research_discovery`) to use — see `discuss`'s Search step (`quick-read`/`quiz-me` follow it by reference). OpenAlex isn't a fetchable "provider" like the other three: a hit either resolves to a known `arxiv`/`europepmc` identifier, or comes back as a link/DOI the user is pointed at rather than something this plugin fetches automatically. If the user hands you a bare DOI, or an identifier string whose provider isn't clear, call `research_resolve_identifier` first rather than guessing. If the user instead hands you a URL, `research_resolve_identifier` will not accept it directly — extract the canonical identifier yourself first (see `url-handling.md`). If the user hands you a local file directly, skip all of the above — go straight to `local-file-handling.md`.

## What remains under `.prioris/`

Per [anirbanbasu/prioris#1](https://github.com/anirbanbasu/prioris/issues/1), `.prioris/` is no longer a durable store for paper content or notes — both live server-side now (`prioris-mcp`'s `StorageBackend` and `NotesBackend`, see `mcp-contracts.md`). Three things legitimately remain:

- **Ephemeral scratch** — as already used by the chunked local-file upload flow (`local-file-handling.md`); genuinely temporary, never a record of anything, safe to ignore or delete at any time.
- **`.prioris/.metadata-cache/<provider>/<identifier>.json`** — gitignored, freely regenerable via `shared/scripts/metadata_cache.py`. Holds only `{title, authors, year}` for display convenience (e.g. `reading-log` showing a title next to a note without an extra `fetch_metadata` round trip this session). Never authoritative for anything; costs nothing to lose. `<identifier>` has `:` replaced with `_` for the filename only.
- **`.prioris/.review/schedule.json`** — versioned, **not** gitignored. `quiz-me`'s spaced-repetition state (`times_asked`, `last_result`, `level`, `last_asked_at`), keyed by question note id, managed via `shared/scripts/review_schedule.py`. This is real progress state with no server-side equivalent — see `notes-model.md`'s "Why review scheduling isn't in `NotesBackend`'s `metadata`".

Nothing else under `.prioris/` is read or written by any skill in this plugin. There is no client-side cache to check, reuse, or force-refetch for paper content any more: every `Fetch` step goes straight to the MCP server (via `document-reader`, see `discuss`'s workflow), whose own `StorageBackend` already avoids redundant fetch/parse work, and whose arXiv resolution always pins an unversioned id to its current latest version — a revised paper is picked up automatically on the next fetch, with nothing to force client-side.
