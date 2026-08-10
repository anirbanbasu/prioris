---
name: quiz-me
description: "Quiz the user on a paper (named-paper mode), or run a spaced-repetition review session over whatever's due across every paper already quizzed (review mode) — both grounded only in each paper's actual content. Triggers: quiz me, test my understanding, ask me about this paper, check if I understood this paper, what's due for review, review me, spaced repetition, review my quiz questions."
metadata:
  version: "0.2.0"
  status: active
  task_type: open-ended
---

# Quiz Me

See `../../shared/scope.md` for the scope boundary and tool constraint, `../../shared/mcp-contracts.md` for the core MCP tool contracts (including `#notes`), `../../shared/notes-model.md` for the tag scheme and why review scheduling lives locally rather than in `metadata`, and `../../shared/context-hygiene.md` for when to nudge the user to clear context. Both modes below use `../../agents/document-reader.md` for the one-time question-bank generation and `../../shared/scripts/review_schedule.py` for all scheduling state.

## Two modes, one loop

Both modes share the same per-question loop: ask one question at a time, wait for the answer, give feedback pointing at the question's stored anchor as evidence, then record the result via `review_schedule.py record`. They differ only in how the *next question* is selected:

- **Named-paper mode** — trigger shape "quiz me on this paper" — quizzes one paper's question bank, in whatever order feels natural, generating the bank on first use.
- **Review mode** — trigger shape "what's due for review" (no paper named) — quizzes whatever's currently due, computed from `.prioris/.review/schedule.json`, potentially spanning several different papers in one session.

## Named-paper mode

1. Identify the target paper explicitly — never silently infer it from conversation context. If `$ARGUMENTS` names one, resolve it per Argument handling below. Otherwise state the candidate (title and identifier) and get explicit confirmation, or run `discuss`'s Search → Select steps first if it isn't established yet.
2. Check for an existing question bank: `research_notes_search(provider, canonical_identifier, tags_all=[<project_tag>, "skill:quiz-me", "type:question"])`.
   - Bank exists, and this isn't an explicit request to add/regenerate → reuse it, skip to step 4.
   - Otherwise → generate (step 3). If the user says the paper has since changed (e.g. a newer arXiv revision), treat that as an explicit regenerate request: there's no version field or force-refetch signal to detect this automatically, and anchors are exact-text quotes, so a revised paper can silently shift or remove the quoted passage and invalidate an old bank's anchors without the skill ever finding out on its own.
3. **Generate** — dispatch `document-reader` per its "A quiz question bank" scenario: a mixed set of recall/comprehension/application questions grounded only in the paper's actual text, each with one `Anchor`. For each returned question, `research_notes_create(provider, identifier, format, text=<question, plus enough of the expected answer to give feedback against>, anchors=[<anchor>], tags=[<project_tag>, "skill:quiz-me", "type:question"])`.
4. Ask one question at a time; wait for the user's answer before revealing the correct one or moving on.
5. After each answer, give brief feedback (correct / partially correct / incorrect) pointing at the question note's anchor rather than a full re-explanation. Record it: `uv run --project <plugin root> python ../../shared/scripts/review_schedule.py record <question note_id> <correct|partial|incorrect>`.
6. At the end, write/update the one `type:recap` note for this paper — deterministic, one per paper, no disambiguation needed: `research_notes_search(provider, canonical_identifier, tags_all=[<project_tag>, "skill:quiz-me", "type:recap"])`; update in place if found (`research_notes_update`), else `research_notes_create(..., tags=[<project_tag>, "skill:quiz-me", "type:recap"])`. Content: which concepts the user handled well vs. struggled with, not a full transcript.
7. **Check in on context** — per `../../shared/context-hygiene.md`.

## Review mode

1. `research_notes_search(tags_all=[<project_tag>, "skill:quiz-me", "type:question"])`, looping `offset`/`has_more` to collect every matching note id — project-scoped by default; an explicit "across all my projects" ask drops `<project_tag>` from `tags_all`.
2. `uv run --project <plugin root> python ../../shared/scripts/review_schedule.py due <id-1> <id-2> ...` — returns only the currently-due ids, most-overdue first. If none are due, say so plainly and stop (offer named-paper mode instead of inventing a review session).
3. Run steps 4-5 from Named-paper mode over the due questions in exactly that order — this can and normally will span several different papers in one session; that's the point of review mode. Skip step 6 (recap notes are per-paper and belong to named-paper mode).
4. **Check in on context** — per `../../shared/context-hygiene.md`.

## Argument handling

- **Named-paper mode** is triggered by `$ARGUMENTS` (or the user) naming a paper id, title, URL, or local file path — resolve exactly as `discuss`/`quick-read` do (search first if it's a title, `url-handling.md` if it's a URL, `local-file-handling.md` if it's a local path), then follow "Named-paper mode" above from step 1.
- **Review mode** is triggered by review-shaped language with no paper named ("what's due", "review me", "spaced repetition") — including a bare `quiz me`/`review me` with nothing else in `$ARGUMENTS` and no paper otherwise established in this conversation. If genuinely ambiguous (a paper *is* in recent context but the user's phrasing sounds review-shaped), ask which mode they mean rather than guessing.
