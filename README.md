# prioris

[![pytest](https://github.com/anirbanbasu/prioris/actions/workflows/uv-pytest-coverage.yml/badge.svg)](https://github.com/anirbanbasu/prioris/actions/workflows/uv-pytest-coverage.yml)

Search, fetch, and discuss prior art against the ideas you're working on. Deliberately scoped to **literature review and discussion only**; it will _**not**_ draft, outline, or write any part of a manuscript, that you may need to create, for you.

## Why

Existing research-assistant plugins tend to bundle discovery, writing, and review into one large pipeline, often leaving you - the researcher - as a bystander while a draft gets generated on your behalf. This is precisely why `prioris` is built to be an assistant, not an author: it helps you find relevant prior art, read and understand a paper in relation to your own work, and jog your memory about papers you've already read and discussed. However, it will not draft, outline, or write any part of a manuscript for you. The actual research and the actual writing is your responsibility.

Discussion notes, quick-read sections, and quiz questions are all saved to persistent, taggable, per-paper storage via `prioris-mcp`'s `NotesBackend`, so your reading record accumulates across papers over time. Cross-paper recall already works today — `reading-log` searches your notes across every paper you've covered, and `quiz-me`'s review mode runs spaced repetition across everything you've quizzed, not just one paper. Deeper cross-paper synthesis, backed by vector and graph indices over those same notes, is planned for a future version.

If you're running against a smaller open-weight model, you may still find it helpful to clear the context window or start a new agentic session between papers to keep a single discussion focused. Context window sizes less than 128K tokens are not recommended for this plugin, as they will not allow you to discuss a paper in depth and will very quickly be vulnerable to context rot and information loss.

## How it works

- Papers are found and fetched via a companion MCP server (the [`prioris-mcp`](https://github.com/anirbanbasu/prioris-mcp)) — arXiv (PDF-preferred, HTML fallback), Europe PMC (JATS XML), and a local PDF you already have on disk — not generic web search, so it behaves the same whether Claude Code is pointed at Anthropic's models or a local model.
- Reference a local PDF directly with `@file` (e.g. `@paper.pdf`) instead of searching — `discuss`, `quick-read`, and `quiz-me` all upload it via the same chunked-upload flow and hand it to `document-reader` for fetching/parsing; see `shared/local-file-handling.md` for why the upload always re-runs (identity is a content hash minted server-side) even though `prioris-mcp`'s own storage means it's never redundantly re-parsed.
- Paper content and notes both live server-side in `prioris-mcp` — its `StorageBackend` (fetched content) and `NotesBackend` (your notes: discussion synthesis, quick-read sections, quiz questions and recaps), each independently searchable and, for notes, taggable. Nothing under `.prioris/` is a durable copy of either any more; see `shared/data-layout.md` for the small amount that remains (a session-local metadata cache, and `quiz-me`'s local spaced-repetition schedule).
- A fetched paper is never re-fetched redundantly: `prioris-mcp`'s own storage already reuses a prior fetch, and an unversioned arXiv id always resolves to its current latest version server-side, so a revised paper is picked up automatically on the next fetch — there's nothing to force client-side any more.
- A shared `document-reader` subagent mediates every full-text touch across `discuss`/`quick-read`/`quiz-me`, so raw paper text stays out of the main conversation — only distilled digests, answers, and section bodies come back.
- Cross-paper recall already works today through `NotesBackend`'s search and tagging — `reading-log` and `quiz-me`'s review mode both span every paper you've noted, not just one at a time. No vector or graph index yet, though: deeper cross-paper synthesis built on top of those same notes is planned for a future version.
- Each capability is its own skill under `skills/<name>/SKILL.md` (the official Claude Code plugin layout) — no separate `commands/` directory. A skill's folder name is both its auto-trigger unit and its explicit slash-invocation name.

## Commands

Each skill below is auto-triggered by Claude when relevant, and also explicitly invocable:

- `/prioris:discuss [paper id, DOI, search query, or @file]` — search, fetch, and discuss papers, typically one at a time, against your working ideas; records topic-tagged discussion notes.
- `/prioris:quick-read [paper id, DOI, search query, or @file]` — six atomic notes from a paper's full text: background and research problem, key assumptions, methodology, results and analyses, documented shortcomings, and takeaways and future avenues.
- `/prioris:quiz-me [paper id or @file]` — quiz yourself on a paper (named-paper mode), grounded only in its actual text; or run a spaced-repetition review session over whatever's due across every paper already quizzed (review mode, no paper named).
- `/prioris:reading-log [provider/ids/date range/keywords]` — recap or search your recorded notes.
- `/prioris:manage-notes` — list, search, tag, and delete your notes; also supports manual note creation.
- `/prioris:vault-export [vault path]` — batch-export notes to an external Obsidian-style Markdown vault.
- `/prioris:rmotd [category] [n]` — abstracts-only digest (default 7, keep within 5–10) of recent items in one or more categories. No full-text fetch.
- `/prioris:manage-storage` — list and delete what's been fetched on the `prioris-mcp` server's content cache (a separate store from your notes).

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

The notes-backed skills above (`discuss`, `quick-read`, `quiz-me`, `reading-log`, `manage-notes`, `vault-export`) require a `prioris-mcp` build that includes `NotesBackend` (`research_notes_create/read/update/delete/search`, and the `notes://{id}/export` resource) — not yet in a tagged `prioris-mcp` release as of this plugin version; run `just update-mcp` once that support lands upstream.

This plugin bundles a `.mcp.json` that launches it via `uv run --project ${CLAUDE_PLUGIN_ROOT} prioris-mcp`, using the local, version-pinned environment defined by the repo's own `pyproject.toml`/`uv.lock` (currently tracking `prioris-mcp`'s git `master` branch, pinned to whatever commit was last locked — see "Local development" below). `uv run` creates that environment on first use, so there's still nothing to install ahead of time beyond `uv` itself on your `PATH`.

## Scope

This plugin will not draft, outline, or write manuscript prose. If asked to write a paper, it declines and points elsewhere.

## License

MIT — see [LICENSE](LICENSE).
