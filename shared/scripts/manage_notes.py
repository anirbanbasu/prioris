"""Deterministic CLI wrapper around prioris-mcp's NotesBackend (research_notes_* tools).

Acts as its own in-process fastmcp client (via _mcp_client.py) so a skill doing notes search,
CRUD, or cross-note aggregation never has to hold multiple raw tool-call round trips, jq
extraction, or an oversized raw JSON payload in its own conversation - only this script's single,
already-shaped stdout line does. See ../notes-model.md and ../mcp-contracts.md#notes.

Usage:
    uv run --project <plugin root> python shared/scripts/manage_notes.py search
        [--provider {arxiv,europepmc,localfile}] [--identifier ID] [--format FMT]
        [--date-from ISO] [--date-to ISO] [--keyword Q]
        [--author-filter {any,mine,named}] [--author-name NAME]
        [--tags-all TAG [TAG ...]] [--tags-any TAG [TAG ...]] [--tags-exclude TAG [TAG ...]]
        [--mode {fts,vector,hybrid}] [--offset N] [--limit N]
        [--all] [--max-pages N] [--group-by-paper] [--attach-titles] [--root PATH]

    uv run --project <plugin root> python shared/scripts/manage_notes.py read NOTE_ID

    uv run --project <plugin root> python shared/scripts/manage_notes.py create
        --provider P --identifier ID [--format FMT] --text TEXT
        [--anchor-quote QUOTE [...]] [--author-name NAME] [--tag TAG [...]]
        [--metadata KEY=VALUE [...]]

    uv run --project <plugin root> python shared/scripts/manage_notes.py update NOTE_ID
        [--text TEXT] [--tag TAG [...]] [--clear-tags]
        [--anchor-quote QUOTE [...]] [--clear-anchors]
        [--metadata KEY=VALUE [...]] [--clear-metadata]

    uv run --project <plugin root> python shared/scripts/manage_notes.py delete NOTE_ID

`search` without `--group-by-paper` prints research_notes_search's own result shape
({"fts": {...}|omitted, "vector": {...}|omitted, "index_status": {...}|null}), aggregated across
pages if `--all` is given (loops offset per populated block until has_more is false or
--max-pages, default 20, is hit - a stderr warning notes if the cap was hit before exhaustion).

`search --group-by-paper` requires `--mode fts` (the default) - vector matches carry no
provider/canonical_identifier to group by, so this exits 1 under vector/hybrid. Prints a JSON
array of per-paper digest groups instead, most-recently-updated first:
    [{"provider", "canonical_identifier", "title": str|null, "authors": [str, ...]|null,
      "latest_updated_at", "notes": [{"id", "text", "tags", "created_at", "updated_at"}, ...]}]
`title`/`authors` are populated only with --attach-titles, from metadata_cache.py's cache under
--root (default "."); a cache miss leaves both null rather than triggering a fetch.

`create`/`update` each build every `--anchor-quote` into an Anchor with only
`selectors.exact_text_quote` set - the one anchor shape this CLI supports; call the MCP tool
directly for a page_number/section_heading anchor instead. `--metadata KEY=VALUE` is repeatable
and builds a flat string/string dict. `update`'s `--clear-tags`/`--clear-anchors`/
`--clear-metadata` send an explicit `[]`/`{}` for that field - distinct from omitting it, which
leaves the field unchanged (see mcp-contracts.md#notes).

Every subcommand prints exactly one JSON value to stdout on success and exits 0; a prioris-mcp
failure (not_found, invalid_request, ...) prints a one-line message to stderr and exits 1, via
_mcp_client.call_tool - see that module's own docstring.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, cast

import anyio
import metadata_cache
from _mcp_client import call_tool, client
from prioris_mcp.models.notes import Note, NotesSearchResult

_DEFAULT_MAX_PAGES = 20


def _build_anchors(quotes: list[str]) -> list[dict[str, Any]]:
    return [{"selectors": {"exact_text_quote": quote}} for quote in quotes]


def _parse_metadata(pairs: list[str]) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            sys.exit(f"--metadata expects KEY=VALUE, got: {pair!r}")
        key, _, value = pair.partition("=")
        metadata[key] = value
    return metadata


async def _search_page(
    c: Any, args: argparse.Namespace, offset: int
) -> NotesSearchResult:
    arguments: dict[str, Any] = {
        "provider": args.provider,
        "canonical_identifier": args.identifier,
        "format": args.format,
        "date_from": args.date_from,
        "date_to": args.date_to,
        "keyword": args.keyword,
        "author_filter": args.author_filter,
        "author_name": args.author_name,
        "tags_all": args.tags_all,
        "tags_any": args.tags_any,
        "tags_exclude": args.tags_exclude,
        "mode": args.mode,
        "offset": offset,
        "limit": args.limit,
    }
    return await call_tool(c, "research_notes_search", arguments, NotesSearchResult)


async def _run_search(args: argparse.Namespace) -> dict[str, Any]:
    async with client() as c:
        fts_notes: list[dict[str, Any]] = []
        vector_matches: list[dict[str, Any]] = []
        index_status: dict[str, Any] | None = None
        offset = args.offset
        page_count = 0
        while True:
            page_count += 1
            result = await _search_page(c, args, offset)
            if result.fts is not None:
                fts_notes.extend(
                    n.model_dump(by_alias=True, mode="json") for n in result.fts.notes
                )
            if result.vector is not None:
                vector_matches.extend(
                    m.model_dump(by_alias=True, mode="json")
                    for m in result.vector.matches
                )
            if result.index_status is not None:
                index_status = {
                    k: cast(Any, v).value for k, v in result.index_status.items()
                }

            has_more = (result.fts.has_more if result.fts is not None else False) or (
                result.vector.has_more if result.vector is not None else False
            )
            if not args.all or not has_more:
                break
            if page_count >= args.max_pages:
                print(
                    f"stopped after {args.max_pages} pages; more results remain",
                    file=sys.stderr,
                )
                break
            offset += args.limit

        output: dict[str, Any] = {}
        if fts_notes or args.mode in ("fts", "hybrid"):
            output["fts"] = {"notes": fts_notes, "total": len(fts_notes)}
        if vector_matches or args.mode in ("vector", "hybrid"):
            output["vector"] = {"matches": vector_matches, "total": len(vector_matches)}
        output["index_status"] = index_status
        return output


def _group_by_paper(
    fts_notes: list[dict[str, Any]], root: Path, attach_titles: bool
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for note in fts_notes:
        key = (note["provider"], note["canonical_identifier"])
        group = groups.setdefault(
            key,
            {
                "provider": note["provider"],
                "canonical_identifier": note["canonical_identifier"],
                "title": None,
                "authors": None,
                "latest_updated_at": note["updated_at"],
                "notes": [],
            },
        )
        group["notes"].append(
            {
                "id": note["id"],
                "text": note["text"],
                "tags": note["tags"],
                "created_at": note["created_at"],
                "updated_at": note["updated_at"],
            }
        )
        group["latest_updated_at"] = max(group["latest_updated_at"], note["updated_at"])

    ordered = sorted(
        groups.values(), key=lambda g: g["latest_updated_at"], reverse=True
    )
    if attach_titles:
        for group in ordered:
            cached = metadata_cache.read_cached(
                root, group["provider"], group["canonical_identifier"]
            )
            if cached is not None:
                group["title"] = cached.get("title")
                group["authors"] = cached.get("authors")
    return ordered


async def cmd_search(args: argparse.Namespace) -> int:
    if args.group_by_paper and args.mode != "fts":
        sys.exit(
            "--group-by-paper requires --mode fts (vector matches carry no provider/canonical_identifier)"
        )
    result = await _run_search(args)
    if args.group_by_paper:
        fts_notes = result.get("fts", {}).get("notes", [])
        groups = _group_by_paper(
            fts_notes, Path(args.root).resolve(), args.attach_titles
        )
        print(json.dumps(groups))
    else:
        print(json.dumps(result))
    return 0


async def cmd_read(args: argparse.Namespace) -> int:
    async with client() as c:
        note = await call_tool(
            c, "research_notes_read", {"note_id": args.note_id}, Note
        )
    print(note.model_dump_json(by_alias=True))
    return 0


async def cmd_create(args: argparse.Namespace) -> int:
    async with client() as c:
        note = await call_tool(
            c,
            "research_notes_create",
            {
                "provider": args.provider,
                "identifier": args.identifier,
                "format": args.format,
                "text": args.text,
                "anchors": _build_anchors(args.anchor_quote),
                "author_name": args.author_name,
                "tags": args.tag,
                "metadata": _parse_metadata(args.metadata) or None,
            },
            Note,
        )
    print(note.model_dump_json(by_alias=True))
    return 0


async def cmd_update(args: argparse.Namespace) -> int:
    arguments: dict[str, Any] = {"note_id": args.note_id}
    if args.text is not None:
        arguments["text"] = args.text
    if args.clear_tags:
        arguments["tags"] = []
    elif args.tag:
        arguments["tags"] = args.tag
    if args.clear_anchors:
        arguments["anchors"] = []
    elif args.anchor_quote:
        arguments["anchors"] = _build_anchors(args.anchor_quote)
    if args.clear_metadata:
        arguments["metadata"] = {}
    elif args.metadata:
        arguments["metadata"] = _parse_metadata(args.metadata)

    async with client() as c:
        note = await call_tool(c, "research_notes_update", arguments, Note)
    print(note.model_dump_json(by_alias=True))
    return 0


async def cmd_delete(args: argparse.Namespace) -> int:
    async with client() as c:
        deleted = await call_tool(c, "research_notes_delete", {"note_id": args.note_id})
    print(json.dumps({"deleted": deleted}))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    search_p = sub.add_parser("search")
    search_p.add_argument(
        "--provider", choices=["arxiv", "europepmc", "localfile"], default=None
    )
    search_p.add_argument("--identifier", default=None)
    search_p.add_argument("--format", default=None)
    search_p.add_argument("--date-from", default=None)
    search_p.add_argument("--date-to", default=None)
    search_p.add_argument("--keyword", default=None)
    search_p.add_argument(
        "--author-filter", choices=["any", "mine", "named"], default="any"
    )
    search_p.add_argument("--author-name", default=None)
    search_p.add_argument("--tags-all", nargs="+", default=[])
    search_p.add_argument("--tags-any", nargs="+", default=[])
    search_p.add_argument("--tags-exclude", nargs="+", default=[])
    search_p.add_argument("--mode", choices=["fts", "vector", "hybrid"], default="fts")
    search_p.add_argument("--offset", type=int, default=0)
    search_p.add_argument("--limit", type=int, default=50)
    search_p.add_argument("--all", action="store_true")
    search_p.add_argument("--max-pages", type=int, default=_DEFAULT_MAX_PAGES)
    search_p.add_argument("--group-by-paper", action="store_true")
    search_p.add_argument("--attach-titles", action="store_true")
    search_p.add_argument("--root", default=".")

    read_p = sub.add_parser("read")
    read_p.add_argument("note_id")

    create_p = sub.add_parser("create")
    create_p.add_argument(
        "--provider", required=True, choices=["arxiv", "europepmc", "localfile"]
    )
    create_p.add_argument("--identifier", required=True)
    create_p.add_argument("--format", default=None)
    create_p.add_argument("--text", required=True)
    create_p.add_argument("--anchor-quote", nargs="+", default=[], dest="anchor_quote")
    create_p.add_argument("--author-name", default=None)
    create_p.add_argument("--tag", nargs="+", default=[], dest="tag")
    create_p.add_argument("--metadata", nargs="+", default=[])

    update_p = sub.add_parser("update")
    update_p.add_argument("note_id")
    update_p.add_argument("--text", default=None)
    update_p.add_argument("--tag", nargs="+", default=[], dest="tag")
    update_p.add_argument("--clear-tags", action="store_true")
    update_p.add_argument("--anchor-quote", nargs="+", default=[], dest="anchor_quote")
    update_p.add_argument("--clear-anchors", action="store_true")
    update_p.add_argument("--metadata", nargs="+", default=[])
    update_p.add_argument("--clear-metadata", action="store_true")

    delete_p = sub.add_parser("delete")
    delete_p.add_argument("note_id")

    return parser


_HANDLERS = {
    "search": cmd_search,
    "read": cmd_read,
    "create": cmd_create,
    "update": cmd_update,
    "delete": cmd_delete,
}


def main() -> int:
    args = build_parser().parse_args()
    return anyio.run(_HANDLERS[args.command], args)


if __name__ == "__main__":
    raise SystemExit(main())
