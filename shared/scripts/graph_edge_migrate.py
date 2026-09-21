"""Deterministic CLI to re-point every edge touching one node onto another, then optionally
delete the first node.

The mechanical half of both manage-graph's "merge concept A into B" and "promote a stub Concept
to a Pointer" operations (see ../graph-model.md) - relation_type is never endpoint-type-
constrained in this graph (any Pointer/Concept combination is valid on the one generic edge
table), so "repointing" an edge never needs to change its relation_type, only which node id it
names. There is no engine primitive to move an edge's endpoint in place (update_edge only
touches relation_type/weight/metadata) - this script recreates each edge instead, then relies
on delete_node's own cascade to clean up the originals.

Usage:
    uv run --project <plugin root> python shared/scripts/graph_edge_migrate.py migrate \
        --from-node-id OLD --to-node-id NEW [--delete-old]

Enumerates every edge touching OLD (paginated), recreates each on NEW with the same
relation_type/weight/metadata and the same direction relative to its other endpoint, then, only
if --delete-old is given, deletes OLD (cascading away the original edges). Without --delete-old,
OLD is left in place with duplicate edges now also on NEW - useful for a dry-run-then-confirm
flow where the caller wants to see the migration's effect before committing to the delete.

Prints {"from_node_id", "to_node_id", "migrated_edge_ids": [...], "deleted_old": bool}. Exits 1
on any prioris-mcp failure via _mcp_client.call_tool.
"""

import argparse
import json
from typing import Any

import anyio
from _mcp_client import call_tool, client
from prioris_mcp.models.graph import GraphWriteResult, NeighborsResult

_NEIGHBORS_PAGE_SIZE = 50


async def _collect_incident_edges(c: Any, node_id: str) -> list[dict]:
    edges: dict[str, dict] = {}
    offset = 0
    while True:
        page = await call_tool(
            c,
            "research_graph_query",
            {
                "op": "neighbors",
                "node_id": node_id,
                "direction": "both",
                "offset": offset,
                "limit": _NEIGHBORS_PAGE_SIZE,
            },
            NeighborsResult,
        )
        for hop in page.matches:
            edges[hop.edge.id] = {
                "from_id": hop.edge.from_id,
                "to_id": hop.edge.to_id,
                "relation_type": hop.edge.relation_type,
                "weight": hop.edge.weight,
                "metadata": hop.edge.metadata,
            }
        if len(page.matches) < _NEIGHBORS_PAGE_SIZE:
            break
        offset += _NEIGHBORS_PAGE_SIZE
    return list(edges.values())


async def cmd_migrate(args: argparse.Namespace) -> int:
    async with client() as c:
        incident = await _collect_incident_edges(c, args.from_node_id)
        migrated_ids: list[str] = []
        for edge in incident:
            new_from = (
                args.to_node_id
                if edge["from_id"] == args.from_node_id
                else edge["from_id"]
            )
            new_to = (
                args.to_node_id if edge["to_id"] == args.from_node_id else edge["to_id"]
            )
            result = await call_tool(
                c,
                "research_graph_write",
                {
                    "op": "create_edge",
                    "from_id": new_from,
                    "to_id": new_to,
                    "relation_type": edge["relation_type"],
                    "weight": edge["weight"],
                    "metadata": edge["metadata"] or None,
                },
                GraphWriteResult,
            )
            migrated_ids.append(result.id)

        deleted_old = False
        if args.delete_old:
            await call_tool(
                c,
                "research_graph_write",
                {"op": "delete_node", "node_id": args.from_node_id},
                GraphWriteResult,
            )
            deleted_old = True

    print(
        json.dumps(
            {
                "from_node_id": args.from_node_id,
                "to_node_id": args.to_node_id,
                "migrated_edge_ids": migrated_ids,
                "deleted_old": deleted_old,
            }
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    migrate_p = sub.add_parser("migrate")
    migrate_p.add_argument("--from-node-id", required=True)
    migrate_p.add_argument("--to-node-id", required=True)
    migrate_p.add_argument("--delete-old", action="store_true")

    return parser


_HANDLERS = {"migrate": cmd_migrate}


def main() -> int:
    args = build_parser().parse_args()
    return anyio.run(_HANDLERS[args.command], args)


if __name__ == "__main__":
    raise SystemExit(main())
