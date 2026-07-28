---
name: rmotd
description: "Research message of the day — periodic digest of recent papers (or other prior art) in one or more chosen categories, showing titles and abstracts only, no full-text fetch. Triggers: research message of the day, rmotd, what's new in, latest papers in, daily digest, arxiv digest."
metadata:
  version: "0.1.0"
  status: active
  task_type: open-ended
---

# RMOTD (Research Message of the Day)

See `../../shared/scope.md` for the scope boundary shared by this plugin (discovery digest, not synthesis or review) and the tool constraint (`prioris-mcp` only for anything it covers — no built-in web search/fetch as a substitute).

## Scope

Breadth, not depth. Surfaces titles and abstracts for recent items in one or more chosen arXiv categories so the user can decide what's worth opening — never fetches or caches full text for the whole batch. Deep engagement with any single item goes through `discuss` (or `quiz-me`) instead.

arXiv-only for now: Europe PMC's search tool has no recency sort, so there is no "recent by category" equivalent there yet.

## Workflow

1. Determine category or categories — ask if not specified. arXiv organizes by taxonomy code (e.g. `cs.CL`, `cs.AI`, `cs.LG`, `stat.ML`, `q-bio.NC`); if unsure of the exact code for a plain-language topic, read the `research://arxiv/categories` resource for the authoritative list rather than guessing from memory. If the user names several categories, clarify whether they want a separate digest per category (the common case) or the intersection of all of them at once (items cross-listed in every named category — a narrower, less common ask). Also ask whether anything should be excluded to cut noise within a given digest (e.g. "cs.LG but not stat.ML").
2. Determine n — default 7 if unspecified, keep within 5–10 unless the user asks otherwise.
3. Call `research_arxiv_list_top_n(include_categories, n, exclude_categories=None)` once per requested digest: for separate per-category digests, call once per category with `include_categories` set to that single code; for an intersection, pass all the categories together in one call. Pass `exclude_categories` on a call when the user wants items in that digest's category (or categories) filtered to exclude an overlapping/noisy one.
4. Present a compact list per digest: title, authors, submission date (`published`), and the `arxiv_id` — no full text is fetched or written to `.prioris/papers/` at this stage.
   - Always include the abstract. If it's 300 words or fewer, show it verbatim, unedited. Only when it runs longer than 300 words, condense it to a 300-word (or shorter) summary that preserves the paper's own claims and terminology rather than a generic paraphrase — this keeps long abstracts (common in physics/math preprints) from dominating the digest while still surfacing every item's content.
5. If the user wants to go deeper on one of the listed items, hand off to `discuss` (or `quiz-me`) using that item's `arxiv_id`. Don't fetch full text here.

## MCP dependency (in addition to shared)

- `research_arxiv_list_top_n(include_categories, n, exclude_categories=None) -> results[]` — each result: `arxiv_id, title, abstract, authors[{name, affiliation}], categories, primary_category, published, updated, pdf_url, doi?, journal_ref?, comment?`. `include_categories` takes one or more taxonomy codes combined with AND (so more than one narrows to the intersection, not a union); `exclude_categories` is optional and combined with ANDNOT.
- `research://arxiv/categories` resource — arXiv's queryable category codes and names; read it to look up or confirm a code instead of guessing.

If `research_arxiv_list_top_n` isn't available, say so rather than substituting a keyword search or guessing at "recent" items from memory. Note: arXiv's own API exposes recency, not a notion of "trending" or citation-weighted importance — treat "top n" as "n most recent" unless a richer ranking signal is explicitly wired up later.

## Argument handling

If invoked with `$ARGUMENTS` giving a category (or categories) and/or a count, use them. Otherwise ask which category and how many items (default 7).
