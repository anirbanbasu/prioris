# Shared: Core MCP Tool Contracts

Referenced by `discuss` and `quick-read`. Assumes a companion MCP server (the `prioris-mcp` server, https://pypi.org/project/prioris-mcp/) exposing at minimum:

**arXiv**
- `research_arxiv_search(query, max_results=10, start=0, sort_by?, sort_order?) -> results[]` (each: `arxiv_id, title, abstract, authors[{name, affiliation}], categories, primary_category, published, updated, pdf_url, doi?, journal_ref?, comment?`)
- `research_arxiv_fetch_metadata(arxiv_ids: []) -> {results: [...], not_found: [...]}`
- `research_arxiv_fetch_full_text(arxiv_id, format: "pdf"|"html") -> {location, format, size_bytes, served_from_storage, resource_uri}`
- `research_arxiv_parse_full_text(arxiv_id, format, offset=0, limit=None) -> {markdown, offset, limit, total_length, has_more, resource_uri}` — fails `not_found` if the id hasn't been fetched first. Paginated — see "Paging through full text" below.
- `research_arxiv_list_top_n(include_categories, n, exclude_categories?) -> results[]` — most recent items across one or more arXiv taxonomy codes (`include_categories` combined with AND, optional `exclude_categories` combined with ANDNOT), e.g. `cs.CL`

**Europe PMC**
- `research_europepmc_search(query, page_size=25, cursor_mark="*") -> {results: [...], next_cursor_mark}` (each: `identifier, pmid?, pmcid?, doi?, title, abstract?, authors[{full_name, first_name, last_name, initials}], journal, pub_year, is_open_access, license?, full_text_available`)
- `research_europepmc_fetch_metadata(identifiers: []) -> {results: [...], not_found: [...]}`
- `research_europepmc_fetch_full_text(identifier) -> {location, format: "xml", size_bytes, served_from_storage, resource_uri}` — fails `format_unavailable` if Europe PMC doesn't host full text for this item
- `research_europepmc_parse_full_text(identifier, offset=0, limit=None) -> {markdown, offset, limit, total_length, has_more, resource_uri}` — fails `not_found` if the id hasn't been fetched first. Paginated — see "Paging through full text" below.

**Local filesystem** (see `local-file-handling.md` for the `@file` workflow this backs — no search, metadata, or identifier-resolution capability exists for this source, only these two calls)
- `research_localfile_fetch_full_text(content_base64, filename=None, format="pdf") -> {id, location, format, size_bytes, served_from_storage, resource_uri}` — takes the caller's own PDF bytes, base64-encoded, not a path: there is no server-side filesystem to resolve against, so this works identically under stdio and streamable-http/http transports. `filename` is an optional hint stored for reference only, never used to derive identity or location. Fails `file_too_large` if the encoded payload's length alone implies it would exceed the server's configured size ceiling (checked before decoding), again post-decode in case base64's rounding slipped a couple of bytes past that pre-check, `invalid_request` if `content_base64` doesn't decode as valid base64, and `invalid_request` if the decoded bytes don't sniff as a PDF (checked by magic-byte prefix, not by trusting a `.pdf`-looking filename). `id` is a caller-facing identifier this call mints (or, if the exact same file content was already fetched, the existing one) — opaque, derived from a hash of the decoded content, not from `filename`. Always re-decodes and re-hashes the given bytes fresh on every call — never assume a previously-returned `id` still corresponds to the file's current on-disk content without re-reading and re-sending it first.
- `research_localfile_parse_full_text(id, offset=0, limit=None) -> {markdown, offset, limit, total_length, has_more, resource_uri}` — `id` is the caller-facing id `fetch_full_text` returned, not `path`; fails `not_found` if that id was never returned by `fetch_full_text`. Paginated exactly like the other providers' `parse_full_text` — see "Paging through full text" below. No `format` choice exists for this source (always `pdf`).

**Cross-provider**
- `research_resolve_identifier(identifier, format) -> {identifier, provider, resolved_url, format, full_text_available?}` — resolves an arXiv id, a Europe PMC id/PMCID, or a DOI of unknown provider to its canonical form. Does **not** accept a URL — a bare DOI is resolved via a doi.org redirect (checked against an allowlisted domain before any further request), everything else is self-identifying by pattern with no network round-trip. Standalone utility, not a required first step when the provider is already known. Does not resolve local files — there is nothing to resolve; a local file's identity is its content hash, established only by calling `research_localfile_fetch_full_text` itself.

**Resources** (read-only; never trigger a fetch or parse — read one that doesn't exist yet and you get a plain not-found, not an error):
- `research://{provider}/{identifier}/{format}/fulltext` — persisted raw full text, returned whole (not paginated)
- `research://{provider}/{identifier}/{format}/markdown{?offset,limit}` — persisted parsed markdown, one page at a time: `{markdown, offset, limit, total_length, has_more}`. Paginated identically to `parse_full_text` below (same params, same shape minus `resource_uri`, since the read is already keyed by that URI).
- `research://arxiv/categories` — arXiv's queryable category codes and names, returned whole (not paginated). Read this to look up or confirm a taxonomy code (e.g. for `research_arxiv_search`'s `cat:` syntax or `research_arxiv_list_top_n`'s `include_categories`/`exclude_categories`) rather than guessing one from memory.

In practice you rarely need to read a resource explicitly: `parse_full_text` already returns a `markdown` page inline, plus the `resource_uri` for re-reading it later (e.g. a fresh session, or a different skill) without re-parsing. The two-step fetch → parse pattern is universal across all three sources — always fetch before parse; parse fails `not_found` otherwise.

## Paging through full text

`parse_full_text` (all three sources) and the `.../markdown` resource no longer return the whole document in one call — each call returns one bounded page of Markdown (`offset`, `limit`, `total_length`, `has_more`), capped by a server-side default (currently ~20,000 characters) unless a larger `limit` is passed explicitly. A short paper may fit in a single page (`has_more: false` immediately); a long one won't.

Any skill that needs the *complete* text — e.g. writing the full cached copy to `.prioris/papers/<provider>/<identifier>.md` — must loop rather than assume one call is enough:

1. Call with `offset=0` (default), collect `markdown`.
2. While the response's `has_more` is `true`, call again with `offset` advanced by the length of the `markdown` just received (not by `limit` — the last page can be shorter), and append the new `markdown` to what you have.
3. Stop once `has_more` is `false`; concatenate the collected pages in order before writing or discussing the text.

This applies the same way whether you're calling `parse_full_text` directly or re-reading a cached paper via its `resource_uri` instead of re-parsing.

`rmotd` additionally needs `research_arxiv_list_top_n`, documented in its own SKILL.md rather than here since it's the only tool `rmotd` uses.

If an expected `prioris-mcp` tool isn't available in the current session, say so plainly and stop — do not guess at paper content from memory or fall back to a built-in web search/fetch tool as a substitute (see `scope.md`).
