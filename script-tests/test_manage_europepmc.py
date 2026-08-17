import json
import sys
from types import SimpleNamespace

import anyio
import manage_europepmc as me
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError


def _record(identifier: str) -> dict:
    return {
        "identifier": identifier,
        "pmid": None,
        "pmcid": None,
        "doi": None,
        "title": "T",
        "authors": [],
        "abstract": "A",
        "journal": None,
        "pub_year": "2026",
        "is_open_access": "Y",
        "license": None,
        "full_text_available": False,
    }


def test_cmd_search_single_page(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    async def fake_call_tool(
        self: Client, name: str, arguments: dict | None = None, **kwargs: object
    ) -> object:
        assert arguments is not None
        assert arguments["cursor_mark"] == "*"
        return SimpleNamespace(
            structured_content={
                "results": [_record("PMC1")],
                "hit_count": 1,
                "next_cursor_mark": None,
            },
            data=None,
        )

    monkeypatch.setattr(Client, "call_tool", fake_call_tool)

    args = me.build_parser().parse_args(["search", "--query", "q"])
    assert anyio.run(me.cmd_search, args) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["results"][0]["identifier"] == "PMC1"
    assert output["next_cursor_mark"] is None


def test_cmd_search_all_loops_cursor_mark(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    # Real Europe PMC (Solr-backed) never signals exhaustion with a null next_cursor_mark - it
    # repeats the SAME cursor mark it was just sent on the last page. The first page advances the
    # mark from "*" to "CURSOR2"; the second page echoes "CURSOR2" back unchanged, which is what
    # should stop the loop (not a null/falsy mark).
    pages = [
        {"results": [_record("PMC1")], "hit_count": 2, "next_cursor_mark": "CURSOR2"},
        {"results": [_record("PMC2")], "hit_count": 2, "next_cursor_mark": "CURSOR2"},
    ]

    async def fake_call_tool(
        self: Client, name: str, arguments: dict | None = None, **kwargs: object
    ) -> object:
        return SimpleNamespace(structured_content=pages.pop(0), data=None)

    monkeypatch.setattr(Client, "call_tool", fake_call_tool)

    args = me.build_parser().parse_args(["search", "--query", "q", "--all"])
    assert anyio.run(me.cmd_search, args) == 0
    # pages.pop(0) would raise IndexError if a third round trip were made, so reaching here at
    # all already proves the loop stopped after exactly two pages.
    output = json.loads(capsys.readouterr().out)
    assert [r["identifier"] for r in output["results"]] == ["PMC1", "PMC2"]
    assert output["next_cursor_mark"] == "CURSOR2"


def test_cmd_search_stops_at_max_pages(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    # Each page must hand back a genuinely new cursor mark (never equal to the one it was just
    # sent) so this test exercises the --max-pages cap itself, not the exhaustion-detection
    # short-circuit added for Europe PMC's Solr cursorMark convention.
    call_count = 0

    async def fake_call_tool(
        self: Client, name: str, arguments: dict | None = None, **kwargs: object
    ) -> object:
        nonlocal call_count
        call_count += 1
        return SimpleNamespace(
            structured_content={
                "results": [_record("PMC1")],
                "hit_count": 99,
                "next_cursor_mark": f"MORE-{call_count}",
            },
            data=None,
        )

    monkeypatch.setattr(Client, "call_tool", fake_call_tool)

    args = me.build_parser().parse_args(
        ["search", "--query", "q", "--all", "--max-pages", "2"]
    )
    assert anyio.run(me.cmd_search, args) == 0
    assert "stopped after 2 pages" in capsys.readouterr().err


def test_cmd_fetch_metadata(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    async def fake_call_tool(
        self: Client, name: str, arguments: dict | None = None, **kwargs: object
    ) -> object:
        assert arguments is not None
        assert arguments["identifiers"] == ["PMC1"]
        return SimpleNamespace(
            structured_content={"results": [_record("PMC1")], "not_found": []},
            data=None,
        )

    monkeypatch.setattr(Client, "call_tool", fake_call_tool)

    args = me.build_parser().parse_args(["fetch-metadata", "--identifier", "PMC1"])
    assert anyio.run(me.cmd_fetch_metadata, args) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["not_found"] == []


def test_cmd_search_exits_on_tool_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_call_tool(
        self: Client, name: str, arguments: dict | None = None, **kwargs: object
    ) -> object:
        raise ToolError("boom")

    monkeypatch.setattr(Client, "call_tool", fake_call_tool)

    args = me.build_parser().parse_args(["search", "--query", "q"])
    with pytest.raises(SystemExit, match="boom"):
        anyio.run(me.cmd_search, args)


def test_main_entry_point(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    async def fake_call_tool(
        self: Client, name: str, arguments: dict | None = None, **kwargs: object
    ) -> object:
        assert name == "research_europepmc_search"
        assert arguments is not None
        return SimpleNamespace(
            structured_content={
                "results": [_record("PMC1")],
                "hit_count": 1,
                "next_cursor_mark": None,
            },
            data=None,
        )

    monkeypatch.setattr(Client, "call_tool", fake_call_tool)
    monkeypatch.setattr(
        sys, "argv", ["manage_europepmc.py", "search", "--query", "test"]
    )

    assert me.main() == 0
    output = json.loads(capsys.readouterr().out)
    assert output["results"][0]["identifier"] == "PMC1"
