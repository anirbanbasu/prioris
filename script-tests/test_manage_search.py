import json
import sys
from types import SimpleNamespace

import anyio
import manage_search as ms
import metadata_cache
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError


def _match(identifier: str, score: float) -> dict:
    return {
        "provider": "arxiv",
        "identifier": identifier,
        "format": "pdf",
        "snippet": "...",
        "offset": 0,
        "score": score,
    }


def _vector_match(identifier: str, score: float) -> dict:
    return {
        "provider": "arxiv",
        "identifier": identifier,
        "chunk_id": "chunk-1",
        "format": "pdf",
        "offset": 0,
        "snippet": "...",
        "score": score,
    }


def test_build_parser_defaults() -> None:
    args = ms.build_parser().parse_args(["search", "--query", "q"])
    assert args.mode == "fts"
    assert args.limit == 50
    assert args.min_score is None


def test_run_aggregates_pages_and_filters_by_min_score(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    pages = [
        {
            "fts": {
                "matches": [_match("a", 0.9), _match("b", 0.1)],
                "offset": 0,
                "limit": 2,
                "total": 3,
                "has_more": True,
            },
            "vector": None,
            "index_status": {"vector": "ready"},
        },
        {
            "fts": {
                "matches": [_match("c", 0.5)],
                "offset": 2,
                "limit": 2,
                "total": 3,
                "has_more": False,
            },
            "vector": None,
            "index_status": {"vector": "ready"},
        },
    ]

    async def fake_call_tool(
        self: Client, name: str, arguments: dict | None = None, **kwargs: object
    ) -> object:
        return SimpleNamespace(structured_content=pages.pop(0), data=None)

    monkeypatch.setattr(Client, "call_tool", fake_call_tool)

    args = ms.build_parser().parse_args(
        ["search", "--query", "q", "--all", "--limit", "2", "--min-score", "0.5"]
    )
    assert anyio.run(ms.run, args) == 0
    output = json.loads(capsys.readouterr().out)
    identifiers = [m["identifier"] for m in output["fts"]["matches"]]
    assert identifiers == ["a", "c"]
    assert output["index_status"] == {"vector": "ready"}
    # Last page fetched had has_more False, so the aggregated block should reflect that even
    # though the first page's has_more was True.
    assert output["fts"]["has_more"] is False


def test_run_attaches_titles_from_cache(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture, tmp_path
) -> None:
    metadata_cache.write_cached(
        tmp_path, "arxiv", "a", title="A Paper", authors=["Author"]
    )

    async def fake_call_tool(
        self: Client, name: str, arguments: dict | None = None, **kwargs: object
    ) -> object:
        return SimpleNamespace(
            structured_content={
                "fts": {
                    "matches": [_match("a", 0.9)],
                    "offset": 0,
                    "limit": 50,
                    "total": 1,
                    "has_more": False,
                },
                "vector": None,
                "index_status": {},
            },
            data=None,
        )

    monkeypatch.setattr(Client, "call_tool", fake_call_tool)

    args = ms.build_parser().parse_args(
        ["search", "--query", "q", "--attach-titles", "--root", str(tmp_path)]
    )
    assert anyio.run(ms.run, args) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["fts"]["matches"][0]["title"] == "A Paper"
    assert output["fts"]["has_more"] is False


def test_run_stops_at_max_pages(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    async def fake_call_tool(
        self: Client, name: str, arguments: dict | None = None, **kwargs: object
    ) -> object:
        return SimpleNamespace(
            structured_content={
                "fts": {
                    "matches": [_match("a", 0.9)],
                    "offset": 0,
                    "limit": 1,
                    "total": 99,
                    "has_more": True,
                },
                "vector": None,
                "index_status": {},
            },
            data=None,
        )

    monkeypatch.setattr(Client, "call_tool", fake_call_tool)

    args = ms.build_parser().parse_args(
        ["search", "--query", "q", "--all", "--limit", "1", "--max-pages", "2"]
    )
    assert anyio.run(ms.run, args) == 0
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert "stopped after 2 pages" in captured.err
    assert output["fts"]["has_more"] is True


def test_run_exits_on_tool_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_call_tool(
        self: Client, name: str, arguments: dict | None = None, **kwargs: object
    ) -> object:
        raise ToolError("boom")

    monkeypatch.setattr(Client, "call_tool", fake_call_tool)

    args = ms.build_parser().parse_args(["search", "--query", "q"])
    with pytest.raises(SystemExit, match="boom"):
        anyio.run(ms.run, args)


def test_run_vector_mode(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    async def fake_call_tool(
        self: Client, name: str, arguments: dict | None = None, **kwargs: object
    ) -> object:
        return SimpleNamespace(
            structured_content={
                "fts": None,
                "vector": {
                    "matches": [_vector_match("a", 0.9)],
                    "offset": 0,
                    "limit": 50,
                    "total": 1,
                    "has_more": False,
                },
                "index_status": {"vector": "ready"},
            },
            data=None,
        )

    monkeypatch.setattr(Client, "call_tool", fake_call_tool)

    args = ms.build_parser().parse_args(["search", "--query", "q", "--mode", "vector"])
    assert anyio.run(ms.run, args) == 0
    output = json.loads(capsys.readouterr().out)
    assert "vector" in output
    assert "fts" not in output
    assert len(output["vector"]["matches"]) == 1
    assert output["vector"]["has_more"] is False


def test_run_hybrid_mode(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    async def fake_call_tool(
        self: Client, name: str, arguments: dict | None = None, **kwargs: object
    ) -> object:
        return SimpleNamespace(
            structured_content={
                "fts": {
                    "matches": [_match("a", 0.9)],
                    "offset": 0,
                    "limit": 50,
                    "total": 1,
                    "has_more": False,
                },
                "vector": {
                    "matches": [_vector_match("b", 0.8)],
                    "offset": 0,
                    "limit": 50,
                    "total": 1,
                    "has_more": False,
                },
                "index_status": {"vector": "ready"},
            },
            data=None,
        )

    monkeypatch.setattr(Client, "call_tool", fake_call_tool)

    args = ms.build_parser().parse_args(["search", "--query", "q", "--mode", "hybrid"])
    assert anyio.run(ms.run, args) == 0
    output = json.loads(capsys.readouterr().out)
    assert "fts" in output
    assert "vector" in output
    assert len(output["fts"]["matches"]) == 1
    assert len(output["vector"]["matches"]) == 1
    assert output["fts"]["has_more"] is False
    assert output["vector"]["has_more"] is False


def test_main_entry_point(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    async def fake_call_tool(
        self: Client, name: str, arguments: dict | None = None, **kwargs: object
    ) -> object:
        return SimpleNamespace(
            structured_content={
                "fts": {
                    "matches": [_match("a", 0.9)],
                    "offset": 0,
                    "limit": 50,
                    "total": 1,
                    "has_more": False,
                },
                "vector": None,
                "index_status": {},
            },
            data=None,
        )

    monkeypatch.setattr(Client, "call_tool", fake_call_tool)
    monkeypatch.setattr(sys, "argv", ["manage_search.py", "search", "--query", "test"])

    assert ms.main() == 0
    output = json.loads(capsys.readouterr().out)
    assert output["fts"]["total"] == 1
