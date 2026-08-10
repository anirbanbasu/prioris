"""Turn a research_notes_search result list into deterministic AskUserQuestion labels.

Exists because tags alone can't reliably disambiguate which existing note to
update - the calling skill must always ask the user, and the option labels
it asks with must be stable across sessions (an LLM-authored summary would
not be), not a fresh judgment call each time. See
../notes-model.md#find-or-create-pattern.

Usage:
    uv run --project <plugin root> python shared/scripts/format_note_choices.py [--max N] < notes.json

Reads a JSON array of note objects (id, text, tags at minimum - the shape
research_notes_search's "notes" field already returns) from stdin. Prints a
JSON array of {"id": ..., "label": ...} to stdout, capped at --max entries
(default 4), preserving input order. Exits 1 with a message on stderr if
stdin isn't valid JSON or isn't a JSON array.
"""

import argparse
import json
import sys

_LABEL_MAX = 80
_TOPIC_PREFIXES = ("topic:", "type:", "section:")


def first_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped:
            return stripped
    return "(empty note)"


def topic_tag(tags: list[str]) -> str | None:
    for tag in tags:
        if tag.startswith(_TOPIC_PREFIXES):
            return tag
    return None


def build_choice(note: dict) -> dict:
    label = first_line(note["text"])
    if len(label) > _LABEL_MAX:
        label = label[: _LABEL_MAX - 3] + "..."
    tag = topic_tag(note.get("tags", []))
    if tag:
        label = f"{label} [{tag}]"
    return {"id": note["id"], "label": label}


def build_choices(notes: list[dict]) -> list[dict]:
    return [build_choice(note) for note in notes]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max", type=int, default=4)
    args = parser.parse_args()

    try:
        notes = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        print(f"stdin did not contain valid JSON: {exc}", file=sys.stderr)
        return 1
    if not isinstance(notes, list):
        print("stdin JSON must be a list of note objects", file=sys.stderr)
        return 1

    print(json.dumps(build_choices(notes)[: args.max]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
