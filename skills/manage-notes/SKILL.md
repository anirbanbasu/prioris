---
name: manage-notes
description: "List, search, tag, and delete notes recorded by this plugin via prioris-mcp's NotesBackend — the administrative counterpart to reading-log's recall-only search. Also handles manual/freeform note creation. Triggers: manage notes, edit note tags, retag this note, delete this note, delete all notes for this paper, add a note, annotate this paper, clean up my notes, rename this topic."
metadata:
  version: "0.1.0"
  status: active
  task_type: open-ended
---

# Manage Notes

See `../../shared/scope.md` for the plugin-wide tool constraint, `../../shared/mcp-contracts.md` for `research_notes_*`'s contracts (`#notes`), and `../../shared/notes-model.md` for the tag scheme and find-or-create pattern this skill is the one exception to.

## Scope

The only skill in this plugin allowed to change an existing note's `tags` — `discuss`/`quick-read`/`quiz-me` each set tags once at creation and never touch them again (`../../shared/notes-model.md`). Also the only skill offering: search/listing beyond `reading-log`'s recall framing, deletion (single or bulk-by-paper), and manual/freeform note creation. Never fetches, parses, or discusses a paper — for that, use `discuss` or `quick-read`. Never touches `prioris-mcp`'s `StorageBackend` — for that, use `manage-storage`.

## Workflow

1. **List/Search** — `research_notes_search` with whatever filters the user gives (`provider`, `canonical_identifier`, `tags_all`/`tags_any`/`tags_exclude`, `keyword`, date range), project-scoped by default via `<project_tag>` (compute once per session via `../../shared/scripts/project_tag.py`), explicit opt-in for cross-project. Present each match's id, first line of its text, tags, and `updated_at`.
2. **Tag editing** — resolve the target note: if the user already gave an id, use it; otherwise search and disambiguate via `../../shared/scripts/format_note_choices.py` plus `AskUserQuestion`, exactly like `discuss`'s Record step. Show its current `tags`, get the exact new tag list from the user, confirm it, then `research_notes_update(note_id, tags=[...])`. This is one note at a time — never silently rename a tag across every note that happens to carry it.
3. **Delete** — confirm the exact note(s) (id plus first line of text) before calling `research_notes_delete(note_id)`. This is destructive with no server-side undo.
   - **Bulk-delete-by-paper** — gather every note for a `(provider, canonical_identifier)` via `research_notes_search` with no tag filter beyond the project scope (every skill's notes: quick-read sections, quiz questions and recap, discuss topics — a paper's full set can be a dozen+ rows). List the complete set, get one explicit confirmation covering all of it, then delete each. `../../hooks/hooks.json`'s `PostToolUse` hook prunes each deleted question's `.prioris/.review/schedule.json` entry automatically — nothing further to do here.
4. **Manual/freeform creation** — ask for the target `(provider, identifier[, format])` (resolve a URL/DOI via `../../shared/url-handling.md`/`research_resolve_identifier` first if needed), the note text, and any tags beyond the automatic `[<project_tag>]` this skill always adds too (for the same project-scoping reason every other skill's notes carry it) — then `research_notes_create(...)`.

## Argument handling

If `$ARGUMENTS` names a note id or clearly requests one of the actions above, go straight to it. Otherwise run List (step 1, unfiltered, project-scoped) and ask what to do next.
