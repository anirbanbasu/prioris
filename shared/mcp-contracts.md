# Shared: Core MCP Tool Contracts

Referenced by `discuss` and `quick-read`. Assumes a companion MCP server (the `prioris-mcp` server, https://pypi.org/project/prioris-mcp/) exposing at minimum:

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

`rmotd` additionally needs `research_arxiv_list_top_n`, documented in its own SKILL.md rather than here since it's the only tool `rmotd` uses.

If an expected `prioris-mcp` tool isn't available in the current session, say so plainly and stop — do not guess at paper content from memory or fall back to a built-in web search/fetch tool as a substitute (see `scope.md`).
