# Shared: Providers and Data Layout

Referenced by `discuss`, `quick-read`, and `reading-log`. See `scope.md` for the plugin-wide scope and tool constraint, and `mcp-contracts.md` for the MCP tool signatures.

## Providers

The companion MCP server (`prioris-mcp`, published at https://pypi.org/project/prioris-mcp/) exposes two literature providers, each with its own tool family — there is no source-generic search or fetch tool:

- **`arxiv`** — preprints (CS, physics, math, stats, q-bio, etc.). Full text available as `pdf` or `html`.
- **`europepmc`** — published biomedical/life-science literature. Full text, when available at all, is JATS `xml` only — no format choice.

Pick the provider from the subject matter (biomedical → `europepmc`, everything else → `arxiv`). If genuinely ambiguous, search both and merge, labeling each result with its provider. If the user hands you a bare DOI, or an identifier string whose provider isn't clear, call `research_resolve_identifier` first rather than guessing. If the user instead hands you a URL, `research_resolve_identifier` will not accept it directly — extract the canonical identifier yourself first (see `url-handling.md`) and proceed with the provider-specific tools.

## Data layout

All state lives under `.prioris/` in the current working directory, as plain markdown with YAML frontmatter — human-readable, git-diffable, no database:

- `.prioris/papers/<provider>/<identifier>.md` — cached, cleaned paper content (parsed markdown from the MCP server). Regenerable; safe to `.gitignore`.
- `.prioris/discussions/<provider>/<identifier>.md` — notes and synthesis from past discussions and quizzes on this paper. Source of truth; should be versioned.

`<identifier>` is the provider's canonical id used in the MCP calls (arXiv id, version-suffixed e.g. `2401.12345v2`; Europe PMC id in `{source}:{id}` form, filesystem-sanitized by replacing `:` with `_` if needed for the filename only — the frontmatter `identifier` field keeps the exact canonical form).

Frontmatter schema for both:

```yaml
---
provider: arxiv | europepmc
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
