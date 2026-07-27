# Shared: Scope, Data Layout, and Core MCP Contracts

Referenced by every skill in this plugin (`../skills/discuss`, `../skills/quiz-me`, `../skills/rmotd`). Keep skill-specific behavior in each SKILL.md and only the shared parts here.

## Scope (applies to every skill in this plugin)

This plugin finds, reads, and discusses prior art — academic papers today, other sources later — one item at a time. No skill in this plugin drafts, outlines, or writes any part of a manuscript. If asked to write or draft paper content, decline and redirect toward discussion instead.

## Providers

The companion MCP server (`prioris-mcp`, published at https://pypi.org/project/prioris-mcp/) exposes two literature providers, each with its own tool family — there is no source-generic search or fetch tool:

- **`arxiv`** — preprints (CS, physics, math, stats, q-bio, etc.). Full text available as `pdf` or `html`.
- **`europepmc`** — published biomedical/life-science literature. Full text, when available at all, is JATS `xml` only — no format choice.

Pick the provider from the subject matter (biomedical → `europepmc`, everything else → `arxiv`). If genuinely ambiguous, search both and merge, labeling each result with its provider. If the user hands you a bare DOI, or an identifier string whose provider isn't clear, call `research_resolve_identifier` first rather than guessing. If the user instead hands you a URL, `research_resolve_identifier` will not accept it directly — extract the canonical identifier yourself first (see "Argument handling" in `discuss`'s SKILL.md) and proceed with the provider-specific tools.

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

## Core MCP dependency

Every skill here assumes a companion MCP server (the `prioris-mcp` server, https://pypi.org/project/prioris-mcp/) exposing at minimum:

**arXiv**
- `research_arxiv_search(query, max_results=10, start=0, sort_by?, sort_order?) -> results[]` (each: `arxiv_id, title, abstract, authors[{name, affiliation}], categories, primary_category, published, updated, pdf_url, doi?, journal_ref?, comment?`)
- `research_arxiv_fetch_metadata(arxiv_ids: []) -> {results: [...], not_found: [...]}`
- `research_arxiv_fetch_full_text(arxiv_id, format: "pdf"|"html") -> {location, format, size_bytes, served_from_storage, resource_uri}`
- `research_arxiv_parse_full_text(arxiv_id, format) -> {markdown, resource_uri}` — fails `not_found` if the id hasn't been fetched first
- `research_arxiv_list_top_n(category, n) -> results[]` — most recent items in an arXiv taxonomy code (e.g. `cs.CL`)

**Europe PMC**
- `research_europepmc_search(query, page_size=25, cursor_mark="*") -> {results: [...], next_cursor_mark}` (each: `identifier, pmid?, pmcid?, doi?, title, abstract?, authors[{full_name, first_name, last_name, initials}], journal, pub_year, is_open_access, license?, full_text_available`)
- `research_europepmc_fetch_metadata(identifiers: []) -> {results: [...], not_found: [...]}`
- `research_europepmc_fetch_full_text(identifier) -> {location, format: "xml", size_bytes, served_from_storage, resource_uri}` — fails `format_unavailable` if Europe PMC doesn't host full text for this item
- `research_europepmc_parse_full_text(identifier) -> {markdown, resource_uri}` — fails `not_found` if the id hasn't been fetched first

**Cross-provider**
- `research_resolve_identifier(identifier, format) -> {identifier, provider, resolved_url, format, full_text_available?}` — resolves an arXiv id, a Europe PMC id/PMCID, or a DOI of unknown provider to its canonical form. Does **not** accept a URL — a bare DOI is resolved via a doi.org redirect (checked against an allowlisted domain before any further request), everything else is self-identifying by pattern with no network round-trip. Standalone utility, not a required first step when the provider is already known.

**Resources** (read-only; never trigger a fetch or parse — read one that doesn't exist yet and you get a plain not-found, not an error):
- `research://{provider}/{identifier}/{format}/fulltext` — persisted raw full text
- `research://{provider}/{identifier}/{format}/markdown` — persisted parsed markdown

In practice you rarely need to read a resource explicitly: `parse_full_text` already returns the `markdown` string inline, plus the `resource_uri` for re-reading it later (e.g. a fresh session, or a different skill) without re-parsing. The two-step fetch → parse pattern is universal across both providers — always fetch before parse; parse fails `not_found` otherwise.

`rmotd` additionally needs `research_arxiv_list_top_n` (documented in its own SKILL.md). Note there is no Europe PMC equivalent for "recent by category" — its search tool has no recency sort, so `rmotd` is arXiv-only for now.

If an expected tool isn't available in the current session, say so plainly and stop — do not guess at paper content from memory or fall back to general web search as a substitute.
