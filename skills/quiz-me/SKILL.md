---
name: quiz-me
description: "Quiz the user on a paper already opened in this conversation (or a cached one), using only that paper's actual content. Triggers: quiz me, test my understanding, ask me about this paper, check if I understood this paper."
metadata:
  version: "0.1.0"
  status: active
  task_type: open-ended
---

# Quiz Me

See `../../shared/scope.md` for the scope boundary and tool constraint shared by every skill in this plugin, and `../../shared/data-layout.md` for the `.prioris/` layout and frontmatter (including the `source_path` field a local file's cache entry carries). This skill reuses the existing cache — no MCP tool beyond the fetch/parse pair (via `discuss`) is required, and that holds for local files too: `quiz-me` never calls `research_localfile_fetch_full_text` itself (see Argument handling below).

## Workflow

1. Identify the target paper explicitly before generating any questions — never silently infer it from whatever happens to be in conversation context, since a long-running session can span several papers and a fresh session (per the plugin's recommended practice of clearing context between papers) may have none. If `$ARGUMENTS` names one, resolve it per Argument handling below. Otherwise, state the paper (title and identifier) you intend to quiz and get explicit confirmation before proceeding — if there's more than one plausible candidate, or none, list the cached options under `.prioris/papers/<provider>/` and ask the user to pick, or run `discuss`'s Search → Fetch steps first if it isn't cached yet.
2. Generate questions grounded only in the cached paper's actual text — mix recall (what was measured/reported), comprehension (why the method works, what the mechanism is), and application (how this would apply in a different setting). Do not invent facts the paper doesn't contain.
3. Ask one question at a time; wait for the user's answer before revealing the correct answer or moving to the next question.
4. After each answer, give brief feedback — correct / partially correct / incorrect — pointing at the relevant part of the paper rather than a full re-explanation, unless asked for more.
5. At the end, summarize which concepts the user handled well vs. struggled with, and append a short "Quiz notes" entry to `.prioris/discussions/<provider>/<identifier>.md` (concepts to revisit) rather than a full transcript. Ask before overwriting a prior quiz-notes entry for that paper.

This skill keeps the same out-of-scope boundary as the rest of the plugin: it produces questions and feedback, never drafted prose.

## Argument handling

If invoked with `$ARGUMENTS` naming a paper id, title, or URL, use that paper — fetching it first via `discuss`'s flow if it isn't cached yet. A title isn't a fetchable identifier: run it through `discuss`'s Search step (`research_arxiv_search` / `research_europepmc_search`) to find the paper first. A URL isn't accepted by any `prioris-mcp` tool either: see `../../shared/url-handling.md` for how to extract the canonical identifier before fetching. Otherwise follow step 1 above: confirm the paper explicitly rather than assuming one from context.

If `$ARGUMENTS` (or the user) instead names a local file directly (e.g. via `@file`), resolve it purely by inspection of the local cache — never call `research_localfile_fetch_full_text` from within `quiz-me`. Look for a `.prioris/papers/localfile/*.md` file whose frontmatter `source_path` matches the given path exactly. If one matches, quiz from it as usual. If none does, the file hasn't been fetched (and hashed/cached) yet — tell the user to run `discuss` or `quick-read` on it first, then retry, rather than fetching it yourself.
