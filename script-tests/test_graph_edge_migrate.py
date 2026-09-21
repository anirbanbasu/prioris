import json

import anyio
import graph_edge_migrate as gem
import pytest
from _mcp_client import call_tool, client
from fastmcp import Client
from fastmcp.exceptions import ToolError
from prioris_mcp.models.graph import GraphWriteResult, NeighborsResult


async def _make_pointer(c: Client, ref_type: str, ref_id: str) -> str:
    result = await call_tool(
        c,
        "research_graph_write",
        {"op": "upsert_pointer", "ref_type": ref_type, "ref_id": ref_id},
        GraphWriteResult,
    )
    return result.id


async def _make_concept(c: Client, label: str) -> str:
    result = await call_tool(
        c,
        "research_graph_write",
        {"op": "create_concept", "label": label},
        GraphWriteResult,
    )
    return result.id


def test_migrate_recreates_edges_without_deleting_by_default(
    capsys: pytest.CaptureFixture,
) -> None:
    async def setup() -> tuple[str, str]:
        async with client() as c:
            old = await _make_concept(c, "gradient checkpointing")
            new = await _make_concept(c, "activation checkpointing")
            neighbor_out = await _make_pointer(c, "document", "arxiv:migrate-out")
            neighbor_in = await _make_pointer(c, "document", "arxiv:migrate-in")
            await call_tool(
                c,
                "research_graph_write",
                {
                    "op": "create_edge",
                    "from_id": old,
                    "to_id": neighbor_out,
                    "relation_type": "about",
                },
                GraphWriteResult,
            )
            await call_tool(
                c,
                "research_graph_write",
                {
                    "op": "create_edge",
                    "from_id": neighbor_in,
                    "to_id": old,
                    "relation_type": "references",
                },
                GraphWriteResult,
            )
            return old, new

    old_id, new_id = anyio.run(setup)

    args = gem.build_parser().parse_args(
        ["migrate", "--from-node-id", old_id, "--to-node-id", new_id]
    )
    assert anyio.run(gem.cmd_migrate, args) == 0
    result = json.loads(capsys.readouterr().out)
    assert len(result["migrated_edge_ids"]) == 2
    assert result["deleted_old"] is False

    async def verify() -> tuple[int, int]:
        async with client() as c:
            old_neighbors = await call_tool(
                c,
                "research_graph_query",
                {"op": "neighbors", "node_id": old_id, "direction": "both"},
                NeighborsResult,
            )
            new_neighbors = await call_tool(
                c,
                "research_graph_query",
                {"op": "neighbors", "node_id": new_id, "direction": "both"},
                NeighborsResult,
            )
            return len(old_neighbors.matches), len(new_neighbors.matches)

    old_count, new_count = anyio.run(verify)
    assert old_count == 2
    assert new_count == 2


def test_migrate_with_delete_old_removes_source_node(
    capsys: pytest.CaptureFixture,
) -> None:
    async def setup() -> tuple[str, str]:
        async with client() as c:
            old = await _make_concept(c, "stub concept")
            new = await _make_concept(c, "real concept")
            neighbor = await _make_pointer(c, "document", "arxiv:migrate-delete")
            await call_tool(
                c,
                "research_graph_write",
                {
                    "op": "create_edge",
                    "from_id": old,
                    "to_id": neighbor,
                    "relation_type": "about",
                },
                GraphWriteResult,
            )
            return old, new

    old_id, new_id = anyio.run(setup)

    args = gem.build_parser().parse_args(
        ["migrate", "--from-node-id", old_id, "--to-node-id", new_id, "--delete-old"]
    )
    assert anyio.run(gem.cmd_migrate, args) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["deleted_old"] is True

    async def get_deleted_node() -> None:
        async with client() as c:
            await call_tool(
                c, "research_graph_query", {"op": "get_node", "node_id": old_id}
            )

    with pytest.raises(SystemExit):
        anyio.run(get_deleted_node)


def test_migrate_preserves_relation_type_and_weight(
    capsys: pytest.CaptureFixture,
) -> None:
    async def setup() -> tuple[str, str]:
        async with client() as c:
            old = await _make_concept(c, "old label")
            new = await _make_concept(c, "new label")
            neighbor = await _make_pointer(c, "document", "arxiv:migrate-weight")
            await call_tool(
                c,
                "research_graph_write",
                {
                    "op": "create_edge",
                    "from_id": old,
                    "to_id": neighbor,
                    "relation_type": "about",
                    "weight": 0.75,
                },
                GraphWriteResult,
            )
            return old, new

    old_id, new_id = anyio.run(setup)
    args = gem.build_parser().parse_args(
        ["migrate", "--from-node-id", old_id, "--to-node-id", new_id]
    )
    assert anyio.run(gem.cmd_migrate, args) == 0

    async def read_new_edge() -> tuple[str, float | None]:
        async with client() as c:
            neighbors = await call_tool(
                c,
                "research_graph_query",
                {"op": "neighbors", "node_id": new_id, "direction": "out"},
                NeighborsResult,
            )
            edge = neighbors.matches[0].edge
            return edge.relation_type, edge.weight

    relation_type, weight = anyio.run(read_new_edge)
    assert relation_type == "about"
    assert weight == 0.75


def test_migrate_exits_on_tool_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_call_tool(
        self: Client, name: str, arguments: dict | None = None, **kwargs: object
    ) -> object:
        raise ToolError("not_found: node does not exist")

    monkeypatch.setattr(Client, "call_tool", fake_call_tool)

    args = gem.build_parser().parse_args(
        ["migrate", "--from-node-id", "missing", "--to-node-id", "also-missing"]
    )
    with pytest.raises(SystemExit, match="not_found"):
        anyio.run(gem.cmd_migrate, args)


def test_migrate_paginates_through_many_edges(capsys: pytest.CaptureFixture) -> None:
    async def setup() -> tuple[str, str]:
        async with client() as c:
            old = await _make_concept(c, "heavily-connected concept")
            new = await _make_concept(c, "heavily-connected replacement")
            for i in range(gem._NEIGHBORS_PAGE_SIZE):
                neighbor = await _make_pointer(c, "document", f"arxiv:migrate-page-{i}")
                await call_tool(
                    c,
                    "research_graph_write",
                    {
                        "op": "create_edge",
                        "from_id": old,
                        "to_id": neighbor,
                        "relation_type": "about",
                    },
                    GraphWriteResult,
                )
            return old, new

    old_id, new_id = anyio.run(setup)

    args = gem.build_parser().parse_args(
        ["migrate", "--from-node-id", old_id, "--to-node-id", new_id]
    )
    assert anyio.run(gem.cmd_migrate, args) == 0
    result = json.loads(capsys.readouterr().out)
    assert len(result["migrated_edge_ids"]) == gem._NEIGHBORS_PAGE_SIZE


def test_main_function(
    capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def setup() -> tuple[str, str]:
        async with client() as c:
            old = await _make_concept(c, "main-test old")
            new = await _make_concept(c, "main-test new")
            return old, new

    old_id, new_id = anyio.run(setup)
    monkeypatch.setattr(
        "sys.argv",
        [
            "graph_edge_migrate.py",
            "migrate",
            "--from-node-id",
            old_id,
            "--to-node-id",
            new_id,
        ],
    )
    assert gem.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["migrated_edge_ids"] == []
