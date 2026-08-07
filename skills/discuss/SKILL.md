---
name: discuss
description: "Search for, fetch, and discuss one academic paper (or other prior art) against your own research ideas — one item at a time, via arXiv or Europe PMC. Caches cleaned content and discussion notes as human-readable markdown under .prioris/. Triggers: discuss this paper, find papers about, what does this paper say about, how does this relate to my idea, literature review, related work, prior art. Out of scope: does NOT draft, outline, or write any part of a manuscript — for that, use a different tool."
metadata:
  version: "0.1.0"
  status: active
  task_type: open-ended
---

# Discuss

See `../../shared/scope.md` for the scope boundary and tool constraint, `../../shared/data-layout.md` for providers and the `.prioris/` layout/frontmatter schema, `../../shared/mcp-contracts.md` for the core MCP tool contracts, `../../shared/local-file-handling.md` for the `@file` workflow, and `../../shared/context-hygiene.md` for when to nudge the user to clear context — all shared by every skill in this plugin.

## Why one paper at a time

Holding many full papers in context at once degrades comparison quality and burns the context window fast — a single 30-page paper is already roughly 15-25K tokens. This skill deliberately works on one paper's full text at a time. Cross-paper synthesis is a deferred feature, to be built later on top of the cached notes, not on simultaneous full-text loading.

## Workflow

1. **Search**
   - **Local search first** — for a search-like query (a topic, title, or keyword search — not a bare identifier/DOI/URL), call `research_search_fetched(query)` before touching any provider (contract in `../../shared/mcp-contracts.md`) — scoped to a specific `provider` only if the user's query already named one. This is read-only over content already fetched *and* parsed on the server and never triggers a fetch itself.
     - **Matches found**: for each distinct `(provider, identifier)`, enrich it with title/authors by reading `.prioris/papers/<provider>/<identifier>.md`'s frontmatter if that file exists locally (fall back to showing the bare identifier plus the match's `snippet` if it doesn't — e.g. the content was fetched by a different client; for `localfile` matches, prefer the frontmatter `source_path` over a blank `title`). Present these clearly labeled as already in local research, distinct from a fresh provider search. If the user picks one directly, it's already fully cached both server- and client-side — skip straight to Discuss (step 4), no Fetch needed. Otherwise ask whether to also search arXiv/Europe PMC to expand beyond what's already fetched, and only continue to provider search below if they say yes.
     - **No matches**: continue straight to provider search below without asking — there's nothing to show yet.
   - **Provider search** — pick the relevant provider(s) from subject matter (biomedical → `research_europepmc_search`, everything else → `research_arxiv_search`; both if genuinely ambiguous). Per relevant provider, come up with up to 3 semantically distinct variations of the query suited to that provider's own query syntax (e.g. broader phrasing, a synonym swap, a narrower/qualified phrasing) and run them concurrently — up to 3 calls per provider (up to 6 total when both apply). Each provider paces its own calls server-side via its request queue, so issuing them concurrently from here is safe. Merge results across variations and providers, de-duplicating by `(provider, identifier)` — the same paper turning up under more than one variation is one entry, not several; flag any entry that already appeared among the local matches above instead of repeating it. If the user instead handed a bare DOI or an identifier of unclear provenance, skip both local and provider search entirely and call `research_resolve_identifier` first — see "Argument handling" below if what you have is a URL rather than a bare id/DOI. Present a short ranked list (provider, title, authors, year, one-line abstract snippet). Do not fetch full text yet.

   **If the user instead handed you a local file (e.g. via `@file`), skip Search (both local and provider) and Select entirely** — there's nothing to search, go straight to Fetch's `localfile` branch below.
2. **Select** — confirm with the user which single paper to open, unless they've already named one directly.
3. **Fetch** — check `.prioris/papers/<provider>/<identifier>.md` first; if a cached copy already exists, reuse it instead of calling the MCP server again — unless the user explicitly asked to refetch or get the latest version, per `../../shared/data-layout.md#forcing-a-refetch`, in which case fetch fresh below and overwrite the cache entry. Otherwise:
   - **arXiv**: call `research_arxiv_fetch_full_text(arxiv_id, format="pdf")` (PDF preferred — arXiv's HTML rendering isn't available for every paper, especially older or figure-heavy ones; retry with `format="html"` if PDF isn't available), then `research_arxiv_parse_full_text(arxiv_id, format)` to get the markdown.
   - **Europe PMC**: call `research_europepmc_fetch_full_text(identifier)` (format is always `xml`), then `research_europepmc_parse_full_text(identifier)`. If that call fails because Europe PMC has no full text for this item — there's no structured error code to check, recognize it from the tool's error message (see `../../shared/mcp-contracts.md`'s note on failures) — say so and offer to discuss from the abstract/metadata only instead.
   - **Local file**: follow `../../shared/local-file-handling.md` in full — unlike the other two providers, the cache check comes *after* fetching, not before, since the file's identity isn't known until `research_localfile_fetch_full_text` re-hashes its current content.
   - `parse_full_text` returns one page of Markdown, not necessarily the whole paper — loop on `has_more` per `../../shared/mcp-contracts.md#paging-through-full-text` until you've collected the complete text, then concatenate the pages.
   - Write the concatenated `markdown` plus frontmatter (including `resource_uri`, and for `localfile` also `source_path`) to `.prioris/papers/<provider>/<identifier>.md`.
4. **Discuss** — read the *one* cached paper into context and discuss it against whatever idea or question the user brings: its claims, method, evidence, limitations, and how it relates to the user's stated idea (agreement, contradiction, gap, extension). Do not pull other papers' full text into this step — reference prior discussion notes (frontmatter/summary only) if relevant instead.
5. **Record** — after a substantive discussion, write a concise synthesis (what the paper says, what was concluded, open questions) under a `## Discussion` heading and set `read_at`. Do this automatically — never ask the user whether to save it first. Use `../../shared/scripts/update_notes_section.py` (see `../../shared/scripts/README.md`) to write it: pass your synthesis as the content file, `"## Discussion"` as the section header, and `read_at` — plus the rest of the frontmatter (`../../shared/data-layout.md`'s schema) on a first write — via `--frontmatter`. This merges cleanly with any `Quick read` or `Quiz notes` section another skill already wrote to the same file, rather than risking one silently clobbering the other.
6. **Check in on context** — per `../../shared/context-hygiene.md`, if this conversation has been running long, close with a brief, polite nudge to clear context before the next paper.

## Argument handling

If invoked with `$ARGUMENTS` containing a paper identifier, URL, search query, or local file path (e.g. `@file`), use it to skip straight to the Search/Fetch step. Otherwise ask what the user is looking for.

If `$ARGUMENTS` (or the user) hands you a URL, see `../../shared/url-handling.md` for how to extract the canonical identifier before calling anything — no `prioris-mcp` tool accepts a raw URL as input. If instead you're handed a local file path, see `../../shared/local-file-handling.md` for how to read and encode it and for the fetch sequence — a local file is not searched or resolved, it's fetched directly.
