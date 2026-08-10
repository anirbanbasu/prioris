# Shared: Notes Model — Tags, Find-or-Create, and the AskUserQuestion Pattern

Referenced by `discuss`, `quick-read`, `quiz-me`, `reading-log`, `manage-storage`, `manage-notes`, and `vault-export`. See `mcp-contracts.md#notes` for the `research_notes_*` tool contracts this doc assumes, and `data-layout.md` for what (little) still lives under `.prioris/` now that notes themselves are server-side.

## No local persistence of paper content or notes

Per [anirbanbasu/prioris#1](https://github.com/anirbanbasu/prioris/issues/1), `.prioris/` is not a durable store for paper content or notes any more — everything durable lives in `prioris-mcp`'s own `StorageBackend` (fetched content) and `NotesBackend` (notes). What remains under `.prioris/` is documented in `data-layout.md`: ephemeral scratch, a gitignored metadata cache (`shared/scripts/metadata_cache.py`), and `quiz-me`'s versioned local review schedule (`shared/scripts/review_schedule.py`) — the one piece of state that genuinely has nowhere else to live, see "Why review scheduling isn't in `metadata`" below.

## Tagging convention

Every note this plugin creates carries at least two tags, set only at `research_notes_create` time:

- A **project tag** — `NotesBackend` is one global store per `prioris-mcp` instance, not project-scoped, so this is how the plugin recovers "notes for this project" via `research_notes_search`'s `tags_all` filter. Compute it once per session via `uv run --project <plugin root> python shared/scripts/project_tag.py` and reuse that value for the rest of the session rather than re-deriving it per note.
- A **skill tag** — `skill:discuss`, `skill:quick-read`, or `skill:quiz-me` (`manage-notes`' manual-creation path uses whichever is most appropriate to the note's purpose, or omits it for a genuinely freeform note).

Plus, depending on the skill (see each `SKILL.md`'s Record/Generate step): `quick-read` adds one `section:<name>` tag (one of the six fixed section names); `quiz-me` adds `type:question` or `type:recap`; `discuss` adds `topic:<slug>`.

**Tags are immutable after creation from every skill except `manage-notes`.** `discuss`/`quick-read`/`quiz-me` never pass `tags` to `research_notes_update`. This matters because `tags_all`/`tags_any`/`tags_exclude` are the plugin's only way to scope a search (by project, by skill, by section/topic/question type), and a skill silently retagging a note out from under another skill's search would break that silently.

## The find-or-create pattern

Used by `discuss`'s Record step (per-topic) and `manage-notes`' tag-edit/delete flows (disambiguating an arbitrary note). **Tags alone cannot reliably pick a single existing note** — two notes can share every tag a search could reasonably filter on — so a skill with more than one candidate must always ask the user, never guess from tag closeness:

1. `research_notes_search(provider, canonical_identifier, tags_all=[<project_tag>, <skill_tag>, ...])`.
2. **Zero results** → create directly (`research_notes_create(...)`), no question asked — there's nothing to disambiguate.
3. **One or more results** → pipe the JSON `notes` array into `uv run --project <plugin root> python shared/scripts/format_note_choices.py` to get deterministic `{"id", "label"}` choices, then present them via `AskUserQuestion` alongside a "start new" option (an LLM-suggested slug/topic name is fine for *this* option's label, since it's proposing something new, not describing an existing note whose label must stay stable across sessions).
4. **Picked existing** → `research_notes_update(note_id, text=...)`, tags untouched. **Picked "start new"** → `research_notes_create(..., tags=[...])`.

Some notes are deterministic one-per-paper and skip this disambiguation entirely: `quick-read`'s six `section:<name>` notes and `quiz-me`'s one `type:recap` note both have a tag combination that can only ever match zero or one note, so step 3's `AskUserQuestion` never applies to them — a search hit means "update this one," full stop.

## Why review scheduling isn't in `NotesBackend`'s `metadata`

`metadata` is explicitly caller-owned, opaque, and **not filterable or searchable** by design (`mcp-contracts.md#notes`) — a key that turns out to matter enough to filter/search by should graduate to a real column, not stay in the opaque bag. "Every question ordered by how overdue it is, across however many papers" is exactly that kind of query, and the server has no way to do it over `metadata`. So `quiz-me`'s `times_asked`/`last_result`/`last_asked_at`/`level` live **only** in the local `.prioris/.review/schedule.json` (`shared/scripts/review_schedule.py`), keyed by `note_id` — never duplicated into the note's own `metadata`, avoiding a second copy to keep in sync. The `research_notes_delete` `PostToolUse` hook (`../hooks/hooks.json`) prunes a question's schedule entry once its note is gone, since deletion (via `manage-notes`) is the only event nothing else would clean this up after.
