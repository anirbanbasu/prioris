---
name: manage-storage
description: "Manage prioris-mcp's server-side storage — list what's been fetched and delete entries you no longer need. Triggers: manage storage, what's cached on the server, what's been fetched, clean up fetched papers, delete a cached PDF, free up disk space, prune old fetches, clear the prioris cache, remove this paper from storage. Distinct from your local .prioris/ notes: this manages the MCP server's own content cache, not this plugin's discussion notes — make sure to reach for this skill whenever the user asks about disk usage, stale downloads, or clearing prioris-mcp's cache specifically, even if they don't name research_list_fetched or research_delete_fetched directly. Out of scope: does NOT fetch, discuss, or summarize a paper — for that, use discuss or quick-read."
metadata:
  version: "0.1.0"
  status: active
  task_type: open-ended
---

# Manage Storage

See `../../shared/scope.md` for the plugin-wide tool constraint, `../../shared/storage-management.md` for the `research_list_fetched`/`research_delete_fetched` contracts and — importantly — the distinction between the server's own storage and this plugin's `.prioris/` cache, and `../../shared/data-layout.md` for the `.prioris/` layout referenced in the cleanup step below.

## Scope

This skill manages `prioris-mcp`'s own server-side content cache (raw fetched PDFs/XML plus their parsed Markdown) — not this plugin's `.prioris/papers/` or `.prioris/discussions/` files. It never fetches, parses, or discusses a paper itself; for that, use `discuss` or `quick-read`. Read `../../shared/storage-management.md` before doing anything here — conflating the two caches is the single easiest way to alarm a user into thinking a storage cleanup deleted their notes, when it didn't.

## Workflow

1. **List** — call `research_list_fetched(provider, format)`, scoped to whatever the user asked about (all providers/formats if unspecified). Present entries grouped by `(provider, identifier)` rather than as a flat list of formats — a single paper is normally stored as two entries (e.g. `pdf` + `pdf-markdown`), and showing them as one row with both formats' size/date is easier to act on than showing the user two disconnected rows for "the same thing."
2. **Select** — work out exactly what the user wants removed: named identifier(s), an entire provider, an age/date cutoff ("clear anything older than 30 days" — convert relative phrasing to an absolute date using the current date), or everything. When an identifier is named, gather *every* entry matching it across all its formats (per `storage-management.md`) — deleting a paper means deleting all of its stored formats, not just whichever one happened to be listed first.
3. **Confirm** — list the exact `(provider, identifier, format)` entries about to be removed and get explicit confirmation before calling `research_delete_fetched`. This is destructive and the server has no undo; don't treat a vague "yeah clean some stuff up" as confirmation for a specific set — show the set first.
4. **Delete** — call `research_delete_fetched(entries=[...])`. Report `deleted` and `not_found` plainly; `not_found` isn't an error, it just means that entry was already gone.
5. **Offer local cleanup** — for each `(provider, identifier)` pair that was actually deleted, check whether `.prioris/papers/<provider>/<identifier>.md` exists locally. If it does, point it out and offer (don't do it silently or bundle it into the confirmation from step 3, since it's a separate decision about a separate cache) to remove that file too — with the server copy gone, it can't be regenerated without a fresh fetch. Separately check `.prioris/discussions/<provider>/<identifier>.md`: if that exists, call it out explicitly and default to recommending it stay — it holds the user's own synthesis and questions, which nothing about clearing server storage can reconstruct. Only remove it if the user explicitly says to, as its own separate confirmation.

## Argument handling

If invoked with `$ARGUMENTS` naming identifiers, a provider, or an age/date phrase (e.g. "delete arxiv 2401.12345v2", "clear everything older than 2 weeks", "what's stored for europepmc"), parse it into the targets/filters above and proceed. A bare "manage storage" / "what's cached" with nothing further means: run List (step 1) and stop there, waiting for the user to say what to do next — never delete anything without an explicit, confirmed target.
