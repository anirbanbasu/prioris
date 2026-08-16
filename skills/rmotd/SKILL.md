---
name: rmotd
description: "Research message of the day — periodic digest of recent papers (or other prior art) via arXiv category browsing or OpenAlex semantic topic search, showing titles and abstracts only, no full-text fetch. Triggers: research message of the day, rmotd, what's new in, latest papers in, daily digest, arxiv digest."
metadata:
  version: "0.2.0"
  status: active
  task_type: open-ended
---

# RMOTD (Research Message of the Day)

See `../../shared/scope.md` for the scope boundary shared by this plugin (discovery digest, not synthesis or review) and the tool constraint (`prioris-mcp` only for anything it covers — no built-in web search/fetch as a substitute).

## Scope

Breadth, not depth. Surfaces titles and abstracts for recent or relevant items — either recent items in one or more chosen arXiv categories, or items semantically ranked against a topic description via OpenAlex — so the user can decide what's worth opening; never fetches or caches full text for the whole batch. Deep engagement with any single item goes through `discuss` (or `quiz-me`) instead.

Europe PMC has no source-generic recency/category-browse tool of its own, so it isn't one of the two source branches below — OpenAlex semantic search is the way to reach biomedical/life-science literature through this skill.

## Workflow

1. **Determine source** — ask via `AskUserQuestion` (single-select) whether to browse `arXiv (by category)` or run an `OpenAlex semantic search (by topic description)`, before anything else. The two branches take a different kind of input and call a different tool — see below.

2. **arXiv branch**
   1. Determine category or categories — ask if not specified. arXiv organizes by taxonomy code (e.g. `cs.CL`, `cs.AI`, `cs.LG`, `stat.ML`, `q-bio.NC`); if unsure of the exact code for a plain-language topic, read the `research://arxiv/categories` resource for the authoritative list rather than guessing from memory. If the user names several categories, clarify whether they want a separate digest per category (the common case) or the intersection of all of them at once (items cross-listed in every named category — a narrower, less common ask). Also ask whether anything should be excluded to cut noise within a given digest (e.g. "cs.LG but not stat.ML").
   2. Determine n — default 7 if unspecified, keep within 5–10 unless the user asks otherwise.
   3. Call `research_arxiv_list_top_n(include_categories, n, exclude_categories=None)` once per requested digest: for separate per-category digests, call once per category with `include_categories` set to that single code; for an intersection, pass all the categories together in one call. Pass `exclude_categories` on a call when the user wants items in that digest's category (or categories) filtered to exclude an overlapping/noisy one.

3. **OpenAlex branch**
   1. Ask for one free-text topic description — a title/abstract-style sentence or two, not a category code or keyword string; the embedding model handles paraphrase itself, so there's no code to look up here.
   2. Determine n (`max_results`) — same default-7/keep-within-5–10 guidance as the arXiv branch, capped by `research_discovery`'s own 50-match ceiling.
   3. Call `research_discovery(query, max_results=n)` once — a single digest, since there's only one query, not per-category digests. `from_year`/`to_year`/`open_access_only` are available if the user wants to narrow further; leave them unset/`false` by default.

4. **Present a compact list per digest**: title, authors, submission date (arXiv's `published`) or publication year (OpenAlex's `publication_year`), and an identifier (arXiv's `arxiv_id`, or OpenAlex's `openalex_id` plus `doi` if present) — no full text is fetched or written to `.prioris/papers/` at this stage.
   - Always include the abstract. If it's 300 words or fewer, show it verbatim, unedited. Only when it runs longer than 300 words, condense it to a 300-word (or shorter) summary that preserves the paper's own claims and terminology rather than a generic paraphrase — this keeps long abstracts (common in physics/math preprints) from dominating the digest while still surfacing every item's content. An OpenAlex hit's abstract can be `null` — say so rather than inventing one.
   - For OpenAlex items, additionally note `work_type` (see `research://openalex/work-types` if the code needs interpreting) — arXiv items don't carry this field.

5. **Go deeper** — if the user wants to go deeper on one listed item, hand off to `discuss` (or `quiz-me`); don't fetch full text here.
   - arXiv-sourced item → hand its `arxiv_id` to `discuss`/`quiz-me`, as before.
   - OpenAlex-sourced item → check its `fetch_route`. `kind == "known_provider"` → hand `fetch_route.provider`/`fetch_route.identifier` to `discuss`/`quiz-me`, same as an arXiv item. `kind` `"oa_link"` or `"manual_upload"` → not fetchable through this plugin; surface `fetch_route.pdf_url` (if present) or the item's own `doi` and tell the user to open it themselves — the same "not fetchable here" handling `discuss`'s own OpenAlex branch uses.

## MCP dependency (in addition to shared)

- `research_arxiv_list_top_n(include_categories, n, exclude_categories=None) -> results[]` — each result: `arxiv_id, title, abstract, authors[{name, affiliation}], categories, primary_category, published, updated, pdf_url, doi?, journal_ref?, comment?`. `include_categories` takes one or more taxonomy codes combined with AND (so more than one narrows to the intersection, not a union); `exclude_categories` is optional and combined with ANDNOT.
- `research://arxiv/categories` resource — arXiv's queryable category codes and names; read it to look up or confirm a code instead of guessing.
- `research_discovery(query, max_results?, page=1, from_year?, to_year?, open_access_only=false) -> {hits: [<DiscoveryHit>, ...], page, per_page, total, has_more}` — see `../../shared/mcp-contracts.md`'s "External discovery" section for the full contract, including the `DiscoveryHit.fetch_route` shape used in step 5 above.
- `research://openalex/work-types` resource — OpenAlex's work `type` vocabulary; read it to interpret a `work_type` code shown in step 4 above.

If the tool the chosen branch needs (`research_arxiv_list_top_n` or `research_discovery`) isn't available, say so rather than substituting a keyword search or guessing at "recent"/"relevant" items from memory. Note the two branches answer genuinely different questions: arXiv's API exposes recency, not "trending" or citation-weighted importance, so treat its "top n" as "n most recent"; OpenAlex's `search.semantic` ranks by embedding similarity to the given topic description, not recency, so its "top n" means "n most related," not "n newest."

## Argument handling

If invoked with `$ARGUMENTS` giving a source (arXiv or OpenAlex), a category or topic description, and/or a count, use them — infer the source from whether what's given looks like an arXiv category code vs a topic description, asking if genuinely ambiguous. Otherwise ask which source first, then which category/topic and how many items (default 7).
