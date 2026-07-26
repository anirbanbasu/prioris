---
name: rmotd
description: "Research message of the day — periodic digest of recent papers (or other prior art) in one or more chosen categories, showing titles and abstracts only, no full-text fetch. Triggers: research message of the day, rmotd, what's new in, latest papers in, daily digest, arxiv digest."
metadata:
  version: "0.2.0"
  status: active
  task_type: open-ended
---

# RMOTD (Research Message of the Day)

See `../../shared/data-layout.md` for the scope boundary shared by this plugin (discovery digest, not synthesis or review).

## Scope

Breadth, not depth. Surfaces titles and abstracts for recent items in one or more chosen categories so the user can decide what's worth opening — never fetches or caches full text for the whole batch. Deep engagement with any single item goes through `discuss` (or `quiz-me`) instead.

## Workflow

1. Determine category or categories — ask if not specified. arXiv organizes by taxonomy code (e.g. `cs.CL`, `cs.AI`, `cs.LG`, `stat.ML`, `q-bio.NC`); help translate a plain-language topic into the right code.
2. Determine n — default 7 if unspecified, keep within 5–10 unless the user asks otherwise.
3. Call `list_recent` once per requested category. Source defaults to arXiv but the tool signature is source-generic, since other sources (and non-paper prior art) may be added later.
4. Present a compact list per category: title, authors, submission date, the abstract in full, and the item's id — no full text is fetched or written to `.prioris/papers/` at this stage.
5. If the user wants to go deeper on one of the listed items, hand off to `discuss` (or `quiz-me`) using that item's id. Don't fetch full text here.

## MCP dependency (in addition to shared)

- `list_recent(source, category, n) -> [{paper_id, title, authors, submitted_at, abstract, url}]`

If `list_recent` isn't available, say so rather than substituting a keyword search or guessing at "recent" items from memory. Note: arXiv's own API exposes recency, not a notion of "trending" or citation-weighted importance — treat "top n" as "n most recent" unless a richer ranking signal is explicitly wired up later.

## Argument handling

If invoked with `$ARGUMENTS` giving a category (or categories) and/or a count, use them. Otherwise ask which category and how many items (default 7).
