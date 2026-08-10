"""Read/write .prioris/.metadata-cache/<provider>/<identifier>.json.

A tiny, disposable, gitignored index of title/authors/year, kept purely so a
skill that already looked a paper's metadata up once this session (e.g. via
research_arxiv_fetch_metadata) doesn't pay for a second round trip just to
show a title next to a note - never authoritative for anything, costs
nothing to lose. See ../data-layout.md.

Usage:
    uv run --project <plugin root> python shared/scripts/metadata_cache.py read <provider> <identifier> [--root PATH]
    uv run --project <plugin root> python shared/scripts/metadata_cache.py write <provider> <identifier> --title T [--author A ...] [--year Y] [--root PATH]

`read` prints the cached {"title", "authors", "year"} JSON object and exits
0 if present, or exits 1 with a message on stderr (a cache miss is a normal,
expected condition, not an error to be surprised by). `write` always
succeeds and prints a one-line confirmation to stderr.
"""

import argparse
import json
import sys
from pathlib import Path


def cache_path(root: Path, provider: str, identifier: str) -> Path:
    safe_id = identifier.replace(":", "_")
    return root / ".prioris" / ".metadata-cache" / provider / f"{safe_id}.json"


def read_cached(root: Path, provider: str, identifier: str) -> dict | None:
    path = cache_path(root, provider, identifier)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def write_cached(
    root: Path,
    provider: str,
    identifier: str,
    title: str,
    authors: list[str],
    year: str | None = None,
) -> None:
    path = cache_path(root, provider, identifier)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"title": title, "authors": authors, "year": year}
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload))
    tmp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    read_p = sub.add_parser("read")
    read_p.add_argument("provider")
    read_p.add_argument("identifier")
    read_p.add_argument("--root", default=".")

    write_p = sub.add_parser("write")
    write_p.add_argument("provider")
    write_p.add_argument("identifier")
    write_p.add_argument("--title", required=True)
    write_p.add_argument("--author", action="append", default=[], dest="authors")
    write_p.add_argument("--year", default=None)
    write_p.add_argument("--root", default=".")

    args = parser.parse_args()
    root = Path(args.root).resolve()

    if args.command == "read":
        cached = read_cached(root, args.provider, args.identifier)
        if cached is None:
            print(
                f"no cached metadata for {args.provider}/{args.identifier}",
                file=sys.stderr,
            )
            return 1
        print(json.dumps(cached))
        return 0

    write_cached(
        root,
        args.provider,
        args.identifier,
        title=args.title,
        authors=args.authors,
        year=args.year,
    )
    print(f"cached metadata for {args.provider}/{args.identifier}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
