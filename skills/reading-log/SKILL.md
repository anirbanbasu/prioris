---
name: reading-log
description: "List concise, one-paragraph recaps of already-cached paper discussions under .prioris/discussions/, so the user can pick up a prior thread — filterable by provider, a list of identifiers, a date range, and/or keywords. Purely local: never calls prioris-mcp, and never fetches or searches to fill in a filter that matches nothing — an unmatched id or keyword is reported as not-found in the cache instead. Triggers: reading log, what have I been reading, list my discussions, what did we cover on, pick up where I left off, show my reading history, what papers have I read, catch me up, recap."
metadata:
  version: "0.1.0"
  status: active
  task_type: open-ended
---

# Reading Log

See `../../shared/scope.md` for the scope boundary shared by every skill in this plugin, and `../../shared/data-layout.md` for providers, `.prioris/` layout, and frontmatter schema. Unlike the other skills here, `reading-log` needs none of the shared MCP tool contracts (`../../shared/mcp-contracts.md`) — see "No MCP dependency" below.

## Scope

A digest of what's already been discussed, not a way to discover or read anything new. `reading-log` only reads files already present under `.prioris/discussions/<provider>/*.md` — it never calls a `prioris-mcp` tool, never fetches a paper, and never searches arXiv/Europe PMC to resolve a filter. If a requested id or keyword doesn't match anything in the cache, that is the answer: report it as not found, don't try to make it true by fetching or searching. This mirrors the plugin's tool constraint (see shared doc) but goes further here — even the fallback of "search for it" is out of scope for this skill specifically, because its whole point is reporting on what's *already* local.

Keep it cheap: read the (already condensed) discussion notes, not the full cached paper text under `.prioris/papers/`. A recap is a paragraph, not a re-read.

## Filters

All filters are optional and combine with AND when more than one is given. If none are given, list every cached discussion.

- **provider** — `arxiv`, `europepmc`, or both (default: both). Restricts which `.prioris/discussions/<provider>/` subdirectories are scanned.
- **ids** — one or more canonical identifiers (or a title/URL the user expects to already be cached — resolve it to an identifier by inspection of cached frontmatter, not by calling `research_resolve_identifier` or any search tool). Keep only files whose frontmatter `identifier` matches. Any requested id that matches no cached file is reported by name as not cached — do not fetch it.
- **date range** — on `read_at` frontmatter (fall back to `fetched_at`, then file mtime, if `read_at` is absent). Accepts natural language ("last week", "since June", "in July 2026") — convert relative phrases to absolute dates using the current date before filtering.
- **keywords** — one or more terms, matched case-insensitively against `title`, `tags`, and the discussion note body (e.g. the "Quick read" section). Multiple keywords are ANDed by default unless the user asks for "any of" / OR. A keyword matching nothing is reported as a zero-result filter, not a cue to search externally.

## Workflow

1. Parse the request for filters (provider / ids / date range / keywords); if the user gives none, treat this as "list everything."
2. Enumerate candidate files under `.prioris/discussions/<provider>/*.md` for the selected provider(s). If the directory tree doesn't exist or is empty, say so plainly and stop — there is nothing to log yet.
3. Apply filters in order (provider narrows the directory scan; ids, date range, and keywords narrow the file list). Track any requested id or keyword that produced zero matches so it can be reported alongside the results.
4. For each remaining file, read its frontmatter and body, and produce one paragraph containing: title, provider, identifier, the relevant date (`read_at` or fallback), tags if present, and a 2-3 sentence gist. Draw the gist from the "Quick read" section if present; otherwise from other discussion/quiz notes in the file; if the file has no synthesized content yet (frontmatter only), say so rather than inventing a summary.
5. Sort by most recent date first unless the user asks for a different order (e.g. by provider, alphabetical by title).
6. Present the list, then separately list any requested ids/keywords that matched nothing, phrased as "not found in the local cache" — not as an error.
7. Close by pointing at `discuss`, `quiz-me`, or `quick-read` with the relevant `identifier` for any item the user wants to revisit.

## No MCP dependency

This skill performs no `prioris-mcp` calls at all — only local file reads under `.prioris/discussions/`. If asked to filter by something not yet in the cache, do not fall back to `discuss`'s search/fetch flow from within `reading-log`; tell the user it isn't cached and let them invoke `discuss` (or `quick-read`) themselves if they want to add it.

## Argument handling

If invoked with `$ARGUMENTS` containing filter language (a provider name, one or more identifiers, a date phrase, or keywords/topics, in any combination or free-text mix), parse it into the filters above and go straight to the Workflow. Otherwise list everything cached, most recent first.
