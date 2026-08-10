"""Render a notes://{note_id}/export resource read into a Markdown file with YAML frontmatter.

The server never writes this to disk itself (export is a resource, not a
tool, precisely so it doesn't - see prioris-mcp's Notes storage spec).
Turning the resource's plain-dict `frontmatter` into YAML, and picking the
file's final name and location, is this plugin's job. This is a pure
render-then-write from a fresh JSON object each time - unlike the retired
update_notes_section.py, there is no existing file to parse/merge into, so
no custom YAML loader is needed here, only a dumper.

Usage:
    uv run --project <plugin root> python shared/scripts/render_note_export.py <vault-dir> < export.json

Reads one notes://{id}/export JSON object ({"suggested_filename",
"frontmatter", "markdown_body"}) from stdin. Writes
<vault-dir>/<suggested_filename>.md (creating <vault-dir> if needed,
overwriting if the file already exists - vault exports are idempotent
snapshots, not append-merges) and prints the written path to stdout.
"""

import json
import sys
from pathlib import Path

import yaml


def render(export: dict) -> str:
    fm_text = yaml.safe_dump(
        export["frontmatter"],
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=None,
        width=1000,
    )
    return f"---\n{fm_text}---\n\n{export['markdown_body'].strip()}\n"


def write_export(export: dict, vault_dir: Path) -> Path:
    vault_dir.mkdir(parents=True, exist_ok=True)
    filename = export["suggested_filename"]
    if not filename.endswith(".md"):
        filename += ".md"
    target = vault_dir / filename
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(render(export))
    tmp.replace(target)
    return target


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {Path(sys.argv[0]).name} <vault-dir>", file=sys.stderr)
        return 2

    try:
        export = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        print(f"stdin did not contain valid JSON: {exc}", file=sys.stderr)
        return 1

    written = write_export(export, Path(sys.argv[1]))
    print(written)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
