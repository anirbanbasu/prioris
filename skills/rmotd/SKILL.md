---
name: rmotd
description: "Research message of the day — periodic digest of recent papers (or other prior art) in one or more chosen categories, showing titles and abstracts only, no full-text fetch. Triggers: research message of the day, rmotd, what's new in, latest papers in, daily digest, arxiv digest."
metadata:
  version: "0.1.0"
  status: active
  task_type: open-ended
---

# RMOTD (Research Message of the Day)

See `../../shared/data-layout.md` for the scope boundary shared by this plugin (discovery digest, not synthesis or review), and the tool constraint (`prioris-mcp` only for anything it covers — no built-in web search/fetch as a substitute).

## Scope

Breadth, not depth. Surfaces titles and abstracts for recent items in one or more chosen arXiv categories so the user can decide what's worth opening — never fetches or caches full text for the whole batch. Deep engagement with any single item goes through `discuss` (or `quiz-me`) instead.

arXiv-only for now: Europe PMC's search tool has no recency sort, so there is no "recent by category" equivalent there yet.

## Workflow

1. Determine category or categories — ask if not specified. arXiv organizes by taxonomy code (e.g. `cs.CL`, `cs.AI`, `cs.LG`, `stat.ML`, `q-bio.NC`); help translate a plain-language topic into the right code.
2. Determine n — default 7 if unspecified, keep within 5–10 unless the user asks otherwise.
3. Call `research_arxiv_list_top_n(category, n)` once per requested category.
4. Present a compact list per category: title, authors, submission date (`published`), the abstract in full, and the `arxiv_id` — no full text is fetched or written to `.prioris/papers/` at this stage.
5. If the user wants to go deeper on one of the listed items, hand off to `discuss` (or `quiz-me`) using that item's `arxiv_id`. Don't fetch full text here.

## MCP dependency (in addition to shared)

- `research_arxiv_list_top_n(category, n) -> results[]` — each result: `arxiv_id, title, abstract, authors[{name, affiliation}], categories, primary_category, published, updated, pdf_url, doi?, journal_ref?, comment?`

If `research_arxiv_list_top_n` isn't available, say so rather than substituting a keyword search or guessing at "recent" items from memory. Note: arXiv's own API exposes recency, not a notion of "trending" or citation-weighted importance — treat "top n" as "n most recent" unless a richer ranking signal is explicitly wired up later.

## Argument handling

If invoked with `$ARGUMENTS` giving a category (or categories) and/or a count, use them. Otherwise ask which category and how many items (default 7).
