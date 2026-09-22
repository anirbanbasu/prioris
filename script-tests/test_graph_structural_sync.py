import json

import anyio
import graph_structural_sync as gss
import pytest
from _mcp_client import call_tool, client
from fastmcp import Client
from fastmcp.exceptions import ToolError
from prioris_mcp.models.graph import GraphWriteResult


def test_parse_metadata_splits_on_first_equals() -> None:
    assert gss._parse_metadata(["a=1", "b=x=y"]) == {"a": "1", "b": "x=y"}


def test_parse_metadata_rejects_missing_equals() -> None:
    with pytest.raises(SystemExit, match="KEY=VALUE"):
        gss._parse_metadata(["not-a-pair"])


def test_build_parser_link_requires_all_ref_fields() -> None:
    with pytest.raises(SystemExit):
        gss.build_parser().parse_args(["link", "--from-ref-type", "note"])


def test_upsert_prints_node_id(capsys: pytest.CaptureFixture) -> None:
    args = gss.build_parser().parse_args(
        ["upsert", "--ref-type", "document", "--ref-id", "arxiv:9999.00001"]
    )
    assert anyio.run(gss.cmd_upsert, args) == 0
    result = json.loads(capsys.readouterr().out)
    assert "id" in result


def test_upsert_is_idempotent_same_ref_returns_same_id(
    capsys: pytest.CaptureFixture,
) -> None:
    args = gss.build_parser().parse_args(
        ["upsert", "--ref-type", "document", "--ref-id", "arxiv:9999.00002"]
    )
    assert anyio.run(gss.cmd_upsert, args) == 0
    first_id = json.loads(capsys.readouterr().out)["id"]
    assert anyio.run(gss.cmd_upsert, args) == 0
    second_id = json.loads(capsys.readouterr().out)["id"]
    assert first_id == second_id


def test_link_creates_new_edge_between_two_new_pointers(
    capsys: pytest.CaptureFixture,
) -> None:
    args = gss.build_parser().parse_args(
        [
            "link",
            "--from-ref-type",
            "note",
            "--from-ref-id",
            "note-1",
            "--to-ref-type",
            "document",
            "--to-ref-id",
            "arxiv:9999.00003",
            "--relation-type",
            "annotates",
        ]
    )
    assert anyio.run(gss.cmd_link, args) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["created"] is True
    assert result["from_id"] and result["to_id"] and result["edge_id"]


def test_link_is_idempotent_second_call_reuses_edge(
    capsys: pytest.CaptureFixture,
) -> None:
    def build_args() -> object:
        return gss.build_parser().parse_args(
            [
                "link",
                "--from-ref-type",
                "note",
                "--from-ref-id",
                "note-2",
                "--to-ref-type",
                "document",
                "--to-ref-id",
                "arxiv:9999.00004",
                "--relation-type",
                "annotates",
            ]
        )

    assert anyio.run(gss.cmd_link, build_args()) == 0
    first = json.loads(capsys.readouterr().out)
    assert first["created"] is True

    assert anyio.run(gss.cmd_link, build_args()) == 0
    second = json.loads(capsys.readouterr().out)
    assert second["created"] is False
    assert second["edge_id"] == first["edge_id"]


def test_link_different_relation_type_creates_separate_edge(
    capsys: pytest.CaptureFixture,
) -> None:
    common = [
        "--from-ref-type",
        "note",
        "--from-ref-id",
        "note-3",
        "--to-ref-type",
        "document",
        "--to-ref-id",
        "arxiv:9999.00005",
    ]
    args_a = gss.build_parser().parse_args(
        ["link", *common, "--relation-type", "annotates"]
    )
    assert anyio.run(gss.cmd_link, args_a) == 0
    first = json.loads(capsys.readouterr().out)

    args_b = gss.build_parser().parse_args(
        ["link", *common, "--relation-type", "references"]
    )
    assert anyio.run(gss.cmd_link, args_b) == 0
    second = json.loads(capsys.readouterr().out)

    assert first["edge_id"] != second["edge_id"]


def test_find_existing_edge_paginates_past_first_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(gss, "_NEIGHBORS_PAGE_SIZE", 2)

    async def run() -> tuple[list[str | None], str | None]:
        async with client() as c:
            from_id = await gss._upsert(c, "note", "note-page-test", None)
            to_ids = []
            for i in range(4):
                to_id = await gss._upsert(c, "document", f"arxiv:page-test-{i}", None)
                await call_tool(
                    c,
                    "research_graph_write",
                    {
                        "op": "create_edge",
                        "from_id": from_id,
                        "to_id": to_id,
                        "relation_type": "annotates",
                    },
                    GraphWriteResult,
                )
                to_ids.append(to_id)
            found = [
                await gss._find_existing_edge(c, from_id, to_id, "annotates")
                for to_id in to_ids
            ]
            # No match anywhere: forces every page to be walked to exhaustion, whatever
            # order the backend returns them in - the `found` list above cannot be relied
            # on to land on a later page, since neighbors' ordering is not specified.
            missing = await gss._find_existing_edge(
                c, from_id, "no-such-node", "annotates"
            )
            return found, missing

    found_edge_ids, missing_edge_id = anyio.run(run)
    assert all(edge_id is not None for edge_id in found_edge_ids)
    assert missing_edge_id is None


def test_link_exits_on_tool_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_call_tool(
        self: Client, name: str, arguments: dict | None = None, **kwargs: object
    ) -> object:
        raise ToolError("invalid_request: bad ref_type")

    monkeypatch.setattr(Client, "call_tool", fake_call_tool)

    args = gss.build_parser().parse_args(
        [
            "link",
            "--from-ref-type",
            "note",
            "--from-ref-id",
            "note-x",
            "--to-ref-type",
            "document",
            "--to-ref-id",
            "arxiv:x",
            "--relation-type",
            "annotates",
        ]
    )
    with pytest.raises(SystemExit, match="invalid_request"):
        anyio.run(gss.cmd_link, args)


def test_main_function(
    capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "graph_structural_sync.py",
            "upsert",
            "--ref-type",
            "document",
            "--ref-id",
            "arxiv:9999.00006",
        ],
    )
    assert gss.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert "id" in result
