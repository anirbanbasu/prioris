import json
import sys
from types import SimpleNamespace

import anyio
import manage_discovery as md
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError


def _hit(
    openalex_id: str, abstract: str | None, work_type: str | None = "article"
) -> dict:
    return {
        "openalex_id": openalex_id,
        "title": "T",
        "abstract": abstract,
        "authors": [],
        "publication_year": 2026,
        "doi": None,
        "work_type": work_type,
        "score": 0.9,
        "fetch_route": {
            "kind": "manual_upload",
            "provider": None,
            "identifier": None,
            "pdf_url": None,
        },
    }


def test_needs_condensation_true_over_300_words() -> None:
    assert md._needs_condensation(" ".join(["word"] * 301)) is True


def test_needs_condensation_false_at_or_under_300_words() -> None:
    assert md._needs_condensation(" ".join(["word"] * 300)) is False


def test_needs_condensation_false_for_null_abstract() -> None:
    assert md._needs_condensation(None) is False


def test_run_marks_needs_condensation_per_hit(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    short_hit = _hit("W1", "short abstract")
    long_hit = _hit("W2", " ".join(["word"] * 400))

    async def fake_call_tool(
        self: Client, name: str, arguments: dict | None = None, **kwargs: object
    ) -> object:
        return SimpleNamespace(
            structured_content={
                "hits": [short_hit, long_hit],
                "page": 1,
                "per_page": 7,
                "total": 2,
                "has_more": False,
            },
            data=None,
        )

    monkeypatch.setattr(Client, "call_tool", fake_call_tool)

    args = md.build_parser().parse_args(["search", "--query", "q"])
    assert anyio.run(md.run, args) == 0
    output = json.loads(capsys.readouterr().out)
    by_id = {h["openalex_id"]: h for h in output["hits"]}
    assert by_id["W1"]["needs_condensation"] is False
    assert by_id["W2"]["needs_condensation"] is True


def test_run_include_work_types_attaches_name_and_description(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    async def fake_call_tool(
        self: Client, name: str, arguments: dict | None = None, **kwargs: object
    ) -> object:
        return SimpleNamespace(
            structured_content={
                "hits": [_hit("W1", "short", work_type="article")],
                "page": 1,
                "per_page": 7,
                "total": 1,
                "has_more": False,
            },
            data=None,
        )

    async def fake_read_resource(
        self: Client, uri: str, **kwargs: object
    ) -> list[object]:
        payload = {
            "types": [
                {
                    "code": "article",
                    "name": "Article",
                    "description": "A journal article.",
                }
            ]
        }
        return [SimpleNamespace(text=json.dumps(payload))]

    monkeypatch.setattr(Client, "call_tool", fake_call_tool)
    monkeypatch.setattr(Client, "read_resource", fake_read_resource)

    args = md.build_parser().parse_args(
        ["search", "--query", "q", "--include-work-types"]
    )
    assert anyio.run(md.run, args) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["hits"][0]["work_type_name"] == "Article"
    assert output["hits"][0]["work_type_description"] == "A journal article."


def test_run_all_loops_pages(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    pages = [
        {
            "hits": [_hit("W1", "a")],
            "page": 1,
            "per_page": 1,
            "total": 2,
            "has_more": True,
        },
        {
            "hits": [_hit("W2", "b")],
            "page": 2,
            "per_page": 1,
            "total": 2,
            "has_more": False,
        },
    ]

    async def fake_call_tool(
        self: Client, name: str, arguments: dict | None = None, **kwargs: object
    ) -> object:
        return SimpleNamespace(structured_content=pages.pop(0), data=None)

    monkeypatch.setattr(Client, "call_tool", fake_call_tool)

    args = md.build_parser().parse_args(["search", "--query", "q", "--all"])
    assert anyio.run(md.run, args) == 0
    output = json.loads(capsys.readouterr().out)
    assert [h["openalex_id"] for h in output["hits"]] == ["W1", "W2"]
    assert output["has_more"] is False


def test_run_stops_at_max_pages(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    async def fake_call_tool(
        self: Client, name: str, arguments: dict | None = None, **kwargs: object
    ) -> object:
        return SimpleNamespace(
            structured_content={
                "hits": [_hit("W1", "a")],
                "page": 1,
                "per_page": 1,
                "total": 50,
                "has_more": True,
            },
            data=None,
        )

    monkeypatch.setattr(Client, "call_tool", fake_call_tool)

    args = md.build_parser().parse_args(
        ["search", "--query", "q", "--all", "--max-pages", "2"]
    )
    assert anyio.run(md.run, args) == 0
    assert "stopped after 2 pages" in capsys.readouterr().err


def test_run_exits_on_tool_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_call_tool(
        self: Client, name: str, arguments: dict | None = None, **kwargs: object
    ) -> object:
        raise ToolError("boom")

    monkeypatch.setattr(Client, "call_tool", fake_call_tool)

    args = md.build_parser().parse_args(["search", "--query", "q"])
    with pytest.raises(SystemExit, match="boom"):
        anyio.run(md.run, args)


def test_main_entry_point(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    async def fake_call_tool(
        self: Client, name: str, arguments: dict | None = None, **kwargs: object
    ) -> object:
        return SimpleNamespace(
            structured_content={
                "hits": [_hit("W1", "short abstract")],
                "page": 1,
                "per_page": 7,
                "total": 1,
                "has_more": False,
            },
            data=None,
        )

    monkeypatch.setattr(Client, "call_tool", fake_call_tool)
    monkeypatch.setattr(
        sys, "argv", ["manage_discovery.py", "search", "--query", "test"]
    )

    assert md.main() == 0
    output = json.loads(capsys.readouterr().out)
    assert output["total"] == 1
