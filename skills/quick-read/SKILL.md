---
name: quick-read
description: "Produce a structured, one-shot summary of a named paper's full text — research gap/questions, compressed background, key assumptions, findings, conclusions, shortcomings, and future directions. Triggers: quick read, quick-read, summarize this paper, tl;dr this paper, quick summary of, executive summary of this paper."
metadata:
  version: "0.1.0"
  status: active
  task_type: open-ended
---

# Quick Read

See `../../shared/scope.md` for the scope boundary and tool constraint, `../../shared/data-layout.md` for providers and the `.prioris/` layout/frontmatter schema, `../../shared/mcp-contracts.md` for the core MCP tool contracts, `../../shared/local-file-handling.md` for the `@file` workflow, and `../../shared/context-hygiene.md` for when to nudge the user to clear context — all shared by every skill in this plugin.

## Scope

A fast, structured single-pass summary of one paper's full text — not a discussion, not a quiz, and not a substitute for `discuss` when the user wants to dig into a paper against their own idea. Like the rest of the plugin, it produces a summary only, grounded in the paper's actual content — never drafted manuscript prose.

## Workflow

1. **Search/Select** — identical to `discuss`'s Search and Select steps: pick the provider from the subject matter (biomedical → `research_europepmc_search`, everything else → `research_arxiv_search`; search both and merge if genuinely ambiguous). If handed a bare DOI or an identifier of unclear provenance, call `research_resolve_identifier` first. If handed a title or search query, run the search and present a short ranked list (provider, title, authors, year, one-line abstract snippet); confirm with the user which paper unless one is already named unambiguously. Do not fetch full text yet. **If handed a local file (e.g. via `@file`) instead, skip straight to Fetch's `localfile` branch** — there's nothing to search or select.
2. **Check for a cached quick read** — for `arxiv`/`europepmc`, the identifier is already known at this point, so check `.prioris/discussions/<provider>/<identifier>.md` before touching the MCP server at all. If it already has a "Quick read" section, skip straight to Present (step 5) with that section's content — no Fetch, no Summarize, no MCP call, no Record. Skip this short-circuit, and run the full workflow instead, if the user is explicitly asking to redo, regenerate, refresh, or refetch the summary. (`localfile` identity isn't known until the file is re-hashed in Fetch, so its equivalent check happens there instead.)
3. **Fetch** — check `.prioris/papers/<provider>/<identifier>.md` first; reuse a cached copy instead of calling the MCP server again — unless the user explicitly asked to refetch or get the latest version, per `../../shared/data-layout.md#forcing-a-refetch`, in which case fetch fresh below and overwrite the cache entry. Otherwise fetch and parse per provider, exactly as in `discuss`'s Fetch step (arXiv: `research_arxiv_fetch_full_text` then `research_arxiv_parse_full_text`, PDF preferred, HTML on retry; Europe PMC: `research_europepmc_fetch_full_text` then `research_europepmc_parse_full_text`, XML only; local file: follow `../../shared/local-file-handling.md` in full — the cache check there comes *after* fetching, since identity isn't known until the file is re-hashed. Once the `id` comes back, apply step 2's check here too: if `.prioris/discussions/localfile/<id>.md` already has a "Quick read" section and this isn't an explicit redo/refetch request, skip straight to Present with it) — `parse_full_text` is paginated, so loop on `has_more` per `../../shared/mcp-contracts.md#paging-through-full-text` to collect the complete text — then write the concatenated markdown plus frontmatter (including `source_path` for `localfile`) to `.prioris/papers/<provider>/<identifier>.md`.
4. **Summarize** — read the *one* cached paper into context and produce a structured summary grounded only in its actual text, under these headers, in this order:
   - **Research gap / question(s)** — what open problem or unanswered question motivates the work.
   - **Background** (compressed) — how existing literature falls short of addressing that gap, briefly.
   - **Key assumptions** — the premises the paper's method or argument depends on.
   - **Findings** — what was measured, observed, or shown.
   - **Conclusions** — what the authors claim follows from the findings.
   - **Shortcomings** — limitations the paper itself acknowledges, or that are evident from its stated scope/method.
   - **Future directions** — what the paper suggests as next steps or open questions.

   Do not invent facts the paper doesn't contain. If a section genuinely doesn't apply (e.g. the paper states no future directions), say so briefly rather than fabricating content.
5. **Present** — show the summary in the conversation, whether freshly generated or read back from an existing "Quick read" section per step 2/3.
6. **Record** — skip this step entirely if step 2/3 short-circuited to a cached section; it's already recorded. Otherwise write a `## Quick read` section using the same seven headers, and set `read_at` if it isn't already set. Do this automatically — never ask the user whether to save it first. Use `../../shared/scripts/update_notes_section.py` (see `../../shared/scripts/README.md`) to write it: pass the summary as the content file, `"## Quick read"` as the section header, and (if `read_at` isn't already set) `read_at` — plus the rest of the frontmatter (`../../shared/data-layout.md`'s schema) on a first write — via `--frontmatter`. This replaces just that section in place if one already exists (e.g. from an explicit redo) and leaves any `Discussion`/`Quiz notes` section from another skill untouched, rather than risking a hand-edit clobbering it.
7. **Check in on context** — per `../../shared/context-hygiene.md`, if this conversation has been running long, close with a brief, polite nudge to clear context before the next paper.

## Argument handling

If invoked with `$ARGUMENTS` naming a paper id, title, URL, or local file path, use it to skip straight to the Search/Select step. If it's a URL, see `../../shared/url-handling.md` for how to extract the canonical identifier first. If it's a local file path (e.g. `@file`), see `../../shared/local-file-handling.md` instead — it's fetched directly, never searched or resolved. Otherwise ask which paper to summarize.
