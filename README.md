# prioris

Search, fetch, and discuss prior art — one at a time — against the ideas you're working on. Deliberately scoped to **literature review and discussion only**; it will _**not**_ draft, outline, or write any part of a manuscript, that you may need to create, for you.

## Why

Existing research-assistant plugins tend to bundle discovery, writing, and review into one large pipeline. `prioris` does one thing: help you actually understand and think about a paper in relation to your own work, one paper at a time, without blowing out the context window on a whole corpus.

The one paper at a time approach is deliberate: it forces you to engage with the paper's content, rather than just skim abstracts or rely on AI-generated summaries. As the discussion is saved to persistent storage, you should clear the context window or start a new agentic session when switching between papers. This is particularly helpful with context window sizes between 128K and 256K tokens, in open-weight models that you can run locally. Context window sizes less than 128K tokens are not recommended for this plugin, as they will not allow you to discuss a paper in depth.

## How it works

- Papers are found and fetched via a companion MCP server (the [`prioris-mcp`](https://github.com/anirbanbasu/prioris-mcp)) — arXiv (PDF-preferred, HTML fallback) and Europe PMC (JATS XML) — not generic web search, so it behaves the same whether Claude Code is pointed at Anthropic's models or a local model.
- Cached paper content and discussion notes are stored as plain markdown with YAML frontmatter under `.prioris/` in your project — human-readable, git-diffable, no database. `.prioris/papers/` is regenerable cache; `.prioris/discussions/` is your actual notes and should be versioned.
- No vector index, graph index, or multi-paper context loading in this version — cross-paper synthesis is a deliberately deferred feature, to be built later on top of the same markdown store.
- Each capability is its own skill under `skills/<name>/SKILL.md` (the official Claude Code plugin layout) — no separate `commands/` directory. A skill's folder name is both its auto-trigger unit and its explicit slash-invocation name.

## Commands

Each skill below is auto-triggered by Claude when relevant, and also explicitly invocable:

- `/prioris:discuss [paper id, DOI, or search query]` — search, fetch, and discuss one paper at a time against your working ideas.
- `/prioris:quick-read [paper id, DOI, or search query]` — one-shot structured summary of a paper's full text: research gap/questions, background, key assumptions, findings, conclusions, shortcomings, and future directions.
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

Every skill carries a lightweight `evals/evals.json` (prompts + verifiable expectations) alongside its `SKILL.md` — add one for any new skill so behavior can be checked before an edit ships, not just eyeballed.

## Requires

The [`prioris-mcp`](https://pypi.org/project/prioris-mcp/) server ([docs](https://docs-prioris-mcp.anirbanbasu.com/)), providing arXiv and Europe PMC search/fetch/parse tools plus identifier resolution — see `shared/mcp-contracts.md` for the full contract this plugin relies on.

This plugin bundles a `.mcp.json` that launches it via [`uvx`](https://docs.astral.sh/uv/guides/tools/), so there's nothing to install ahead of time — `uvx` fetches and runs `prioris-mcp` from PyPI on first use. You only need `uv` itself available on your `PATH`.

## Scope

This plugin will not draft, outline, or write manuscript prose. If asked to write a paper, it declines and points elsewhere.

## License

MIT — see [LICENSE](LICENSE).
