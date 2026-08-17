import json
import sys
from types import SimpleNamespace

import anyio
import manage_arxiv as ma
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError


def _record(arxiv_id: str) -> dict:
    return {
        "arxiv_id": arxiv_id,
        "title": "T",
        "authors": [],
        "abstract": "A",
        "categories": ["cs.AI"],
        "primary_category": "cs.AI",
        "published": "2026-01-01",
        "updated": "2026-01-01",
        "pdf_url": None,
        "doi": None,
        "journal_ref": None,
        "comment": None,
    }


def test_cmd_search_passes_arguments_through(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    async def fake_call_tool(
        self: Client, name: str, arguments: dict | None = None, **kwargs: object
    ) -> object:
        assert name == "research_arxiv_search"
        assert arguments is not None
        assert arguments["query"] == "quantum trust"
        assert "sort_by" not in arguments
        assert "sort_order" not in arguments
        return SimpleNamespace(
            structured_content={"results": [_record("1234.5678")], "total_results": 1},
            data=None,
        )

    monkeypatch.setattr(Client, "call_tool", fake_call_tool)

    args = ma.build_parser().parse_args(["search", "--query", "quantum trust"])
    assert anyio.run(ma.cmd_search, args) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["results"][0]["arxiv_id"] == "1234.5678"


def test_cmd_search_includes_sort_args_when_set(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    async def fake_call_tool(
        self: Client, name: str, arguments: dict | None = None, **kwargs: object
    ) -> object:
        assert name == "research_arxiv_search"
        assert arguments is not None
        assert arguments["query"] == "quantum trust"
        assert arguments["sort_by"] == "submittedDate"
        assert arguments["sort_order"] == "ascending"
        return SimpleNamespace(
            structured_content={"results": [_record("1234.5678")], "total_results": 1},
            data=None,
        )

    monkeypatch.setattr(Client, "call_tool", fake_call_tool)

    args = ma.build_parser().parse_args(
        [
            "search",
            "--query",
            "quantum trust",
            "--sort-by",
            "submittedDate",
            "--sort-order",
            "ascending",
        ]
    )
    assert anyio.run(ma.cmd_search, args) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["results"][0]["arxiv_id"] == "1234.5678"


def test_build_parser_rejects_invalid_sort_by() -> None:
    with pytest.raises(SystemExit):
        ma.build_parser().parse_args(["search", "--query", "q", "--sort-by", "JUNK"])


def test_build_parser_rejects_invalid_sort_order() -> None:
    with pytest.raises(SystemExit):
        ma.build_parser().parse_args(["search", "--query", "q", "--sort-order", "JUNK"])


def test_cmd_list_top_n_passes_categories(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    async def fake_call_tool(
        self: Client, name: str, arguments: dict | None = None, **kwargs: object
    ) -> object:
        assert name == "research_arxiv_list_top_n"
        assert arguments is not None
        assert arguments["include_categories"] == ["cs.CL"]
        assert arguments["exclude_categories"] == ["stat.ML"]
        return SimpleNamespace(
            structured_content={"results": [], "total_results": 0}, data=None
        )

    monkeypatch.setattr(Client, "call_tool", fake_call_tool)

    args = ma.build_parser().parse_args(
        [
            "list-top-n",
            "--include-category",
            "cs.CL",
            "--n",
            "7",
            "--exclude-category",
            "stat.ML",
        ]
    )
    assert anyio.run(ma.cmd_list_top_n, args) == 0


def test_cmd_fetch_metadata(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    async def fake_call_tool(
        self: Client, name: str, arguments: dict | None = None, **kwargs: object
    ) -> object:
        assert arguments is not None
        assert arguments["arxiv_ids"] == ["1234.5678"]
        return SimpleNamespace(
            structured_content={"results": [_record("1234.5678")], "not_found": []},
            data=None,
        )

    monkeypatch.setattr(Client, "call_tool", fake_call_tool)

    args = ma.build_parser().parse_args(["fetch-metadata", "--arxiv-id", "1234.5678"])
    assert anyio.run(ma.cmd_fetch_metadata, args) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["not_found"] == []


def test_cmd_categories_lookup_by_code(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    async def fake_read_resource(
        self: Client, uri: str, **kwargs: object
    ) -> list[object]:
        payload = {
            "categories": [{"code": "cs.CL", "name": "Computation and Language"}]
        }
        return [SimpleNamespace(text=json.dumps(payload))]

    monkeypatch.setattr(Client, "read_resource", fake_read_resource)

    args = ma.build_parser().parse_args(["categories", "--code", "cs.CL"])
    assert anyio.run(ma.cmd_categories, args) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["name"] == "Computation and Language"


def test_cmd_categories_unknown_code_exits(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_read_resource(
        self: Client, uri: str, **kwargs: object
    ) -> list[object]:
        return [SimpleNamespace(text=json.dumps({"categories": []}))]

    monkeypatch.setattr(Client, "read_resource", fake_read_resource)

    args = ma.build_parser().parse_args(["categories", "--code", "nope.XX"])
    with pytest.raises(SystemExit, match="no arXiv category"):
        anyio.run(ma.cmd_categories, args)


def test_cmd_categories_query_filters_by_name(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    async def fake_read_resource(
        self: Client, uri: str, **kwargs: object
    ) -> list[object]:
        payload = {
            "categories": [
                {"code": "cs.CL", "name": "Computation and Language"},
                {"code": "cs.CV", "name": "Computer Vision"},
            ]
        }
        return [SimpleNamespace(text=json.dumps(payload))]

    monkeypatch.setattr(Client, "read_resource", fake_read_resource)

    args = ma.build_parser().parse_args(["categories", "--query", "language"])
    assert anyio.run(ma.cmd_categories, args) == 0
    output = json.loads(capsys.readouterr().out)
    assert [c["code"] for c in output] == ["cs.CL"]


def test_cmd_categories_no_filter_prints_all(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    async def fake_read_resource(
        self: Client, uri: str, **kwargs: object
    ) -> list[object]:
        payload = {
            "categories": [{"code": "cs.CL", "name": "Computation and Language"}]
        }
        return [SimpleNamespace(text=json.dumps(payload))]

    monkeypatch.setattr(Client, "read_resource", fake_read_resource)

    args = ma.build_parser().parse_args(["categories"])
    assert anyio.run(ma.cmd_categories, args) == 0
    output = json.loads(capsys.readouterr().out)
    assert len(output) == 1


def test_cmd_search_exits_on_tool_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_call_tool(
        self: Client, name: str, arguments: dict | None = None, **kwargs: object
    ) -> object:
        raise ToolError("boom")

    monkeypatch.setattr(Client, "call_tool", fake_call_tool)

    args = ma.build_parser().parse_args(["search", "--query", "q"])
    with pytest.raises(SystemExit, match="boom"):
        anyio.run(ma.cmd_search, args)


def test_main_entry_point(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    async def fake_call_tool(
        self: Client, name: str, arguments: dict | None = None, **kwargs: object
    ) -> object:
        assert name == "research_arxiv_search"
        assert arguments is not None
        return SimpleNamespace(
            structured_content={"results": [_record("1234.5678")], "total_results": 1},
            data=None,
        )

    monkeypatch.setattr(Client, "call_tool", fake_call_tool)
    monkeypatch.setattr(sys, "argv", ["manage_arxiv.py", "search", "--query", "test"])

    assert ma.main() == 0
    output = json.loads(capsys.readouterr().out)
    assert output["results"][0]["arxiv_id"] == "1234.5678"
