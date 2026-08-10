---
name: quick-read
description: "Produce six atomic, per-section notes from a named paper's full text — background and research problem, key assumptions, methodology, results and analyses, documented shortcomings, and takeaways and future avenues — each grounded strictly in the paper's own text, never opinion or prior discussion. Triggers: quick read, quick-read, summarize this paper, tl;dr this paper, quick summary of, executive summary of this paper."
metadata:
  version: "0.2.0"
  status: active
  task_type: open-ended
---

# Quick Read

See `../../shared/scope.md` for the scope boundary and tool constraint, `../../shared/data-layout.md` for providers and what little remains under `.prioris/`, `../../shared/mcp-contracts.md` for the core MCP tool contracts (including `#notes`), `../../shared/notes-model.md` for the tag scheme, `../../shared/local-file-handling.md` for the `@file` workflow, and `../../shared/context-hygiene.md` for when to nudge the user to clear context.

## Scope

A fast, structured summary of one paper's full text, as six independently-updatable notes — not a discussion, not a quiz, and not a substitute for `discuss` when the user wants to dig into a paper against their own idea. Every section is grounded strictly in the paper's own text — its authors' claims, methods, results, and stated limitations — never the model's own opinion and never anything drawn from a prior `discuss` session on the same paper; that separation is what keeps a quick-read note reusable as neutral source material for other skills.

## The six sections

Each is its own note, tagged `section:<name>` alongside `<project_tag>` and `skill:quick-read`:

- `section:background-and-research-problem` — the open problem/question motivating the work, and how existing literature falls short of addressing it.
- `section:key-assumptions` — the premises the paper's method or argument depends on.
- `section:methodology` — how the work was actually carried out.
- `section:results-and-analyses` — what was measured, observed, or shown.
- `section:documented-shortcomings` — limitations the paper itself acknowledges, or that are evident from its stated scope/method.
- `section:takeaways-and-future-avenues` — what the authors claim follows from the results, plus what they suggest as next steps.

## Workflow

1. **Search/Select** — identical to `discuss`'s Search and Select steps (including the provider-choice `AskUserQuestion` once expanding beyond local matches). **If handed a local file (e.g. via `@file`), skip straight to step 2** with the paper identified by its uploaded `id`.
2. **Per-section find-or-create** — for each of the six sections, search first: `research_notes_search(provider, canonical_identifier, tags_all=[<project_tag>, "skill:quick-read", "section:<name>"])`. A hit is reused as-is (this tag combination can only ever match zero or one note, so there's nothing to disambiguate) unless the user explicitly asked to redo/regenerate that section — collect the set of sections still missing (or explicitly requested to redo).
3. **Generate** — if any sections remain missing/requested, dispatch `../../agents/document-reader.md` once with the paper's `(provider, identifier[, format])` and the specific list of section names still needed, per its "One or more sections for `quick-read`" scenario. It returns one grounded Markdown body per requested section.
4. **Present** — show all six sections (reused plus freshly generated) under the headers above, in the order listed. If a section genuinely doesn't apply (e.g. the paper states no future directions), say so briefly rather than fabricating content.
5. **Record** — for a section generated because it was missing, `research_notes_create(provider, identifier, format, text=<section body>, tags=[<project_tag>, "skill:quick-read", "section:<name>"])`. For a section regenerated because the user explicitly asked to redo it, `research_notes_update(note_id=<existing section note's id>, text=<new body>)` instead — tags untouched, no disambiguation question, since this tag combination is already known to be unique per paper. Do this automatically for every freshly generated/regenerated section — never ask first.
6. **Check in on context** — per `../../shared/context-hygiene.md`, if this conversation has been running long, close with a brief, polite nudge to clear context before the next paper.

## Argument handling

If invoked with `$ARGUMENTS` naming a paper id, title, URL, or local file path, use it to skip straight to Search/Select. If it's a URL, see `../../shared/url-handling.md`. If it's a local file path, see `../../shared/local-file-handling.md`. A request naming one or more specific sections ("redo the methodology summary") narrows step 2's "missing or requested" set to just those, leaving the other five untouched if they already exist. Otherwise ask which paper to summarize.
