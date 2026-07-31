# Shared: Providers and Data Layout

Referenced by `discuss`, `quick-read`, `quiz-me`, and `reading-log`. See `scope.md` for the plugin-wide scope and tool constraint, `mcp-contracts.md` for the MCP tool signatures, and `local-file-handling.md` for the `@file` convention specific to the `localfile` provider.

## Providers

The companion MCP server (`prioris-mcp`, published at https://pypi.org/project/prioris-mcp/) exposes three sources, each with its own tool family — there is no source-generic search or fetch tool:

- **`arxiv`** — preprints (CS, physics, math, stats, q-bio, etc.). Full text available as `pdf` or `html`. Searchable.
- **`europepmc`** — published biomedical/life-science literature. Full text, when available at all, is JATS `xml` only — no format choice. Searchable.
- **`localfile`** — a PDF the user already has on disk, referenced directly (typically via the `@file` convention) rather than found through search. No search, metadata, or identifier-resolution capability exists for this source — see `local-file-handling.md`.

For a paper the user names by topic, title, or identifier, pick the provider from the subject matter (biomedical → `europepmc`, everything else → `arxiv`). If genuinely ambiguous, search both and merge, labeling each result with its provider. If the user hands you a bare DOI, or an identifier string whose provider isn't clear, call `research_resolve_identifier` first rather than guessing. If the user instead hands you a URL, `research_resolve_identifier` will not accept it directly — extract the canonical identifier yourself first (see `url-handling.md`) and proceed with the provider-specific tools. If instead the user hands you a local file directly, skip all of the above — go straight to `local-file-handling.md`.

## Data layout

All state lives under `.prioris/` in the current working directory, as plain markdown with YAML frontmatter — human-readable, git-diffable, no database:

- `.prioris/papers/<provider>/<identifier>.md` — cached, cleaned paper content (parsed markdown from the MCP server). Regenerable; safe to `.gitignore`.
- `.prioris/discussions/<provider>/<identifier>.md` — notes and synthesis from past discussions and quizzes on this paper. Source of truth; should be versioned.

`<identifier>` is the provider's canonical id used in the MCP calls (arXiv id, version-suffixed e.g. `2401.12345v2`; Europe PMC id in `{source}:{id}` form, filesystem-sanitized by replacing `:` with `_` if needed for the filename only — the frontmatter `identifier` field keeps the exact canonical form). For `localfile`, there is no canonical id derived from the content itself the way there is for the other two sources — `<identifier>` is instead the caller-facing id `research_localfile_fetch_full_text` mints and returns (e.g. `20260729-0813-a1b2`); treat it as opaque.

Frontmatter schema for all three:

```yaml
---
provider: arxiv | europepmc | localfile
identifier: <canonical id as returned by the MCP server>
title: ...
authors: [...]
source_url: ...
resource_uri: research://{provider}/{identifier}/{format}/markdown
fetched_at: <ISO 8601>
read_at: <ISO 8601, omitted if not yet discussed>
tags: [...]
---
```

`localfile` entries add one more field: `source_path: <the path you were given, e.g. via @file>`. Nothing else consumes it at fetch time, but `quiz-me` and `reading-log` both use it to recognize "this same file" again without an opaque id to search on — see `local-file-handling.md` and `reading-log`'s `ids` filter. `title`/`authors`/`source_url` won't be available from a provider lookup the way they are for `arxiv`/`europepmc`; fill them in from the PDF's own content (e.g. a title page) if evident, or leave them blank rather than guessing.

A `.prioris/discussions/<provider>/<identifier>.md` file's body is a sequence of `## `-level sections, one per skill that's written to it: `discuss` writes `## Discussion`, `quick-read` writes `## Quick read`, `quiz-me` writes `## Quiz notes`. All three read/update this same file rather than each keeping a separate one, via `scripts/update_notes_section.py` (see `scripts/README.md`), which replaces exactly the named section in place and leaves the others untouched — so a paper discussed, quick-read, and quizzed all end up as sections of one file.

## Forcing a refetch

By default, every skill that reads `.prioris/papers/<provider>/<identifier>.md` treats a cache hit as final and reuses it as-is, never re-fetching, since a published `arxiv`/`europepmc` identifier is normally immutable. If the user explicitly asks to refetch, force a refresh, or get the latest version of a paper already cached this way — e.g. an arXiv preprint that's been revised to a new version, or a suspicion the cached copy is truncated or corrupted — bypass the `.prioris/papers/` cache check entirely for that call: run the provider's fetch/parse tools fresh exactly as if nothing were cached, then overwrite the existing `.prioris/papers/<provider>/<identifier>.md` with the new content and a fresh `fetched_at`.

This only applies to `arxiv`/`europepmc`. `localfile` already fetches fresh on every call regardless (see `local-file-handling.md`), so there's nothing to force there.

Only `discuss` and `quick-read` call the fetch tools directly. `quiz-me` never fetches on its own — a refetch request there defers to `discuss`'s forced Fetch step first, the same way an ordinary cache-miss fetch already does, before quizzing from the result.

A plain "redo"/"regenerate" request (e.g. `quick-read` regenerating its summary from already-cached text) is not the same as a refetch and should not bypass this cache — only an explicit ask for a refetch or the latest version should.
