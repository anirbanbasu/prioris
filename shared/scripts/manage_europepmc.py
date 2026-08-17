"""Deterministic CLI wrapper around prioris-mcp's Europe PMC tools (search, fetch-metadata).

Acts as its own in-process fastmcp client (via _mcp_client.py) so discuss's Search step never has
to hold a raw EuropePmcSearchResult page in its own conversation just to list candidates -
comprehension of any one paper's actual full text still goes through
../../agents/document-reader.md, unaffected by this script. See ../mcp-contracts.md's "Europe
PMC" section. Europe PMC has no source-generic recency/category-browse or resource-lookup
equivalent to arXiv's list-top-n/categories (see ../scope.md), so this script has only the two
subcommands below.

Usage:
    uv run --project <plugin root> python shared/scripts/manage_europepmc.py search --query Q
        [--page-size N] [--cursor-mark MARK] [--all] [--max-pages N]

    uv run --project <plugin root> python shared/scripts/manage_europepmc.py fetch-metadata
        --identifier ID [ID ...]

`search` prints {"results": [...], "hit_count": N, "next_cursor_mark": str|null}. `--all` loops
`next_cursor_mark` (starting from `--cursor-mark`, default "*") until it comes back null/empty or
--max-pages (default 10) is hit, aggregating `results`; `next_cursor_mark` in the output then
reflects the last page fetched. `fetch-metadata` prints its tool's own result shape as-is.
"""

import argparse
import json
import sys
from typing import Any

import anyio
from _mcp_client import call_tool, client
from prioris_mcp.models.europepmc import (
    EuropePmcFetchMetadataResult,
    EuropePmcSearchResult,
)

_DEFAULT_MAX_PAGES = 10


async def cmd_search(args: argparse.Namespace) -> int:
    async with client() as c:
        all_results: list[Any] = []
        cursor_mark: str | None = args.cursor_mark
        hit_count = 0
        page_count = 0
        while True:
            page_count += 1
            result = await call_tool(
                c,
                "research_europepmc_search",
                {
                    "query": args.query,
                    "page_size": args.page_size,
                    "cursor_mark": cursor_mark,
                },
                EuropePmcSearchResult,
            )
            all_results.extend(
                r.model_dump(by_alias=True, mode="json") for r in result.results
            )
            hit_count = result.hit_count
            cursor_mark = result.next_cursor_mark

            if not args.all or not cursor_mark:
                break
            if page_count >= args.max_pages:
                print(
                    f"stopped after {args.max_pages} pages; more results remain",
                    file=sys.stderr,
                )
                break

    print(
        json.dumps(
            {
                "results": all_results,
                "hit_count": hit_count,
                "next_cursor_mark": cursor_mark,
            }
        )
    )
    return 0


async def cmd_fetch_metadata(args: argparse.Namespace) -> int:
    async with client() as c:
        result = await call_tool(
            c,
            "research_europepmc_fetch_metadata",
            {"identifiers": args.identifier},
            EuropePmcFetchMetadataResult,
        )
    print(result.model_dump_json(by_alias=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    search_p = sub.add_parser("search")
    search_p.add_argument("--query", required=True)
    search_p.add_argument("--page-size", type=int, default=25)
    search_p.add_argument("--cursor-mark", default="*")
    search_p.add_argument("--all", action="store_true")
    search_p.add_argument("--max-pages", type=int, default=_DEFAULT_MAX_PAGES)

    fetch_p = sub.add_parser("fetch-metadata")
    fetch_p.add_argument(
        "--identifier", action="extend", nargs="+", required=True, dest="identifier"
    )

    return parser


_HANDLERS = {"search": cmd_search, "fetch-metadata": cmd_fetch_metadata}


def main() -> int:
    args = build_parser().parse_args()
    return anyio.run(_HANDLERS[args.command], args)


if __name__ == "__main__":
    raise SystemExit(main())
