---
name: reading-log
description: "Recap prior discussions, quick-reads, and quiz sessions by searching prioris-mcp's NotesBackend — filterable by provider, canonical identifiers, a date range, and/or keywords. Also the plugin's general recall search over your own notes. Triggers: reading log, what have I been reading, list my discussions, what did we cover on, pick up where I left off, show my reading history, what papers have I read, catch me up, recap, search my notes, find my notes about."
metadata:
  version: "0.2.0"
  status: active
  task_type: open-ended
---

# Reading Log

See `../../shared/scope.md` for the scope boundary, `../../shared/mcp-contracts.md` for `research_notes_search`'s contract (`#notes`), `../../shared/notes-model.md` for the tag scheme, and `../../shared/context-hygiene.md` for when to nudge the user to clear context.

## Scope

A digest of what's already been recorded, drawn entirely from `research_notes_search` — never a way to discover or read anything new, and never a fetch or a search of arXiv/Europe PMC. Absorbs the "search my notes for X" recall use case via the `keyword` filter, so there's no separate `search-notes` skill. Project-scoped by default (via the same `<project_tag>` every other skill's notes carry); an explicit "across all my projects" ask drops that filter. This is a local IPC call to `prioris-mcp` over stdio with the same reliability characteristics as a file read — `prioris-mcp` is a local, single-user server, not a hosted multi-tenant service — so this is a changed mechanism from the old `.prioris/discussions/` file scan, not a lost guarantee.

## Filters

All optional, combined with AND:

- **provider** — `arxiv`, `europepmc`, `localfile`, or any combination; maps to `research_notes_search`'s `provider` (one call per provider if more than one is named, since a single call takes at most one).
- **canonical identifier(s)** — maps to `canonical_identifier` (requires pairing with exactly one `provider` per call, per the tool's own `invalid_request` rule — run one search per `(provider, identifier)` pair if several are named).
- **date range** — maps to `date_from`/`date_to` (filters on `created_at`). Accepts natural language ("last week", "since June") — convert to absolute ISO dates using the current date before calling.
- **keywords** — maps to `keyword` (matches a note's `text` only, never `tags`/`anchors`/`metadata`). A keyword matching nothing is reported as a zero-result filter, not a cue to search externally.

## Workflow

1. Parse the request into the filters above; no filters means "list everything," project-scoped.
2. Compute `<project_tag>` (unless cross-project was explicitly requested) and call `research_notes_search(tags_all=[<project_tag>], provider?, canonical_identifier?, date_from?, date_to?, keyword?, offset=0, limit=50)`, looping on `has_more`/advancing `offset` until exhausted or enough results are in hand to answer the request.
3. Group results by `(provider, canonical_identifier)`. For each paper, draw a 2-3 sentence gist preferentially from its `section:background-and-research-problem` and `section:takeaways-and-future-avenues` quick-read notes if present (a further `research_notes_search` scoped to `skill:quick-read` and those two `section:` tags); otherwise from the most recent `topic:*` discuss note; otherwise from a `type:recap` quiz-me note; otherwise state plainly that there's no synthesized content yet for that paper.
4. Enrich each paper's title/authors via `uv run --project <plugin root> python ../../shared/scripts/metadata_cache.py read <provider> <identifier>`; on a cache miss, show the bare `(provider, identifier)` instead of a title rather than fetching it — reading-log never calls out to a provider itself, per Scope above, so an uncached title is only ever populated as a side effect of `discuss`/`quick-read`/`quiz-me` running on that paper.
5. Sort most-recent-first by default (by the latest matching note's `updated_at` per paper) unless the user asks for a different order.
6. Present the list, then separately list any requested identifiers/keywords that matched nothing, phrased as "no notes found" — not an error.
7. Point at `discuss`, `quick-read`, or `quiz-me` with the relevant `(provider, identifier)` for any item the user wants to revisit.
8. Per `../../shared/context-hygiene.md`, if this conversation has been running long, close with a brief, polite nudge to clear context before diving back into a paper.

## Argument handling

If invoked with `$ARGUMENTS` containing filter language (a provider name, one or more identifiers, a date phrase, or keywords/topics, in any combination or free-text mix), parse it into the filters above and go straight to the Workflow. Otherwise list everything, project-scoped, most recent first.
