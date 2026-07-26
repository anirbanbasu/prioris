# Shared: Scope, Data Layout, and Core MCP Contracts

Referenced by every skill in this plugin (`../skills/discuss`, `../skills/quiz-me`, `../skills/rmotd`). Keep skill-specific behavior in each SKILL.md and only the shared parts here.

## Scope (applies to every skill in this plugin)

This plugin finds, reads, and discusses prior art — academic papers today, other sources later — one item at a time. No skill in this plugin drafts, outlines, or writes any part of a manuscript. If asked to write or draft paper content, decline and redirect toward discussion instead.

## Data layout

All state lives under `.prioris/` in the current working directory, as plain markdown with YAML frontmatter — human-readable, git-diffable, no database:

- `.prioris/papers/<paper-id>.md` — cached, cleaned paper content (HTML-preferred extraction, PDF fallback). Regenerable; safe to `.gitignore`.
- `.prioris/discussions/<paper-id>.md` — notes and synthesis from past discussions and quizzes on this paper. Source of truth; should be versioned.

Frontmatter schema for both:

```yaml
---
paper_id: <arxiv id / doi / stable slug>
title: ...
authors: [...]
source_url: ...
fetched_at: <ISO 8601>
read_at: <ISO 8601, omitted if not yet discussed>
tags: [...]
---
```

## Core MCP dependency

Every skill here assumes a companion MCP server (the `prioris` server, a separate project) exposing at minimum:

- `search_papers(query, source?) -> [{paper_id, title, authors, year, venue, abstract, url}]`
- `fetch_paper(paper_id_or_url) -> {paper_id, cleaned_markdown, source_url, format}`

`rmotd` additionally needs `list_recent` (documented in its own SKILL.md).

If an expected tool isn't available in the current session, say so plainly and stop — do not guess at paper content from memory or fall back to general web search as a substitute.
