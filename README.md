# prioris

Search, fetch, and discuss prior art — one at a time — against the ideas you're working on. Deliberately scoped to **literature review and discussion only**; it will not draft, outline, or write any part of a manuscript for you.

## Why

Existing research-assistant plugins tend to bundle discovery, writing, and review into one large pipeline. `prioris` does one thing: help you actually understand and think about a paper in relation to your own work, one paper at a time, without blowing out the context window on a whole corpus.

## How it works

- Papers are found and fetched via a companion MCP server (HTML-preferred, PDF fallback), not generic web search — so it behaves the same whether Claude Code is pointed at Anthropic's models or a local model.
- Cached paper content and discussion notes are stored as plain markdown with YAML frontmatter under `.prioris/` in your project — human-readable, git-diffable, no database. `.prioris/papers/` is regenerable cache; `.prioris/discussions/` is your actual notes and should be versioned.
- No vector index, graph index, or multi-paper context loading in this version — cross-paper synthesis is a deliberately deferred feature, to be built later on top of the same markdown store.
- Each capability is its own skill under `skills/<name>/SKILL.md` (the official Claude Code plugin layout) — no separate `commands/` directory. A skill's folder name is both its auto-trigger unit and its explicit slash-invocation name.

## Commands

Each skill below is auto-triggered by Claude when relevant, and also explicitly invocable:

- `/prioris:discuss [paper id, URL, or search query]` — search, fetch, and discuss one paper at a time against your working ideas.
- `/prioris:quiz-me [paper id]` — quiz yourself on a paper already opened (or named), grounded only in its actual text.
- `/prioris:rmotd [category] [n]` — abstracts-only digest (default 7, keep within 5–10) of recent items in one or more categories. No full-text fetch.

## Install

```
/plugin marketplace add anirbanbasu/prioris
/plugin install prioris
```

## Local development

Test directly from a local clone or working copy, without publishing to GitHub first:

```
claude --plugin-dir /path/to/prioris
```

This loads the plugin for the current session only — use it to iterate on `skills/*/SKILL.md` before pushing and publishing via a marketplace. Multiple `--plugin-dir` flags can be given at once if you're testing alongside other local plugins.

## Requires

The `prioris-mcp` server (separate project, not yet published) exposing `search_papers`, `fetch_paper`, and (for `rmotd`) `list_recent` tools. Until that's available, install manually and point `.mcp.json` at your local build.

## Scope

This plugin will not draft, outline, or write manuscript prose. If asked to write a paper, it declines and points elsewhere.

## License

MIT — see [LICENSE](LICENSE).
