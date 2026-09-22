"""Deterministic CLI wrapper for structural graph linking: Pointer upserts and idempotent edges.

No LLM judgment anywhere in this module - every write here is derivable purely from
(ref_type, ref_id) pairs the caller already has (a document's (provider, identifier), a note's
own id). See ../graph-model.md for the ref_id convention and the fixed relation_type vocabulary
this script is allowed to write.

Usage:
    uv run --project <plugin root> python shared/scripts/graph_structural_sync.py upsert \
        --ref-type {chunk,document,note} --ref-id ID [--metadata KEY=VALUE ...]

    uv run --project <plugin root> python shared/scripts/graph_structural_sync.py link \
        --from-ref-type {chunk,document,note} --from-ref-id ID \
        --to-ref-type {chunk,document,note} --to-ref-id ID \
        --relation-type TEXT [--weight FLOAT]

`upsert` prints the resulting Pointer node id as {"id": ...}. `link` upserts both ends (reusing
the same logic `upsert` uses), then checks whether an edge with this exact relation_type already
exists from the "from" pointer to the "to" pointer (paginating through every out-edge of that
relation_type - create_edge is NOT deduplicated by the engine, see ../graph-model.md's
idempotency rule) and only calls create_edge if none was found. Prints {"from_id", "to_id",
"edge_id", "created"} - "created": false means an equivalent edge already existed and nothing
new was written.

Every subcommand prints exactly one JSON value to stdout on success and exits 0; a prioris-mcp
failure prints a one-line message to stderr and exits 1, via _mcp_client.call_tool.
"""

import argparse
import json
import sys
from typing import Any

import anyio
from _mcp_client import call_tool, client
from prioris_mcp.models.graph import GraphWriteResult, NeighborsResult

_NEIGHBORS_PAGE_SIZE = 50


def _parse_metadata(pairs: list[str]) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            sys.exit(f"--metadata expects KEY=VALUE, got: {pair!r}")
        key, _, value = pair.partition("=")
        metadata[key] = value
    return metadata


async def _upsert(
    c: Any, ref_type: str, ref_id: str, metadata: dict[str, str] | None
) -> str:
    result = await call_tool(
        c,
        "research_graph_write",
        {
            "op": "upsert_pointer",
            "ref_type": ref_type,
            "ref_id": ref_id,
            "metadata": metadata or None,
        },
        GraphWriteResult,
    )
    return result.id


async def _find_existing_edge(
    c: Any, from_id: str, to_id: str, relation_type: str
) -> str | None:
    offset = 0
    while True:
        page = await call_tool(
            c,
            "research_graph_query",
            {
                "op": "neighbors",
                "node_id": from_id,
                "direction": "out",
                "relation_type": relation_type,
                "offset": offset,
                "limit": _NEIGHBORS_PAGE_SIZE,
            },
            NeighborsResult,
        )
        for hop in page.matches:
            if hop.node.id == to_id:
                return hop.edge.id
        if len(page.matches) < _NEIGHBORS_PAGE_SIZE:
            return None
        offset += _NEIGHBORS_PAGE_SIZE


async def cmd_upsert(args: argparse.Namespace) -> int:
    async with client() as c:
        node_id = await _upsert(
            c, args.ref_type, args.ref_id, _parse_metadata(args.metadata)
        )
    print(json.dumps({"id": node_id}))
    return 0


async def cmd_link(args: argparse.Namespace) -> int:
    async with client() as c:
        from_id = await _upsert(c, args.from_ref_type, args.from_ref_id, None)
        to_id = await _upsert(c, args.to_ref_type, args.to_ref_id, None)
        existing_edge_id = await _find_existing_edge(
            c, from_id, to_id, args.relation_type
        )
        if existing_edge_id is not None:
            print(
                json.dumps(
                    {
                        "from_id": from_id,
                        "to_id": to_id,
                        "edge_id": existing_edge_id,
                        "created": False,
                    }
                )
            )
            return 0
        result = await call_tool(
            c,
            "research_graph_write",
            {
                "op": "create_edge",
                "from_id": from_id,
                "to_id": to_id,
                "relation_type": args.relation_type,
                "weight": args.weight,
            },
            GraphWriteResult,
        )
    print(
        json.dumps(
            {"from_id": from_id, "to_id": to_id, "edge_id": result.id, "created": True}
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    upsert_p = sub.add_parser("upsert")
    upsert_p.add_argument(
        "--ref-type", required=True, choices=["chunk", "document", "note"]
    )
    upsert_p.add_argument("--ref-id", required=True)
    upsert_p.add_argument("--metadata", action="extend", nargs="+", default=[])

    link_p = sub.add_parser("link")
    link_p.add_argument(
        "--from-ref-type", required=True, choices=["chunk", "document", "note"]
    )
    link_p.add_argument("--from-ref-id", required=True)
    link_p.add_argument(
        "--to-ref-type", required=True, choices=["chunk", "document", "note"]
    )
    link_p.add_argument("--to-ref-id", required=True)
    link_p.add_argument("--relation-type", required=True)
    link_p.add_argument("--weight", type=float, default=None)

    return parser


_HANDLERS = {"upsert": cmd_upsert, "link": cmd_link}


def main() -> int:
    args = build_parser().parse_args()
    return anyio.run(_HANDLERS[args.command], args)


if __name__ == "__main__":
    raise SystemExit(main())
