"""Deterministic CLI wrapper around prioris-mcp's research_search_fetched tool.

Acts as its own in-process fastmcp client (via _mcp_client.py), looping pagination and applying
a client-side score floor itself, so discuss's local-search-first step never has to hold a raw,
unthresholded vector-match page in its own conversation. See ../mcp-contracts.md's "Search over
fetched content" section - this never triggers a fetch or parse, only searches content already
fetched and parsed on the server.

Usage:
    uv run --project <plugin root> python shared/scripts/manage_search.py search --query Q
        [--provider {arxiv,europepmc,localfile}] [--identifier ID] [--format FMT]
        [--mode {fts,vector,hybrid}] [--offset N] [--limit N]
        [--all] [--max-pages N] [--min-score FLOAT] [--attach-titles] [--root PATH]

Prints {"fts": {"matches": [...], "total": N}, "vector": {...}, "index_status": {...}} (each of
fts/vector present only when --mode requested it), aggregated across pages if `--all` (loops each
populated block's own offset until has_more is false or --max-pages, default 20, is hit).
`--min-score` drops any match (fts or vector) whose score is below it - required practice for
vector/hybrid mode per mcp-contracts.md's "Vector/KNN search is unthresholded" caveat, applied
uniformly to fts matches too since SearchMatch/VectorSearchMatch both carry a `score` field.
`--attach-titles` adds `title`/`authors` to each match from metadata_cache.py's cache under --root
(default "."); a cache miss leaves both null.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import anyio
import metadata_cache
from _mcp_client import call_tool, client
from prioris_mcp.models.common import SearchFetchedResult

_DEFAULT_MAX_PAGES = 20


async def _search_page(
    c: Any, args: argparse.Namespace, offset: int
) -> SearchFetchedResult:
    arguments: dict[str, Any] = {
        "query": args.query,
        "provider": args.provider,
        "identifier": args.identifier,
        "format": args.format,
        "mode": args.mode,
        "offset": offset,
        "limit": args.limit,
    }
    return await call_tool(c, "research_search_fetched", arguments, SearchFetchedResult)


def _attach_title(match: dict[str, Any], root: Path) -> dict[str, Any]:
    cached = metadata_cache.read_cached(root, match["provider"], match["identifier"])
    match["title"] = cached.get("title") if cached else None
    match["authors"] = cached.get("authors") if cached else None
    return match


async def run(args: argparse.Namespace) -> int:
    async with client() as c:
        fts_matches: list[dict[str, Any]] = []
        vector_matches: list[dict[str, Any]] = []
        index_status: dict[str, Any] = {}
        offset = args.offset
        page_count = 0
        while True:
            page_count += 1
            result = await _search_page(c, args, offset)
            if result.fts is not None:
                fts_matches.extend(
                    m.model_dump(by_alias=True, mode="json") for m in result.fts.matches
                )
            if result.vector is not None:
                vector_matches.extend(
                    m.model_dump(by_alias=True, mode="json")
                    for m in result.vector.matches
                )
            index_status = dict(result.index_status.items())

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

    if args.min_score is not None:
        fts_matches = [m for m in fts_matches if m["score"] >= args.min_score]
        vector_matches = [m for m in vector_matches if m["score"] >= args.min_score]

    if args.attach_titles:
        root = Path(args.root).resolve()
        fts_matches = [_attach_title(m, root) for m in fts_matches]
        vector_matches = [_attach_title(m, root) for m in vector_matches]

    output: dict[str, Any] = {}
    if args.mode in ("fts", "hybrid"):
        output["fts"] = {"matches": fts_matches, "total": len(fts_matches)}
    if args.mode in ("vector", "hybrid"):
        output["vector"] = {"matches": vector_matches, "total": len(vector_matches)}
    output["index_status"] = index_status
    print(json.dumps(output))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    search_p = sub.add_parser("search")
    search_p.add_argument("--query", required=True)
    search_p.add_argument(
        "--provider", choices=["arxiv", "europepmc", "localfile"], default=None
    )
    search_p.add_argument("--identifier", default=None)
    search_p.add_argument("--format", default=None)
    search_p.add_argument("--mode", choices=["fts", "vector", "hybrid"], default="fts")
    search_p.add_argument("--offset", type=int, default=0)
    search_p.add_argument("--limit", type=int, default=50)
    search_p.add_argument("--all", action="store_true")
    search_p.add_argument("--max-pages", type=int, default=_DEFAULT_MAX_PAGES)
    search_p.add_argument("--min-score", type=float, default=None)
    search_p.add_argument("--attach-titles", action="store_true")
    search_p.add_argument("--root", default=".")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return anyio.run(run, args)


if __name__ == "__main__":
    raise SystemExit(main())
