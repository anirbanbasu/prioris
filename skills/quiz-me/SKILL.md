---
name: quiz-me
description: "Quiz the user on a paper already opened in this conversation (or a cached one), using only that paper's actual content. Triggers: quiz me, test my understanding, ask me about this paper, check if I understood this paper."
metadata:
  version: "0.1.0"
  status: active
  task_type: open-ended
---

# Quiz Me

See `../../shared/scope.md` for the scope boundary and tool constraint shared by every skill in this plugin. This skill reuses the existing cache — no MCP tool beyond the fetch/parse pair (via `discuss`) is required.

## Workflow

1. Identify the target paper — use whichever one is already in context if unambiguous; otherwise ask which cached paper (see `.prioris/papers/<provider>/`), or run `discuss`'s Search → Fetch steps first if it isn't cached yet.
2. Generate questions grounded only in the cached paper's actual text — mix recall (what was measured/reported), comprehension (why the method works, what the mechanism is), and application (how this would apply in a different setting). Do not invent facts the paper doesn't contain.
3. Ask one question at a time; wait for the user's answer before revealing the correct answer or moving to the next question.
4. After each answer, give brief feedback — correct / partially correct / incorrect — pointing at the relevant part of the paper rather than a full re-explanation, unless asked for more.
5. At the end, summarize which concepts the user handled well vs. struggled with, and append a short "Quiz notes" entry to `.prioris/discussions/<provider>/<identifier>.md` (concepts to revisit) rather than a full transcript. Ask before overwriting a prior quiz-notes entry for that paper.

This skill keeps the same out-of-scope boundary as the rest of the plugin: it produces questions and feedback, never drafted prose.

## Argument handling

If invoked with `$ARGUMENTS` naming a paper id, title, or URL, use that paper — fetching it first via `discuss`'s flow if it isn't cached yet. A title isn't a fetchable identifier: run it through `discuss`'s Search step (`research_arxiv_search` / `research_europepmc_search`) to find the paper first. A URL isn't accepted by any `prioris-mcp` tool either: see `../../shared/url-handling.md` for how to extract the canonical identifier before fetching. Otherwise use whichever paper is already in context, or ask which one.
