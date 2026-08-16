"""Deterministic CLI wrapper around prioris-mcp's research_discovery tool (OpenAlex semantic
search).

Acts as its own in-process fastmcp client (via _mcp_client.py), looping pages and computing two
deterministic per-hit fields - needs_condensation and, when requested, work_type_name/
work_type_description - so rmotd's and discuss's OpenAlex branches never have to hold a raw
DiscoveryResult page (or a second research://openalex/work-types resource read) in their own
conversation just to apply those two purely mechanical rules. See ../mcp-contracts.md's "External
discovery" section. Never fetches, parses, or persists anything - discovery only.

Usage:
    uv run --project <plugin root> python shared/scripts/manage_discovery.py search --query Q
        [--max-results N] [--from-year Y] [--to-year Y] [--open-access-only]
        [--all] [--max-pages N] [--include-work-types]

Each hit in the printed {"hits": [...], "page", "per_page", "total", "has_more"} gets one added
field, needs_condensation: true if its abstract is non-null and exceeds 300 words - rmotd's own
verbatim-vs-condense threshold (see rmotd/SKILL.md) - false otherwise (including a null abstract,
which rmotd instead reports as "not available" rather than condensing). `--include-work-types`
additionally reads research://openalex/work-types once and adds work_type_name/
work_type_description to every hit whose work_type is non-null. `--all` loops `page` from 1
until has_more is false or --max-pages (default 5, since search.semantic caps at 50 total matches)
is hit, aggregating hits; `page`/`has_more` in the output then describe the last page fetched.
"""

import argparse
import json
import sys
from typing import Any

import anyio
from _mcp_client import call_tool, client, read_resource
from prioris_mcp.models.discovery import DiscoveryResult, OpenAlexWorkTypesResult

_DEFAULT_MAX_PAGES = 5
_CONDENSE_WORD_THRESHOLD = 300


def _needs_condensation(abstract: str | None) -> bool:
    return abstract is not None and len(abstract.split()) > _CONDENSE_WORD_THRESHOLD


async def run(args: argparse.Namespace) -> int:
    async with client() as c:
        work_types: dict[str, dict[str, str]] = {}
        if args.include_work_types:
            types_result = await read_resource(
                c, "research://openalex/work-types", OpenAlexWorkTypesResult
            )
            work_types = {
                t.code: {"name": t.name, "description": t.description}
                for t in types_result.types
            }

        all_hits: list[dict[str, Any]] = []
        page = 1
        page_count = 0
        last_result: DiscoveryResult | None = None
        while True:
            page_count += 1
            arguments: dict[str, Any] = {
                "query": args.query,
                "max_results": args.max_results,
                "page": page,
                "from_year": args.from_year,
                "to_year": args.to_year,
                "open_access_only": args.open_access_only,
            }
            result = await call_tool(
                c, "research_discovery", arguments, DiscoveryResult
            )
            last_result = result
            for hit in result.hits:
                hit_dict = hit.model_dump(by_alias=True, mode="json")
                hit_dict["needs_condensation"] = _needs_condensation(hit.abstract)
                if (
                    args.include_work_types
                    and hit.work_type is not None
                    and hit.work_type in work_types
                ):
                    hit_dict["work_type_name"] = work_types[hit.work_type]["name"]
                    hit_dict["work_type_description"] = work_types[hit.work_type][
                        "description"
                    ]
                all_hits.append(hit_dict)

            if not args.all or not result.has_more:
                break
            if page_count >= args.max_pages:
                print(
                    f"stopped after {args.max_pages} pages; more results remain",
                    file=sys.stderr,
                )
                break
            page += 1

    assert last_result is not None
    output = {
        "hits": all_hits,
        "page": last_result.page,
        "per_page": last_result.per_page,
        "total": last_result.total,
        "has_more": last_result.has_more,
    }
    print(json.dumps(output))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    search_p = sub.add_parser("search")
    search_p.add_argument("--query", required=True)
    search_p.add_argument("--max-results", type=int, default=None)
    search_p.add_argument("--from-year", type=int, default=None)
    search_p.add_argument("--to-year", type=int, default=None)
    search_p.add_argument("--open-access-only", action="store_true")
    search_p.add_argument("--all", action="store_true")
    search_p.add_argument("--max-pages", type=int, default=_DEFAULT_MAX_PAGES)
    search_p.add_argument("--include-work-types", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return anyio.run(run, args)


if __name__ == "__main__":
    raise SystemExit(main())
