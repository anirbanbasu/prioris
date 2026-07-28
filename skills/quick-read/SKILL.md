---
name: quick-read
description: "Produce a structured, one-shot summary of a named paper's full text — research gap/questions, compressed background, key assumptions, findings, conclusions, shortcomings, and future directions. Triggers: quick read, quick-read, summarize this paper, tl;dr this paper, quick summary of, executive summary of this paper."
metadata:
  version: "0.1.0"
  status: active
  task_type: open-ended
---

# Quick Read

See `../../shared/data-layout.md` for the scope boundary, providers, `.prioris/` layout, frontmatter schema, core MCP tool contracts, and the tool constraint (`prioris-mcp` only for anything it covers — no built-in web search/fetch as a substitute) shared by every skill in this plugin.

## Scope

A fast, structured single-pass summary of one paper's full text — not a discussion, not a quiz, and not a substitute for `discuss` when the user wants to dig into a paper against their own idea. Like the rest of the plugin, it produces a summary only, grounded in the paper's actual content — never drafted manuscript prose.

## Workflow

1. **Search/Select** — identical to `discuss`'s Search and Select steps: pick the provider from the subject matter (biomedical → `research_europepmc_search`, everything else → `research_arxiv_search`; search both and merge if genuinely ambiguous). If handed a bare DOI or an identifier of unclear provenance, call `research_resolve_identifier` first. If handed a title or search query, run the search and present a short ranked list (provider, title, authors, year, one-line abstract snippet); confirm with the user which paper unless one is already named unambiguously. Do not fetch full text yet.
2. **Fetch** — check `.prioris/papers/<provider>/<identifier>.md` first; reuse a cached copy instead of calling the MCP server again. Otherwise fetch and parse per provider, exactly as in `discuss`'s Fetch step (arXiv: `research_arxiv_fetch_full_text` then `research_arxiv_parse_full_text`, PDF preferred, HTML on retry; Europe PMC: `research_europepmc_fetch_full_text` then `research_europepmc_parse_full_text`, XML only), then write the returned markdown plus frontmatter to `.prioris/papers/<provider>/<identifier>.md`.
3. **Summarize** — read the *one* cached paper into context and produce a structured summary grounded only in its actual text, under these headers, in this order:
   - **Research gap / question(s)** — what open problem or unanswered question motivates the work.
   - **Background** (compressed) — how existing literature falls short of addressing that gap, briefly.
   - **Key assumptions** — the premises the paper's method or argument depends on.
   - **Findings** — what was measured, observed, or shown.
   - **Conclusions** — what the authors claim follows from the findings.
   - **Shortcomings** — limitations the paper itself acknowledges, or that are evident from its stated scope/method.
   - **Future directions** — what the paper suggests as next steps or open questions.

   Do not invent facts the paper doesn't contain. If a section genuinely doesn't apply (e.g. the paper states no future directions), say so briefly rather than fabricating content.
4. **Present** — show the summary in the conversation.
5. **Record** — append or update a "Quick read" section in `.prioris/discussions/<provider>/<identifier>.md` using the same seven headers, and set `read_at` if it isn't already set. Ask before overwriting an existing quick-read entry for that paper rather than silently clobbering it.

## Argument handling

If invoked with `$ARGUMENTS` naming a paper id, title, or URL, use it to skip straight to the Search/Select step — same rules as `discuss`'s "Argument handling" section, including URL canonicalization (arXiv landing/PDF/HTML URLs, Europe PMC `/PMC<digits>` or `/article/{source}/{id}` URLs, and DOIs via `research_resolve_identifier`). Otherwise ask which paper to summarize.
