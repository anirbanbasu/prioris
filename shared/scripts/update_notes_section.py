"""Merge one named section (and optionally some frontmatter keys) into a
.prioris/discussions/<provider>/<identifier>.md note, preserving everything
else in the file untouched.

Exists because "read the file, find the right section, replace just that
part, keep the rest, don't corrupt the YAML frontmatter" is mechanical but
has real edge cases (first write vs. update, YAML-unsafe titles/authors
containing colons or quotes, accidentally clobbering a sibling section) -
see ../data-layout.md and the "Record" steps in discuss/quick-read/quiz-me's
SKILL.md. Getting any of that wrong silently loses the user's own notes,
which are the one thing in .prioris/ that isn't just regenerable cache.

Usage:
    uv run --project <plugin root> python shared/scripts/update_notes_section.py \\
        <target.md> "<## Section Header>" <content-file.md> [--frontmatter <keys.yaml>]

- <target.md>: e.g. .prioris/discussions/arxiv/2401.12345v2.md. Created fresh
  (with a minimal frontmatter block) if it doesn't exist yet.
- <content-file.md>: a file containing just the section's body markdown -
  not the "## " header line itself, that's the second argument.
- --frontmatter <keys.yaml>: optional path to a YAML file containing only the
  frontmatter keys to set or overwrite (e.g. `read_at: ...`). Existing keys
  not mentioned are left as-is. Required (with the full schema per
  ../data-layout.md) the first time a file is created, since the script has
  no way to invent title/authors/tags/etc. itself.

If the named section already exists (matched by exact header text), its
content is replaced in place, preserving section order. Otherwise the new
section is appended at the end. Writes are atomic (temp file + rename).
"""

import re
import sys
from pathlib import Path

import yaml

SECTION_RE = re.compile(r"^(##\s+.+)$", re.MULTILINE)


class _StringSafeLoader(yaml.SafeLoader):
    """SafeLoader that leaves ISO-8601-looking strings as plain strings.

    PyYAML's default implicit resolvers auto-parse e.g. "2026-07-28T01:47:45Z"
    into a datetime object, which then re-serializes as "2026-07-28
    01:47:45+00:00" - silently breaking data-layout.md's "fetched_at/read_at:
    <ISO 8601>" contract on every round trip through this script.
    """


_StringSafeLoader.yaml_implicit_resolvers = {
    key: [
        (tag, regexp)
        for tag, regexp in resolvers
        if tag != "tag:yaml.org,2002:timestamp"
    ]
    for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def split_frontmatter(text: str) -> tuple[dict, str]:
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise ValueError("file doesn't start with a '---' frontmatter delimiter")
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        raise ValueError("frontmatter '---' block is never closed")
    frontmatter = yaml.load("".join(lines[1:end_idx]), Loader=_StringSafeLoader) or {}
    if not isinstance(frontmatter, dict):
        raise TypeError("frontmatter didn't parse as a YAML mapping")
    body = "".join(lines[end_idx + 1 :])
    return frontmatter, body


def parse_sections(body: str) -> list[list[str]]:
    matches = list(SECTION_RE.finditer(body))
    sections = []
    for i, m in enumerate(matches):
        header = m.group(1).rstrip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        sections.append([header, body[start:end].strip("\n")])
    return sections


def render(frontmatter: dict, sections: list[list[str]]) -> str:
    fm_text = yaml.dump(
        frontmatter,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=None,
        width=1000,
    )
    parts = ["---\n", fm_text, "---\n"]
    for header, content in sections:
        parts.append("\n" + header + "\n")
        if content:
            parts.append("\n" + content + "\n")
    return "".join(parts).rstrip("\n") + "\n"


def main() -> int:
    args = sys.argv[1:]
    frontmatter_path = None
    if "--frontmatter" in args:
        idx = args.index("--frontmatter")
        try:
            frontmatter_path = args[idx + 1]
        except IndexError:
            print("--frontmatter requires a path argument", file=sys.stderr)
            return 2
        del args[idx : idx + 2]

    if len(args) != 3:
        print(
            f'usage: {Path(sys.argv[0]).name} <target.md> "<## Section Header>" '
            "<content-file.md> [--frontmatter <keys.yaml>]",
            file=sys.stderr,
        )
        return 2

    target_path, section_header, content_file = (
        Path(args[0]),
        args[1].rstrip(),
        Path(args[2]),
    )

    if not section_header.startswith("#"):
        print(
            f'section header must start with "#" (e.g. "## Quick read"), got: {section_header!r}',
            file=sys.stderr,
        )
        return 2

    try:
        new_content = content_file.read_text().strip("\n")
    except OSError as exc:
        print(f"couldn't read content file {content_file}: {exc}", file=sys.stderr)
        return 1

    if target_path.exists():
        try:
            frontmatter, body = split_frontmatter(target_path.read_text())
        except (ValueError, TypeError) as exc:
            print(
                f"{target_path} doesn't look safe to merge into: {exc}", file=sys.stderr
            )
            return 1
        sections = parse_sections(body)
        created = False
    else:
        frontmatter, sections = {}, []
        created = True

    if frontmatter_path is not None:
        try:
            overrides = yaml.load(
                Path(frontmatter_path).read_text(), Loader=_StringSafeLoader
            )
        except OSError as exc:
            print(
                f"couldn't read frontmatter file {frontmatter_path}: {exc}",
                file=sys.stderr,
            )
            return 1
        if overrides:
            if not isinstance(overrides, dict):
                print(
                    f"{frontmatter_path} must be a YAML mapping of frontmatter keys",
                    file=sys.stderr,
                )
                return 1
            frontmatter.update(overrides)
    elif created:
        print(
            f"{target_path} doesn't exist yet and no --frontmatter was given - "
            "the file would be created with an empty frontmatter block",
            file=sys.stderr,
        )

    replaced = False
    for entry in sections:
        if entry[0].strip() == section_header:
            entry[1] = new_content
            replaced = True
            break
    if not replaced:
        sections.append([section_header, new_content])

    target_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target_path.with_suffix(target_path.suffix + ".tmp")
    tmp_path.write_text(render(frontmatter, sections))
    tmp_path.replace(target_path)

    verb = "created" if created else ("updated" if replaced else "appended to")
    print(f"{verb} {section_header!r} in {target_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
