"""Deterministic CLI wrapper around prioris-mcp's arXiv tools (search, list-top-n,
fetch-metadata, categories).

Acts as its own in-process fastmcp client (via _mcp_client.py) so discuss's Search step and
rmotd's arXiv branch never have to hold a raw ArxivSearchResult/ArxivCategoriesResult page in
their own conversation just to list or filter candidates - comprehension of any one paper's
actual full text still goes through ../../agents/document-reader.md, unaffected by this script.
See ../mcp-contracts.md's "arXiv" section.

Usage:
    uv run --project <plugin root> python shared/scripts/manage_arxiv.py search --query Q
        [--max-results N] [--start N] [--sort-by NAME] [--sort-order NAME]

    uv run --project <plugin root> python shared/scripts/manage_arxiv.py list-top-n
        --include-category CODE [CODE ...] --n N [--exclude-category CODE [CODE ...]]

    uv run --project <plugin root> python shared/scripts/manage_arxiv.py fetch-metadata
        --arxiv-id ID [ID ...]

    uv run --project <plugin root> python shared/scripts/manage_arxiv.py categories
        [--code CODE] [--query TEXT]

`search`/`list-top-n`/`fetch-metadata` each print their tool's own result shape as-is - no
aggregation or reshaping, since none of these paginate beyond what the tool's own `max_results`/
`n` already bounds. `categories` reads research://arxiv/categories once: with `--code`, prints
that one {"code", "name"} entry or exits 1 if the code isn't found (a lookup miss, not a
prioris-mcp failure); with `--query`, prints every entry whose name case-insensitively contains
it; with neither, prints the full list.
"""

import argparse
import json
import sys

import anyio
from _mcp_client import call_tool, client, read_resource
from prioris_mcp.models.arxiv import (
    ArxivCategoriesResult,
    ArxivFetchMetadataResult,
    ArxivSearchResult,
)


async def cmd_search(args: argparse.Namespace) -> int:
    arguments: dict[str, object] = {
        "query": args.query,
        "max_results": args.max_results,
        "start": args.start,
    }
    if args.sort_by is not None:
        arguments["sort_by"] = args.sort_by
    if args.sort_order is not None:
        arguments["sort_order"] = args.sort_order
    async with client() as c:
        result = await call_tool(
            c,
            "research_arxiv_search",
            arguments,
            ArxivSearchResult,
        )
    print(result.model_dump_json(by_alias=True))
    return 0


async def cmd_list_top_n(args: argparse.Namespace) -> int:
    async with client() as c:
        result = await call_tool(
            c,
            "research_arxiv_list_top_n",
            {
                "include_categories": args.include_category,
                "n": args.n,
                "exclude_categories": args.exclude_category or None,
            },
            ArxivSearchResult,
        )
    print(result.model_dump_json(by_alias=True))
    return 0


async def cmd_fetch_metadata(args: argparse.Namespace) -> int:
    async with client() as c:
        result = await call_tool(
            c,
            "research_arxiv_fetch_metadata",
            {"arxiv_ids": args.arxiv_id},
            ArxivFetchMetadataResult,
        )
    print(result.model_dump_json(by_alias=True))
    return 0


async def cmd_categories(args: argparse.Namespace) -> int:
    async with client() as c:
        result = await read_resource(
            c, "research://arxiv/categories", ArxivCategoriesResult
        )

    if args.code is not None:
        for category in result.categories:
            if category.code == args.code:
                print(category.model_dump_json())
                return 0
        sys.exit(f"no arXiv category with code {args.code!r}")

    categories = result.categories
    if args.query is not None:
        needle = args.query.lower()
        categories = [c for c in categories if needle in c.name.lower()]
    print(json.dumps([c.model_dump(mode="json") for c in categories]))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    search_p = sub.add_parser("search")
    search_p.add_argument("--query", required=True)
    search_p.add_argument("--max-results", type=int, default=10)
    search_p.add_argument("--start", type=int, default=0)
    search_p.add_argument("--sort-by", default=None)
    search_p.add_argument("--sort-order", default=None)

    list_top_n_p = sub.add_parser("list-top-n")
    list_top_n_p.add_argument(
        "--include-category", action="extend", nargs="+", required=True
    )
    list_top_n_p.add_argument("--n", type=int, required=True)
    list_top_n_p.add_argument(
        "--exclude-category", action="extend", nargs="+", default=[]
    )

    fetch_p = sub.add_parser("fetch-metadata")
    fetch_p.add_argument(
        "--arxiv-id", action="extend", nargs="+", required=True, dest="arxiv_id"
    )

    categories_p = sub.add_parser("categories")
    categories_p.add_argument("--code", default=None)
    categories_p.add_argument("--query", default=None)

    return parser


_HANDLERS = {
    "search": cmd_search,
    "list-top-n": cmd_list_top_n,
    "fetch-metadata": cmd_fetch_metadata,
    "categories": cmd_categories,
}


def main() -> int:
    args = build_parser().parse_args()
    return anyio.run(_HANDLERS[args.command], args)


if __name__ == "__main__":
    raise SystemExit(main())
