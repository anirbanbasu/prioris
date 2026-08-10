# Shared: Bundled Scripts

Referenced by `local-file-handling.md`, `url-handling.md`, and the Record step of `discuss`, `quick-read`, and `quiz-me`. Each script below replaces a step that's mechanical — base64-encoding bytes, parsing a URL, merging one section into a YAML-frontmattered markdown file — and has exactly one correct answer, unlike the judgment calls (which provider, what to say, whether to discuss further) that stay as prose instructions. Re-deriving the equivalent shell/regex/YAML logic by hand every invocation risks the same categories of mistake each time: a platform-dependent shell flag, a slipped regex branch, a hand-edited YAML block that clobbers a sibling section. Running the same tested script instead makes the outcome deterministic.

## How to invoke them

It is imperative that any Python you run — a script in this directory, from any skill, or an ad hoc snippet you write yourself for a one-off check — always runs as `uv run python`, never bare `python` or `python3`, without exception. This isn't specific to the bundled scripts: the same rule applies to anything Python-shaped you decide to execute. A bare `python3` resolves to whatever interpreter happens to be on the host's `PATH`, which won't have the pinned dependencies these scripts rely on (e.g. PyYAML for `update_notes_section.py`) and may not even be the same major version — `uv run` is what guarantees this repo's own `pyproject.toml`/`uv.lock`-pinned environment is the one that runs.

For a bundled script:

```
uv run --project <plugin root> python <plugin root>/shared/scripts/<script>.py <args>
```

For an ad hoc snippet with no file of its own:

```
uv run --project <plugin root> python -c "<snippet>"
```

`<plugin root>` is this plugin's own installed directory — the same directory every `SKILL.md` already resolves `../../shared/*.md` against, and every `shared/*.md` resolves `../scripts/*.py` against. Compute it as a concrete absolute path from wherever you found this file before running the command; don't assume the shell's current working directory is the plugin root, since the user's actual project directory can be anywhere.

## Scripts

- **`pdf_chunk_upload_helper.py <path> [--filename <name>]`** — with a local `%PDF-` magic-byte check that fails fast before any MCP call, uploads a local PDF to `prioris-mcp` via the three-phase chunked-upload flow (`research_localfile_begin_upload` → `research_localfile_upload_chunk` looped → `research_localfile_finalize_upload`), acting as its own in-process MCP client so every chunk's base64 stays inside the script and never reaches the calling agent's context. Prints one line of result JSON on stdout, or a one-line error on stderr. See `../local-file-handling.md`.
- **`extract_identifier.py <url-or-doi>`** — extract `{"provider": ..., "identifier": ...}` from a paper URL or bare DOI. See `../url-handling.md`.
- **`project_tag.py [--cwd PATH]`** — derives this project's stable `project:<slug>` note tag from the git remote (or folder name as a fallback). See `../notes-model.md`.
- **`format_note_choices.py [--max N]`** — turns a `research_notes_search` result list (piped in as JSON on stdin) into deterministic `AskUserQuestion` option labels for picking which existing note to update. See `../notes-model.md`.
- **`metadata_cache.py {read|write} <provider> <identifier> [...]`** — session-local title/author lookup cache under `.prioris/.metadata-cache/`, so a skill that already looked a paper's metadata up once doesn't pay for a second round trip. See `../data-layout.md`.
- **`review_schedule.py {record|due|prune} ...`** — `quiz-me`'s local spaced-repetition state under `.prioris/.review/schedule.json`. See `../notes-model.md`.
- **`render_note_export.py <vault-dir>`** — renders a `notes://{id}/export` resource read (piped in as JSON on stdin) into a YAML-frontmattered Markdown file. See `vault-export`'s `SKILL.md`.

Each script's own module docstring documents its exact usage, output shape, and exit codes — read it directly (`head -30 <script>.py`) if this summary isn't enough; running it with the wrong number of arguments also prints a usage line.

## What's deliberately *not* scripted

The `has_more` pagination loop for `parse_full_text` (see `../mcp-contracts.md#paging-through-full-text`) looks like the same kind of mechanical repetition, but isn't a candidate: each iteration needs to hand its `markdown` page back into the conversation (to write to `.prioris/papers/...` or discuss), and only the agent driving the conversation can do that — a script that made this loop internally would have nowhere to put the pages it collected except print them, defeating the point. That loop stays as a prose instruction.

`pdf_chunk_upload_helper.py`'s own begin/chunk-loop/finalize sequence looks like the same shape but *is* scripted despite that reasoning, because it's the opposite case: nothing about an intermediate chunk's `upload_chunk` response needs to reach the conversation at all — only the final `finalize_upload` result does — so running the whole loop inside one script call, as its own MCP client, is strictly better than surfacing each chunk as a separate tool call the agent would otherwise have to make (and pay context for) one by one.
