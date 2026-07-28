---
name: discuss
description: "Search for, fetch, and discuss one academic paper (or other prior art) against your own research ideas — one item at a time, via arXiv or Europe PMC. Caches cleaned content and discussion notes as human-readable markdown under .prioris/. Triggers: discuss this paper, find papers about, what does this paper say about, how does this relate to my idea, literature review, related work, prior art. Out of scope: does NOT draft, outline, or write any part of a manuscript — for that, use a different tool."
metadata:
  version: "0.1.0"
  status: active
  task_type: open-ended
---

# Discuss

See `../../shared/scope.md` for the scope boundary and tool constraint, `../../shared/data-layout.md` for providers and the `.prioris/` layout/frontmatter schema, and `../../shared/mcp-contracts.md` for the core MCP tool contracts — all shared by every skill in this plugin.

## Why one paper at a time

Holding many full papers in context at once degrades comparison quality and burns the context window fast — a single 30-page paper is already roughly 15-25K tokens. This skill deliberately works on one paper's full text at a time. Cross-paper synthesis is a deferred feature, to be built later on top of the cached notes, not on simultaneous full-text loading.

## Workflow

1. **Search** — pick the provider from the subject matter (biomedical → `research_europepmc_search`, everything else → `research_arxiv_search`; search both and merge if genuinely ambiguous). If the user instead handed you a bare DOI or an identifier of unclear provenance, call `research_resolve_identifier` first to determine provider and canonical identifier — see "Argument handling" below if what you have is a URL rather than a bare id/DOI. Present a short ranked list (provider, title, authors, year, one-line abstract snippet). Do not fetch full text yet.
2. **Select** — confirm with the user which single paper to open, unless they've already named one directly.
3. **Fetch** — check `.prioris/papers/<provider>/<identifier>.md` first; if a cached copy already exists, reuse it instead of calling the MCP server again. Otherwise:
   - **arXiv**: call `research_arxiv_fetch_full_text(arxiv_id, format="pdf")` (PDF preferred — arXiv's HTML rendering isn't available for every paper, especially older or figure-heavy ones; retry with `format="html"` if PDF isn't available), then `research_arxiv_parse_full_text(arxiv_id, format)` to get the markdown.
   - **Europe PMC**: call `research_europepmc_fetch_full_text(identifier)` (format is always `xml`), then `research_europepmc_parse_full_text(identifier)`. If this fails `format_unavailable`, Europe PMC has no full text for this item — say so and offer to discuss from the abstract/metadata only instead.
   - `parse_full_text` returns one page of Markdown, not necessarily the whole paper — loop on `has_more` per `../../shared/mcp-contracts.md#paging-through-full-text` until you've collected the complete text, then concatenate the pages.
   - Write the concatenated `markdown` plus frontmatter (including `resource_uri`) to `.prioris/papers/<provider>/<identifier>.md`.
4. **Discuss** — read the *one* cached paper into context and discuss it against whatever idea or question the user brings: its claims, method, evidence, limitations, and how it relates to the user's stated idea (agreement, contradiction, gap, extension). Do not pull other papers' full text into this step — reference prior discussion notes (frontmatter/summary only) if relevant instead.
5. **Record** — after a substantive discussion, write or update `.prioris/discussions/<provider>/<identifier>.md` with a concise synthesis (what the paper says, what was concluded, open questions) and set `read_at`. Ask before overwriting existing notes rather than silently clobbering them.

## Argument handling

If invoked with `$ARGUMENTS` containing a paper identifier, URL, or search query, use it to skip straight to the Search/Fetch step. Otherwise ask what the user is looking for.

If `$ARGUMENTS` (or the user) hands you a URL, see `../../shared/url-handling.md` for how to extract the canonical identifier before calling anything — no `prioris-mcp` tool accepts a raw URL as input.
