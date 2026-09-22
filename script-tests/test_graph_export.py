import json
from pathlib import Path

import anyio
import graph_export as ge
import pytest
from _mcp_client import call_tool, client
from fastmcp import Client
from mcp.shared.exceptions import MCPError
from prioris_mcp.models.graph import ConceptNode, GraphWriteResult, PointerNode


async def _seed_small_graph() -> tuple[str, str]:
    async with client() as c:
        concept = await call_tool(
            c,
            "research_graph_write",
            {"op": "create_concept", "label": "export test concept"},
            GraphWriteResult,
        )
        pointer = await call_tool(
            c,
            "research_graph_write",
            {
                "op": "upsert_pointer",
                "ref_type": "document",
                "ref_id": "arxiv:export-test",
            },
            GraphWriteResult,
        )
        await call_tool(
            c,
            "research_graph_write",
            {
                "op": "create_edge",
                "from_id": pointer.id,
                "to_id": concept.id,
                "relation_type": "about",
            },
            GraphWriteResult,
        )
        return concept.id, pointer.id


def test_export_cypher_json_to_stdout(capsys: pytest.CaptureFixture) -> None:
    concept_id, pointer_id = anyio.run(_seed_small_graph)
    args = ge.build_parser().parse_args(["export"])
    assert anyio.run(ge.cmd_export, args) == 0
    payload = json.loads(capsys.readouterr().out)
    node_ids = {n["id"] for n in payload["nodes"]}
    assert concept_id in node_ids
    assert pointer_id in node_ids


def test_export_cypher_json_to_file(tmp_path: Path) -> None:
    anyio.run(_seed_small_graph)
    out_path = tmp_path / "export.json"
    args = ge.build_parser().parse_args(["export", "--out", str(out_path)])
    assert anyio.run(ge.cmd_export, args) == 0
    payload = json.loads(out_path.read_text())
    assert "nodes" in payload and "edges" in payload


def test_export_graphml_to_file(tmp_path: Path) -> None:
    anyio.run(_seed_small_graph)
    out_path = tmp_path / "export.graphml"
    args = ge.build_parser().parse_args(
        ["export", "--format", "graphml", "--out", str(out_path)]
    )
    assert anyio.run(ge.cmd_export, args) == 0
    content = out_path.read_text()
    assert "<graphml" in content


def test_visualize_writes_png_file(tmp_path: Path) -> None:
    anyio.run(_seed_small_graph)
    out_path = tmp_path / "graph.png"
    args = ge.build_parser().parse_args(["visualize", "--out", str(out_path)])
    assert anyio.run(ge.cmd_visualize, args) == 0
    assert out_path.exists()
    assert out_path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_node_label_uses_concept_label_or_pointer_ref() -> None:
    concept = ConceptNode(
        kind="concept",
        id="c1",
        label="my concept",
        aliases=[],
        description=None,
        metadata={},
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    pointer = PointerNode(
        kind="pointer",
        id="p1",
        ref_type="document",
        ref_id="arxiv:1",
        metadata={},
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    assert ge._node_label(concept) == "my concept"
    assert ge._node_label(pointer) == "document:arxiv:1"


def test_export_exits_on_mcp_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_read_resource(self: Client, uri: str, **kwargs: object) -> object:
        raise MCPError(code=-1, message="not found")

    monkeypatch.setattr(Client, "read_resource", fake_read_resource)
    args = ge.build_parser().parse_args(["export", "--format", "graphml"])
    with pytest.raises(SystemExit):
        anyio.run(ge.cmd_export, args)


def test_main_function(
    capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    anyio.run(_seed_small_graph)
    monkeypatch.setattr("sys.argv", ["graph_export.py", "export"])
    assert ge.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert "nodes" in payload
