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
