import json
from pathlib import Path
from types import SimpleNamespace

import anyio
import manage_notes as mn
import metadata_cache
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

# --- pure helpers -------------------------------------------------------------


def test_build_anchors_wraps_each_quote_in_selectors() -> None:
    assert mn._build_anchors(["a quote", "another"]) == [
        {"selectors": {"exact_text_quote": "a quote"}},
        {"selectors": {"exact_text_quote": "another"}},
    ]


def test_build_anchors_empty_list() -> None:
    assert mn._build_anchors([]) == []


def test_parse_metadata_splits_on_first_equals() -> None:
    assert mn._parse_metadata(["a=1", "b=x=y"]) == {"a": "1", "b": "x=y"}


def test_parse_metadata_rejects_missing_equals() -> None:
    with pytest.raises(SystemExit, match="KEY=VALUE"):
        mn._parse_metadata(["not-a-pair"])


def _note(note_id: str, provider: str, identifier: str, updated_at: str) -> dict:
    return {
        "id": note_id,
        "provider": provider,
        "canonical_identifier": identifier,
        "text": "x",
        "tags": ["skill:quick-read"],
        "created_at": updated_at,
        "updated_at": updated_at,
    }


def test_group_by_paper_groups_sorts_and_attaches_titles(tmp_path: Path) -> None:
    notes = [
        _note("n1", "arxiv", "1234.5678", "2026-01-01T00:00:00+00:00"),
        _note("n2", "arxiv", "1234.5678", "2026-01-02T00:00:00+00:00"),
        _note("n3", "localfile", "abc", "2026-01-03T00:00:00+00:00"),
    ]
    metadata_cache.write_cached(
        tmp_path, "arxiv", "1234.5678", title="A Paper", authors=["A. Author"]
    )

    groups = mn._group_by_paper(notes, tmp_path, attach_titles=True)

    assert [g["canonical_identifier"] for g in groups] == ["abc", "1234.5678"]
    arxiv_group = groups[1]
    assert arxiv_group["latest_updated_at"] == "2026-01-02T00:00:00+00:00"
    assert [n["id"] for n in arxiv_group["notes"]] == ["n1", "n2"]
    assert arxiv_group["title"] == "A Paper"
    assert arxiv_group["authors"] == ["A. Author"]
    assert groups[0]["title"] is None


def test_group_by_paper_without_attach_titles_leaves_titles_null(
    tmp_path: Path,
) -> None:
    notes = [_note("n1", "arxiv", "1234.5678", "2026-01-01T00:00:00+00:00")]
    metadata_cache.write_cached(
        tmp_path, "arxiv", "1234.5678", title="A Paper", authors=["A. Author"]
    )
    groups = mn._group_by_paper(notes, tmp_path, attach_titles=False)
    assert groups[0]["title"] is None


# --- CLI parsing ---------------------------------------------------------------


def test_build_parser_search_defaults() -> None:
    args = mn.build_parser().parse_args(["search"])
    assert args.command == "search"
    assert args.mode == "fts"
    assert args.limit == 50
    assert args.all is False
    assert args.tags_all == []


def test_build_parser_create_requires_provider_identifier_text() -> None:
    with pytest.raises(SystemExit):
        mn.build_parser().parse_args(["create"])


def test_search_group_by_paper_rejects_non_fts_mode() -> None:
    args = mn.build_parser().parse_args(
        ["search", "--mode", "vector", "--group-by-paper"]
    )
    with pytest.raises(SystemExit, match="--mode fts"):
        anyio.run(mn.cmd_search, args)


# --- real round trip against the isolated in-process server -------------------


def test_create_search_read_update_delete_round_trip(
    capsys: pytest.CaptureFixture,
) -> None:
    create_args = mn.build_parser().parse_args(
        [
            "create",
            "--provider",
            "arxiv",
            "--identifier",
            "9999.0001",
            "--text",
            "A test note",
            "--tag",
            "project:test",
            "--anchor-quote",
            "quoted text",
        ]
    )
    assert anyio.run(mn.cmd_create, create_args) == 0
    created = json.loads(capsys.readouterr().out)
    note_id = created["id"]
    assert created["text"] == "A test note"
    assert created["anchors"][0]["selectors"]["exact_text_quote"] == "quoted text"

    search_args = mn.build_parser().parse_args(
        [
            "search",
            "--provider",
            "arxiv",
            "--identifier",
            "9999.0001",
            "--group-by-paper",
        ]
    )
    assert anyio.run(mn.cmd_search, search_args) == 0
    groups = json.loads(capsys.readouterr().out)
    assert len(groups) == 1
    assert groups[0]["notes"][0]["id"] == note_id

    read_args = mn.build_parser().parse_args(["read", note_id])
    assert anyio.run(mn.cmd_read, read_args) == 0
    read_back = json.loads(capsys.readouterr().out)
    assert read_back["id"] == note_id

    update_args = mn.build_parser().parse_args(["update", note_id, "--clear-tags"])
    assert anyio.run(mn.cmd_update, update_args) == 0
    updated = json.loads(capsys.readouterr().out)
    assert updated["tags"] == []

    delete_args = mn.build_parser().parse_args(["delete", note_id])
    assert anyio.run(mn.cmd_delete, delete_args) == 0
    assert json.loads(capsys.readouterr().out) == {"deleted": True}


