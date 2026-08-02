# prioris

[![pytest](https://github.com/anirbanbasu/prioris/actions/workflows/uv-pytest-coverage.yml/badge.svg)](https://github.com/anirbanbasu/prioris/actions/workflows/uv-pytest-coverage.yml)

Search, fetch, and discuss prior art — one at a time — against the ideas you're working on. Deliberately scoped to **literature review and discussion only**; it will _**not**_ draft, outline, or write any part of a manuscript, that you may need to create, for you.

## Why

Existing research-assistant plugins tend to bundle discovery, writing, and review into one large pipeline. `prioris` does one thing: help you actually understand and think about a paper in relation to your own work, one paper at a time, without blowing out the context window on a whole corpus.

The one paper at a time approach is deliberate: it forces you to engage with the paper's content, rather than just skim abstracts or rely on AI-generated summaries. As the discussion is saved to persistent storage, you should clear the context window or start a new agentic session when switching between papers. This is particularly helpful with context window sizes between 128K and 256K tokens, in open-weight models that you can run locally. Context window sizes less than 128K tokens are not recommended for this plugin, as they will not allow you to discuss a paper in depth.

## How it works

- Papers are found and fetched via a companion MCP server (the [`prioris-mcp`](https://github.com/anirbanbasu/prioris-mcp)) — arXiv (PDF-preferred, HTML fallback), Europe PMC (JATS XML), and a local PDF you already have on disk — not generic web search, so it behaves the same whether Claude Code is pointed at Anthropic's models or a local model.
- Reference a local PDF directly with `@file` (e.g. `@paper.pdf`) instead of searching — `discuss` and `quick-read` fetch and cache it the same way as an arXiv/Europe PMC paper; `quiz-me` and `reading-log` recognize it by that same path afterwards, without re-fetching.
- Cached paper content and discussion notes are stored as plain markdown with YAML frontmatter under `.prioris/` in your project — human-readable, git-diffable, no database. `.prioris/papers/` is regenerable cache; `.prioris/discussions/` is your actual notes and should be versioned.
- A cached paper is reused as-is by default and never silently re-fetched. Explicitly ask to refetch or "get the latest version" (e.g. after an arXiv revision) to bypass that cache for one call — supported by `discuss`, `quick-read`, and `quiz-me` (which defers to `discuss`'s fetch step); see `shared/data-layout.md` for the exact rules. This is separate from asking `quick-read` to just redo/regenerate its summary, which reuses the cached paper text and only bypasses the cached summary.
- No vector index, graph index, or multi-paper context loading in this version — cross-paper synthesis is a deliberately deferred feature, to be built later on top of the same markdown store.
- Each capability is its own skill under `skills/<name>/SKILL.md` (the official Claude Code plugin layout) — no separate `commands/` directory. A skill's folder name is both its auto-trigger unit and its explicit slash-invocation name.

## Commands

Each skill below is auto-triggered by Claude when relevant, and also explicitly invocable:

- `/prioris:discuss [paper id, DOI, search query, or @file]` — search, fetch, and discuss one paper at a time against your working ideas.
- `/prioris:quick-read [paper id, DOI, search query, or @file]` — one-shot structured summary of a paper's full text: research gap/questions, background, key assumptions, findings, conclusions, shortcomings, and future directions.
- `/prioris:quiz-me [paper id or @file]` — quiz yourself on a paper already opened (or named), grounded only in its actual text.
- `/prioris:reading-log [provider/ids/date range/keywords]` — recap already-cached discussions so you can pick up a prior thread; purely local, never fetches or searches.
- `/prioris:rmotd [category] [n]` — abstracts-only digest (default 7, keep within 5–10) of recent items in one or more categories. No full-text fetch.
- `/prioris:manage-storage` — list and delete what's been fetched on the `prioris-mcp` server itself (a separate cache from `.prioris/`), with an optional offer to clean up the matching local files too.

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

Run `just sync` once (or let the first `uv run` in `.mcp.json` do it lazily) to create the `.venv` this repo's `pyproject.toml` describes, which pins the companion `prioris-mcp` server and provides the interpreter for `shared/scripts/` (see `shared/scripts/README.md`). Because `uv.lock` pins an exact git commit rather than re-resolving `master` on every launch, `prioris-mcp` won't pick up new upstream commits automatically — run `just update-mcp` to re-pin to the latest commit when you want that.

Every skill carries a lightweight `evals/evals.json` (prompts + verifiable expectations) alongside its `SKILL.md` — add one for any new skill so behavior can be checked before an edit ships, not just eyeballed.

## Requires

The [`prioris-mcp`](https://pypi.org/project/prioris-mcp/) server ([docs](https://docs-prioris-mcp.anirbanbasu.com/)), providing arXiv and Europe PMC search/fetch/parse tools, identifier resolution, a local-filesystem fetch/parse pair for `@file`, and server-side storage list/delete tools — see `shared/mcp-contracts.md` and `shared/storage-management.md` for the full contracts this plugin relies on.

This plugin bundles a `.mcp.json` that launches it via `uv run --project ${CLAUDE_PLUGIN_ROOT} prioris-mcp`, using the local, version-pinned environment defined by the repo's own `pyproject.toml`/`uv.lock` (currently tracking `prioris-mcp`'s git `master` branch, pinned to whatever commit was last locked — see "Local development" below). `uv run` creates that environment on first use, so there's still nothing to install ahead of time beyond `uv` itself on your `PATH`.

## Scope

This plugin will not draft, outline, or write manuscript prose. If asked to write a paper, it declines and points elsewhere.

## License

MIT — see [LICENSE](LICENSE).
