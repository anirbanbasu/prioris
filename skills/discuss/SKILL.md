---
name: discuss
description: "Search for, fetch, and discuss one academic paper (or other prior art) against your own research ideas — one item at a time. Fetches over HTTPS (HTML-first, PDF fallback), caches cleaned content and discussion notes as human-readable markdown under .prioris/. Triggers: discuss this paper, find papers about, what does this paper say about, how does this relate to my idea, literature review, related work, prior art. Out of scope: does NOT draft, outline, or write any part of a manuscript — for that, use a different tool."
metadata:
  version: "0.2.0"
  status: active
  task_type: open-ended
---

# Discuss

See `../../shared/data-layout.md` for the scope boundary, `.prioris/` layout, frontmatter schema, and core MCP tool contracts shared by every skill in this plugin.

## Why one paper at a time

Holding many full papers in context at once degrades comparison quality and burns the context window fast — a single 30-page paper is already roughly 15-25K tokens. This skill deliberately works on one paper's full text at a time. Cross-paper synthesis is a deferred feature, to be built later on top of the cached notes, not on simultaneous full-text loading.

## Workflow

1. **Search** — use the `search_papers` MCP tool to find candidates for the user's query. Present a short ranked list (title, authors, year, venue, one-line abstract snippet). Do not fetch full text yet.
2. **Select** — confirm with the user which single paper to open, unless they've already named one directly.
3. **Fetch** — use `fetch_paper` (HTML source preferred; PDF extraction only as fallback) to retrieve and cache the paper under `.prioris/papers/<paper-id>.md`. If a fresh cached copy already exists, reuse it instead of re-fetching.
4. **Discuss** — read the *one* cached paper into context and discuss it against whatever idea or question the user brings: its claims, method, evidence, limitations, and how it relates to the user's stated idea (agreement, contradiction, gap, extension). Do not pull other papers' full text into this step — reference prior discussion notes (frontmatter/summary only) if relevant instead.
5. **Record** — after a substantive discussion, write or update `.prioris/discussions/<paper-id>.md` with a concise synthesis (what the paper says, what was concluded, open questions) and set `read_at`. Ask before overwriting existing notes rather than silently clobbering them.

## Argument handling

If invoked with `$ARGUMENTS` containing a paper identifier, URL, or search query, use it to skip straight to the Search/Fetch step. Otherwise ask what the user is looking for.
