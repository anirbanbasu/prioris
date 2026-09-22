"""Deterministic CLI to export the corpus-wide graph and render a static visualization.

Wraps the read-only research://graph/export{?format} resource (see ../graph-model.md) -
deliberately the one unbounded, whole-graph read in this plugin's graph tooling, reserved for an
explicit export/visualize request rather than anything routine skills call automatically.
concept-explore's "whole graph" scope option shells out to this script rather than working
around research_graph_analyze's seed-bounded design.

Usage:
    uv run --project <plugin root> python shared/scripts/graph_export.py export \
        [--format {cypher_json,graphml}] [--out PATH]

    uv run --project <plugin root> python shared/scripts/graph_export.py visualize \
        --out PATH.png [--layout {spring,kamada_kawai}]

`export` with no --out prints the export to stdout (JSON for cypher_json, raw GraphML XML for
graphml); with --out, writes to that path instead and prints a one-line confirmation to stderr.

`visualize` always fetches cypher_json, builds a NetworkX MultiDiGraph locally (concept nodes
labeled by `label`, pointer nodes labeled `ref_type:ref_id`, edges labeled by `relation_type`),
and renders it to a PNG at --out via matplotlib's non-interactive Agg backend - safe to run
headless. --layout picks the NetworkX layout algorithm.
"""

import argparse
import sys
from typing import cast

import anyio
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import networkx as nx
from _mcp_client import client, read_resource
from fastmcp import Client
from mcp.shared.exceptions import MCPError
from mcp.types import TextResourceContents
from prioris_mcp.models.graph import ConceptNode, GraphEdge, GraphNode
from pydantic import BaseModel


class _ExportedGraph(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


async def _fetch_graphml(c: Client) -> str:
    try:
        contents = await c.read_resource("research://graph/export?format=graphml")
    except MCPError as exc:
        sys.exit(str(exc))
    return cast(TextResourceContents, contents[0]).text


def _node_label(node: GraphNode) -> str:
    if isinstance(node, ConceptNode):
        return node.label
    return f"{node.ref_type}:{node.ref_id}"


def _materialize(graph: _ExportedGraph) -> nx.MultiDiGraph:
    g = nx.MultiDiGraph()
    for node in graph.nodes:
        g.add_node(node.id, label=_node_label(node))
    for edge in graph.edges:
        g.add_edge(
            edge.from_id, edge.to_id, key=edge.id, relation_type=edge.relation_type
        )
    return g


async def cmd_export(args: argparse.Namespace) -> int:
    async with client() as c:
        if args.format == "cypher_json":
            exported = await read_resource(
                c, "research://graph/export?format=cypher_json", _ExportedGraph
            )
            output = exported.model_dump_json()
        else:
            output = await _fetch_graphml(c)
    if args.out:
        async with await anyio.open_file(args.out, "w") as f:
            await f.write(output)
        print(f"wrote {args.format} export to {args.out}", file=sys.stderr)
    else:
        print(output)
    return 0


async def cmd_visualize(args: argparse.Namespace) -> int:
    async with client() as c:
        exported = await read_resource(
            c, "research://graph/export?format=cypher_json", _ExportedGraph
        )
    g = _materialize(exported)
    layout_fn = (
        nx.kamada_kawai_layout if args.layout == "kamada_kawai" else nx.spring_layout
    )
    positions = layout_fn(g)
    labels = {node_id: data["label"] for node_id, data in g.nodes(data=True)}
    # Parallel edges between the same pair collapse to one label here - an accepted cosmetic
    # simplification for a diagnostic visualization, not a functional-correctness concern.
    edge_labels = {(u, v): data["relation_type"] for u, v, data in g.edges(data=True)}

    fig, ax = plt.subplots(figsize=(12, 12))
    nx.draw_networkx_nodes(g, positions, ax=ax, node_size=400)
    nx.draw_networkx_edges(g, positions, ax=ax, arrows=True)
    nx.draw_networkx_labels(g, positions, labels=labels, ax=ax, font_size=7)
    nx.draw_networkx_edge_labels(
        g, positions, edge_labels=edge_labels, ax=ax, font_size=6
    )
    ax.axis("off")
    fig.savefig(args.out, format="png", bbox_inches="tight")
    plt.close(fig)
    print(f"wrote visualization to {args.out}", file=sys.stderr)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    export_p = sub.add_parser("export")
    export_p.add_argument(
        "--format", choices=["cypher_json", "graphml"], default="cypher_json"
    )
    export_p.add_argument("--out", default=None)

    visualize_p = sub.add_parser("visualize")
    visualize_p.add_argument("--out", required=True)
    visualize_p.add_argument(
        "--layout", choices=["spring", "kamada_kawai"], default="spring"
    )

    return parser


_HANDLERS = {"export": cmd_export, "visualize": cmd_visualize}


def main() -> int:
    args = build_parser().parse_args()
    return anyio.run(_HANDLERS[args.command], args)


if __name__ == "__main__":
    raise SystemExit(main())
