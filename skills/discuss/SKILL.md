---
name: discuss
description: "Search for, fetch, and discuss one academic paper (or other prior art) against your own research ideas — one item at a time, via arXiv or Europe PMC. Persists discussion notes server-side via prioris-mcp's NotesBackend, tagged per project and topic — no local mirror of paper content or notes. Triggers: discuss this paper, find papers about, what does this paper say about, how does this relate to my idea, literature review, related work, prior art. Out of scope: does NOT draft, outline, or write any part of a manuscript — for that, use a different tool."
metadata:
  version: "0.2.0"
  status: active
  task_type: open-ended
---

# Discuss

See `../../shared/scope.md` for the scope boundary and tool constraint, `../../shared/data-layout.md` for providers and what little remains under `.prioris/`, `../../shared/mcp-contracts.md` for the core MCP tool contracts (including `#notes`), `../../shared/notes-model.md` for the tag scheme and find-or-create pattern used in Record below, `../../shared/local-file-handling.md` for the `@file` workflow, and `../../shared/context-hygiene.md` for when to nudge the user to clear context — all shared by every skill in this plugin.

## Why one paper at a time

Holding many full papers in context at once degrades comparison quality and burns the context window fast — a single 30-page paper is already roughly 15-25K tokens. This skill deliberately works on one paper at a time, and even the one paper it works on is never loaded whole into this conversation: `../../agents/document-reader.md` mediates every full-text touch, returning only what a given step actually needs. Cross-paper synthesis is a deferred feature — `NotesBackend`'s notes have exactly one primary document each, no cross-document relations yet.

## Workflow

1. **Search**
   - **Local search first** — for a search-like query (a topic, title, or keyword search — not a bare identifier/DOI/URL), call `research_search_fetched(query)` before touching any provider (contract in `../../shared/mcp-contracts.md`) — scoped to a specific `provider` only if the user's query already named one. This is read-only over content already fetched *and* parsed on the server and never triggers a fetch itself.
     - **Matches found**: for each distinct `(provider, identifier)`, enrich it with title/authors via `uv run --project <plugin root> python ../../shared/scripts/metadata_cache.py read <provider> <identifier>` if a cache entry exists (fall back to the bare identifier plus the match's `snippet` otherwise — e.g. the content was fetched by a different client; for `localfile` matches, prefer the frontmatter-equivalent `source_path` you tracked this session over a blank title if you have it). Present these clearly labeled as already in local research, distinct from a fresh provider search. If the user picks one directly, it's already fully searchable server-side — skip straight to Discuss (step 4), no Fetch needed. Otherwise ask whether to also search arXiv/Europe PMC to expand beyond what's already fetched, and only continue to provider search below if they say yes.
     - **No matches**: continue straight to provider search below without asking — there's nothing to show yet.
   - **Provider search** — once the user agrees to expand beyond local matches, first ask via `AskUserQuestion` which of arXiv / Europe PMC / both to search, rather than silently picking by subject matter as before. Then, per chosen provider, come up with up to 3 semantically distinct query variations suited to that provider's own query syntax and run them concurrently — up to 3 calls per provider (up to 6 total if both were chosen); each provider paces its own calls server-side, so this is safe. Merge results across variations and providers, de-duplicating by `(provider, identifier)`, flagging any entry that already appeared among the local matches above. If the user instead handed a bare DOI or an identifier of unclear provenance, skip both local and provider search entirely and call `research_resolve_identifier` first — see "Argument handling" below if what you have is a URL rather than a bare id/DOI. Present a short ranked list (provider, title, authors, year, one-line abstract snippet). Do not fetch full text yet.

   **If the user instead handed you a local file (e.g. via `@file`), skip Search (both local and provider) and Select entirely** — there's nothing to search, go straight to Fetch's `localfile` branch below.
2. **Select** — confirm with the user which single paper to open, unless they've already named one directly.
3. **Fetch** — dispatch `../../agents/document-reader.md` with the resolved `(provider, identifier[, format])`, asking it to fetch/parse and return only a light digest: title, authors, abstract, and a section-heading outline. Hold only that digest in this conversation. There is nothing to cache or force-refetch on this side any more: the server's own storage already reuses a prior fetch, and an unversioned arXiv id always resolves to its current latest version server-side, so a revised paper is picked up automatically on the very next fetch.
4. **Discuss** — hold only the digest from Fetch in context, and discuss it against whatever idea or question the user brings: its claims, method, evidence, limitations, and how it relates to the user's stated idea. For each specific sub-question that needs the paper's actual wording (a number, a quoted claim, a method detail), dispatch `document-reader` again with that precise question — only its distilled answer returns here. Reference prior discussion notes via `research_notes_search` (see Record below) rather than re-reading full text for ground already covered. Do not pull other papers' full text into this step.
5. **Record** — after a substantive discussion, write a concise synthesis (what the paper says, what was concluded, open questions) as a note. Do this automatically — never ask the user whether to save it first. Follow `../../shared/notes-model.md`'s find-or-create pattern, scoped to this skill:
   1. `research_notes_search(provider=<p>, canonical_identifier=<id>, tags_all=[<project_tag>, "skill:discuss"])` (compute `<project_tag>` once per session via `shared/scripts/project_tag.py`, reuse it for the rest of the session).
   2. No results → `research_notes_create(provider=<p>, identifier=<id>, format=<f, or omitted for a note predating any fetch>, text=<synthesis>, tags=[<project_tag>, "skill:discuss", "topic:<llm-suggested-slug>"])` — nothing to disambiguate, no question asked.
   3. One or more results → run them through `shared/scripts/format_note_choices.py` and present the resulting labels via `AskUserQuestion`, plus a "start a new topic: `<llm-suggested-slug>`" option. With more existing topics than fit (the script already caps at 4), rely on `AskUserQuestion`'s auto-added "Other" as the escape hatch.
   4. Picked an existing topic → `research_notes_update(note_id=<id>, text=<merged/extended synthesis>)`, tags untouched. Picked "new topic" → `research_notes_create(..., tags=[<project_tag>, "skill:discuss", "topic:<slug>"])`.
6. **Check in on context** — per `../../shared/context-hygiene.md`, if this conversation has been running long, close with a brief, polite nudge to clear context before the next paper.

## Argument handling

If invoked with `$ARGUMENTS` containing a paper identifier, URL, search query, or local file path (e.g. `@file`), use it to skip straight to the Search/Fetch step. Otherwise ask what the user is looking for.

If `$ARGUMENTS` (or the user) hands you a URL, see `../../shared/url-handling.md` for how to extract the canonical identifier before calling anything — no `prioris-mcp` tool accepts a raw URL as input. If instead you're handed a local file path, see `../../shared/local-file-handling.md` for how to read and encode it and for the fetch sequence — a local file is not searched or resolved, it's uploaded directly, and the resulting `id` is what you hand `document-reader` in Fetch.
