---
name: vault-export
description: "Batch-export notes to an external Obsidian-style Markdown vault via prioris-mcp's notes://{id}/export resource, translating each note's JSON frontmatter to YAML. Triggers: export my notes, export to Obsidian, export notes to vault, sync notes to my vault, dump notes as markdown files."
metadata:
  version: "0.1.0"
  status: active
  task_type: open-ended
---

# Vault Export

See `../../shared/mcp-contracts.md` for the `notes://{note_id}/export` resource's contract (`#notes`) and `../../shared/notes-model.md` for the tag scheme used in filtering below.

## Scope

Writes files *outside* `.prioris/` — this is user-directed output to a vault path the user provides, not plugin state, and the server itself never writes this to disk (`export` is a resource, not a tool). Never invoked automatically by another skill; always an explicit, user-initiated action.

## Workflow

1. Determine which notes to export — same filter language as `reading-log`/`manage-notes` (`research_notes_search`, project-scoped by default), or an explicit list of note ids the user already has.
2. Determine the destination vault path — ask if not given. Confirm the directory exists, or offer to create it, before writing anything (`../../shared/scripts/render_note_export.py` creates it automatically if missing, but say so to the user first rather than silently creating a new directory tree on their filesystem).
3. For each selected note id, read `notes://{note_id}/export`, pipe the resulting JSON into `uv run --project <plugin root> python ../../shared/scripts/render_note_export.py <vault path>`, which writes `<vault path>/<note id>.md` and prints the path it wrote.
4. Report how many notes were written and where. If a file already existed at a given path, `render_note_export.py` overwrote it (vault exports are idempotent snapshots, not append-merges) — say so rather than implying it was a fresh file.

## Argument handling

If `$ARGUMENTS` names a vault path and/or filter language, use it. Otherwise ask for the destination path first — nothing else can proceed without it — then ask which notes to export.