# --- pagination looping (mocked) -----------------------------------------------


def test_search_all_loops_until_has_more_false(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    pages = [
        {
            "fts": {
                "notes": [
                    _note("n1", "arxiv", "1234.5678", "2026-01-01T00:00:00+00:00")
                ],
                "offset": 0,
                "limit": 1,
                "total": 2,
                "has_more": True,
            },
            "vector": None,
            "index_status": None,
        },
        {
            "fts": {
                "notes": [
                    _note("n2", "arxiv", "1234.5678", "2026-01-02T00:00:00+00:00")
                ],
                "offset": 1,
                "limit": 1,
                "total": 2,
                "has_more": False,
            },
            "vector": None,
            "index_status": None,
        },
    ]

    async def fake_call_tool(
        self: Client, name: str, arguments: dict | None = None, **kwargs: object
    ) -> object:
        return SimpleNamespace(structured_content=pages.pop(0), data=None)

    monkeypatch.setattr(Client, "call_tool", fake_call_tool)

    args = mn.build_parser().parse_args(["search", "--all", "--limit", "1"])
    assert anyio.run(mn.cmd_search, args) == 0
    output = json.loads(capsys.readouterr().out)
    assert [n["id"] for n in output["fts"]["notes"]] == ["n1", "n2"]
    # Last page fetched had has_more False, so the aggregated block should reflect that even
    # though the first page's has_more was True.
    assert output["fts"]["has_more"] is False


def test_search_all_stops_at_max_pages(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    async def fake_call_tool(
        self: Client, name: str, arguments: dict | None = None, **kwargs: object
    ) -> object:
        return SimpleNamespace(
            structured_content={
                "fts": {
                    "notes": [
                        _note("n1", "arxiv", "1234.5678", "2026-01-01T00:00:00+00:00")
                    ],
                    "offset": 0,
                    "limit": 1,
                    "total": 99,
                    "has_more": True,
                },
                "vector": None,
                "index_status": None,
            },
            data=None,
        )

    monkeypatch.setattr(Client, "call_tool", fake_call_tool)

    args = mn.build_parser().parse_args(
        ["search", "--all", "--limit", "1", "--max-pages", "2"]
    )
    assert anyio.run(mn.cmd_search, args) == 0
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert "stopped after 2 pages" in captured.err
    assert output["fts"]["has_more"] is True


def test_create_exits_on_tool_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_call_tool(
        self: Client, name: str, arguments: dict | None = None, **kwargs: object
    ) -> object:
        raise ToolError("invalid_request: bad provider")

    monkeypatch.setattr(Client, "call_tool", fake_call_tool)

    args = mn.build_parser().parse_args(
        ["create", "--provider", "arxiv", "--identifier", "x", "--text", "t"]
    )
    with pytest.raises(SystemExit, match="invalid_request"):
        anyio.run(mn.cmd_create, args)


def test_search_without_group_by_paper(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    async def fake_call_tool(
        self: Client, name: str, arguments: dict | None = None, **kwargs: object
    ) -> object:
        return SimpleNamespace(
            structured_content={
                "fts": {
                    "notes": [
                        _note("n1", "arxiv", "1234.5678", "2026-01-01T00:00:00+00:00")
                    ],
                    "offset": 0,
                    "limit": 50,
                    "total": 1,
                    "has_more": False,
                },
                "vector": None,
                "index_status": None,
            },
            data=None,
        )

    monkeypatch.setattr(Client, "call_tool", fake_call_tool)

    args = mn.build_parser().parse_args(["search"])
    assert anyio.run(mn.cmd_search, args) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["fts"]["notes"][0]["id"] == "n1"
    assert output["fts"]["has_more"] is False


def test_search_all_with_no_pagination(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    async def fake_call_tool(
        self: Client, name: str, arguments: dict | None = None, **kwargs: object
    ) -> object:
        return SimpleNamespace(
            structured_content={
                "fts": {
                    "notes": [
                        _note("n1", "arxiv", "1234.5678", "2026-01-01T00:00:00+00:00")
                    ],
                    "offset": 0,
                    "limit": 50,
                    "total": 1,
                    "has_more": False,
                },
                "vector": None,
                "index_status": None,
            },
            data=None,
        )

    monkeypatch.setattr(Client, "call_tool", fake_call_tool)

    args = mn.build_parser().parse_args(["search", "--all"])
    assert anyio.run(mn.cmd_search, args) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["fts"]["notes"][0]["id"] == "n1"


def test_update_with_text_and_tag_and_anchor_quote_and_metadata(
    capsys: pytest.CaptureFixture,
) -> None:
    # Test update with --text, --tag, --anchor-quote, and --metadata by using the real server
    # First create a note
    create_args = mn.build_parser().parse_args(
        [
            "create",
            "--provider",
            "arxiv",
            "--identifier",
            "9999.0002",
            "--text",
            "Original text",
        ]
    )
    assert anyio.run(mn.cmd_create, create_args) == 0
    created = json.loads(capsys.readouterr().out)
    note_id = created["id"]

    # Now update it with all the different flags
    update_args = mn.build_parser().parse_args(
        [
            "update",
            note_id,
            "--text",
            "Updated text",
            "--tag",
            "new_tag",
            "--anchor-quote",
            "new quote",
            "--metadata",
            "key=value",
        ]
    )
    assert anyio.run(mn.cmd_update, update_args) == 0
    updated = json.loads(capsys.readouterr().out)
    assert updated["text"] == "Updated text"
    assert "new_tag" in updated["tags"]
    assert len(updated["anchors"]) > 0


def test_update_with_clear_anchors_and_metadata(capsys: pytest.CaptureFixture) -> None:
    # Test update with --clear-anchors and --clear-metadata by using the real server
    # First create a note with anchors and metadata
    create_args = mn.build_parser().parse_args(
        [
            "create",
            "--provider",
            "arxiv",
            "--identifier",
            "9999.0003",
            "--text",
            "Test note",
            "--anchor-quote",
            "quoted text",
            "--metadata",
            "key=value",
        ]
    )
    assert anyio.run(mn.cmd_create, create_args) == 0
    created = json.loads(capsys.readouterr().out)
    note_id = created["id"]
    assert len(created["anchors"]) > 0

    # Now clear the anchors and metadata
    update_args = mn.build_parser().parse_args(
        ["update", note_id, "--clear-anchors", "--clear-metadata"]
    )
    assert anyio.run(mn.cmd_update, update_args) == 0
    updated = json.loads(capsys.readouterr().out)
    assert updated["anchors"] == []
    assert updated["metadata"] == {}


def test_search_with_vector_and_index_status(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Test that vector matches and index_status are correctly included in output."""

    async def fake_call_tool(
        self: Client, name: str, arguments: dict | None = None, **kwargs: object
    ) -> object:
        return SimpleNamespace(
            structured_content={
                "fts": {
                    "notes": [
                        _note("n1", "arxiv", "1234.5678", "2026-01-01T00:00:00+00:00")
                    ],
                    "offset": 0,
                    "limit": 50,
                    "total": 1,
                    "has_more": False,
                },
                "vector": {
                    "matches": [
                        {
                            "note_id": "vm1",
                            "text_preview": "vector match text preview",
                            "score": 0.95,
                        }
                    ],
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

    args = mn.build_parser().parse_args(["search", "--mode", "hybrid"])
    assert anyio.run(mn.cmd_search, args) == 0
    output = json.loads(capsys.readouterr().out)

    # Assert vector matches are in output
    assert "vector" in output
    assert len(output["vector"]["matches"]) == 1
    assert output["vector"]["matches"][0]["note_id"] == "vm1"
    assert output["vector"]["total"] == 1
    assert output["vector"]["has_more"] is False

    # Assert index_status is in output as a plain dict with string values
    assert "index_status" in output
    assert output["index_status"]["vector"] == "ready"


def test_search_mode_vector(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Test that search --mode vector returns only vector matches without fts block."""

    def _vector_match(note_id: str, score: float) -> dict:
        return {
            "note_id": note_id,
            "score": score,
            "text_preview": "vector match text preview",
        }

    async def fake_call_tool(
        self: Client, name: str, arguments: dict | None = None, **kwargs: object
    ) -> object:
        return SimpleNamespace(
            structured_content={
                "fts": None,
                "vector": {
                    "matches": [_vector_match("vm1", 0.95)],
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

    args = mn.build_parser().parse_args(["search", "--mode", "vector"])
    assert anyio.run(mn.cmd_search, args) == 0
    output = json.loads(capsys.readouterr().out)

    # Assert vector matches are in output
    assert "vector" in output
    assert len(output["vector"]["matches"]) == 1
    assert output["vector"]["matches"][0]["note_id"] == "vm1"
    assert output["vector"]["total"] == 1

    # Assert fts is NOT in output when mode is vector and fts_notes is empty
    assert "fts" not in output

    # Assert index_status is present
    assert "index_status" in output
    assert output["index_status"]["vector"] == "ready"


def test_main_function(capsys: pytest.CaptureFixture) -> None:
    # Test that main() function works correctly
    import sys as sys_module

    # Mock sys.argv and call main
    original_argv = sys_module.argv
    try:
        sys_module.argv = ["manage_notes.py", "search"]
        # main() should return 0 on success
        result = mn.main()
        assert result == 0
    finally:
        sys_module.argv = original_argv
