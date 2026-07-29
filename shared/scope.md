# Shared: Scope and Tool Constraint

Referenced by every skill in this plugin (`../skills/discuss`, `../skills/quick-read`, `../skills/quiz-me`, `../skills/reading-log`, `../skills/rmotd`, `../skills/manage-storage`).

## Scope (applies to every skill in this plugin)

This plugin finds, reads, and discusses prior art — academic papers today, other sources later — one item at a time. No skill in this plugin drafts, outlines, or writes any part of a manuscript. If asked to write or draft paper content, decline and redirect toward discussion instead.

## Tool constraint: `prioris-mcp` for anything it covers

For any search, full-text fetch, metadata fetch, or identifier resolution that a `prioris-mcp` tool can perform (see `data-layout.md` and `mcp-contracts.md` for the tools themselves, and `research_arxiv_list_top_n` for `rmotd`), use that tool — never a host agent's built-in web search or page-fetch tool (e.g. Claude Code's `WebSearch` / `WebFetch`, or the equivalent on any other agent platform this plugin runs on) as a substitute. This holds even when the relevant `prioris-mcp` tool is unavailable, errors, or seems insufficient: say so plainly and stop, or ask the user how to proceed — do not fall back to a general web search/fetch for that same lookup, and do not answer from memory. The rationale is caching and provenance: anything written to `.prioris/` must be traceable to a `prioris-mcp` call.

This constraint is scoped to what `prioris-mcp` actually covers (paper/prior-art search, fetch, and metadata). Nothing here restricts general web search or fetch for other needs outside that scope — e.g. looking up an unrelated fact, checking a library's docs, or browsing a non-paper URL the user shares. Reach for `prioris-mcp` first whenever the task is a paper/prior-art lookup; use general web tools freely otherwise.
