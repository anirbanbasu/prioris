# Shared: Bundled Scripts

Referenced by `local-file-handling.md`, `url-handling.md`, and the Record step of `discuss`, `quick-read`, and `quiz-me`. Each script below replaces a step that's mechanical — base64-encoding bytes, parsing a URL, merging one section into a YAML-frontmattered markdown file — and has exactly one correct answer, unlike the judgment calls (which provider, what to say, whether to discuss further) that stay as prose instructions. Re-deriving the equivalent shell/regex/YAML logic by hand every invocation risks the same categories of mistake each time: a platform-dependent shell flag, a slipped regex branch, a hand-edited YAML block that clobbers a sibling section. Running the same tested script instead makes the outcome deterministic.

## How to invoke them

Run every script with `uv`, using the environment this repo's own `pyproject.toml`/`uv.lock` pin — not your own `python3`, which won't have the pinned dependencies these scripts rely on (e.g. PyYAML for `update_notes_section.py`):

```
uv run --project <plugin root> python <plugin root>/shared/scripts/<script>.py <args>
```

`<plugin root>` is this plugin's own installed directory — the same directory every `SKILL.md` already resolves `../../shared/*.md` against, and every `shared/*.md` resolves `../scripts/*.py` against. Compute it as a concrete absolute path from wherever you found this file before running the command; don't assume the shell's current working directory is the plugin root, since the user's actual project directory can be anywhere.

## Scripts

- **`encode_local_pdf.py <path>`** — base64-encode a local PDF for `content_base64`, with a local `%PDF-` magic-byte check that fails fast before any MCP call. See `../local-file-handling.md`.
- **`extract_identifier.py <url-or-doi>`** — extract `{"provider": ..., "identifier": ...}` from a paper URL or bare DOI. See `../url-handling.md`.
- **`update_notes_section.py <target.md> "<## Header>" <content-file> [--frontmatter <keys.yaml>]`** — merge one named section (and optionally some frontmatter keys) into a `.prioris/discussions/<provider>/<identifier>.md` note, preserving every other section and frontmatter key untouched. See `../data-layout.md` and each skill's Record step.

Each script's own module docstring documents its exact usage, output shape, and exit codes — read it directly (`head -30 <script>.py`) if this summary isn't enough; running it with the wrong number of arguments also prints a usage line.

## What's deliberately *not* scripted

The `has_more` pagination loop for `parse_full_text` (see `../mcp-contracts.md#paging-through-full-text`) looks like the same kind of mechanical repetition, but isn't a candidate: each iteration is itself an MCP tool call, and only the agent driving the conversation can make one — a script has no path to invoke `prioris-mcp` the same way. That loop stays as a prose instruction.
