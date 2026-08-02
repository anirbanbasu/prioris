import json
import sys
from pathlib import Path
from types import SimpleNamespace

import anyio
import pdf_chunk_upload_helper as helper
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

# --- pure helpers ------------------------------------------------------------


def test_chunk_base64_splits_on_4_char_boundaries() -> None:
    encoded = "AAAA" * 5  # 20 chars; max_chunk_bytes=3 -> 4 chars/chunk, divides evenly
    assert helper.chunk_base64(encoded, max_chunk_bytes=3) == ["AAAA"] * 5


def test_chunk_base64_handles_remainder() -> None:
    encoded = "A" * 10
    pieces = helper.chunk_base64(encoded, max_chunk_bytes=3)
    assert "".join(pieces) == encoded
    assert all(len(p) == 4 for p in pieces[:-1])
    assert 0 < len(pieces[-1]) <= 4


def test_chunk_base64_empty_input_yields_one_empty_piece() -> None:
    assert helper.chunk_base64("", max_chunk_bytes=100) == [""]


def test_read_and_sniff_missing_file(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="no such file"):
        helper.read_and_sniff(tmp_path / "missing.pdf")


def test_read_and_sniff_directory(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="is a directory"):
        helper.read_and_sniff(tmp_path)


def test_read_and_sniff_rejects_non_pdf(tmp_path: Path) -> None:
    path = tmp_path / "fake.pdf"
    path.write_bytes(b"not a pdf")
    with pytest.raises(SystemExit, match="does not sniff as a PDF"):
        helper.read_and_sniff(path)


def test_read_and_sniff_accepts_pdf_magic_bytes(
    tmp_path: Path, tiny_pdf_bytes: bytes
) -> None:
    path = tmp_path / "real.pdf"
    path.write_bytes(tiny_pdf_bytes)
    assert helper.read_and_sniff(path) == tiny_pdf_bytes


def test_read_and_sniff_reports_other_os_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Covers the generic `except OSError` branch (e.g. permission denied, I/O error) - simulated
    # directly rather than via real filesystem permissions, which vary by OS/CI user and aren't a
    # reliable way to trigger this deterministically.
    path = tmp_path / "unreadable.pdf"
    path.write_bytes(b"%PDF-1.4\n")

    def fake_read_bytes(self: Path) -> bytes:
        raise OSError("simulated I/O error")

    monkeypatch.setattr(Path, "read_bytes", fake_read_bytes)

    with pytest.raises(SystemExit, match="couldn't read"):
        helper.read_and_sniff(path)


# --- real in-process upload: happy path --------------------------------------
# Exercises the full begin -> upload_chunk -> finalize sequence against the actual
# prioris_mcp.server.app(), the same way the manual QA for this fix was done - not mocked, so it
# also verifies fastmcp/pydantic version compatibility with the current prioris-mcp pin.


def test_upload_happy_path_round_trips_through_real_server(
    tiny_pdf_bytes: bytes,
) -> None:
    result = anyio.run(helper.upload, tiny_pdf_bytes, "sample.pdf")
    assert result.format_ == "pdf"
    assert result.size_bytes == len(tiny_pdf_bytes)
    assert result.resource_uri.startswith("research://localfile/")


def test_main_prints_format_alias_not_field_name(
    tmp_path: Path,
    capsys: pytest.CaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    tiny_pdf_bytes: bytes,
) -> None:
    path = tmp_path / "sample.pdf"
    path.write_bytes(tiny_pdf_bytes)
    monkeypatch.setattr(sys, "argv", ["pdf_chunk_upload_helper.py", str(path)])

    assert helper.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["format"] == "pdf"
    assert "format_" not in payload


# --- contract test: a real MCP-side failure still raises ToolError, not a dict -----------------
# This is the exact assumption pdf_chunk_upload_helper.py depends on and the exact thing that
# silently stopped being true across the Pydantic/ToolError migration (see mcp-contracts.md and
# the fix commit). If prioris-mcp or fastmcp ever changes this contract again, this test - not
# just the mocked ones below - is what should catch it.


async def _call_with_unknown_session() -> None:
    async with Client(transport=helper.app(), timeout=60) as client:
        await client.call_tool(
            "research_localfile_upload_chunk",
            arguments={
                "session_id": "does-not-exist",
                "index": 0,
                "chunk_base64": "AAAA",
            },
        )


def test_unknown_session_id_raises_real_tool_error() -> None:
    with pytest.raises(ToolError):
        anyio.run(_call_with_unknown_session)


# --- our own error handling: mocked ToolError / ValidationError paths --------
# These isolate upload()'s own try/except from prioris-mcp's specific validation rules - they'd
# still pass even if prioris-mcp changed which calls fail under which conditions, as long as a
# ToolError (or a malformed response) is still handled the same way.


def test_upload_exits_cleanly_on_tool_error_from_any_call(
    monkeypatch: pytest.MonkeyPatch, tiny_pdf_bytes: bytes
) -> None:
    async def fake_call_tool(
        self: Client, name: str, arguments: dict | None = None, **kwargs: object
    ) -> None:
        raise ToolError(f"Error calling tool '{name}': boom")

    monkeypatch.setattr(Client, "call_tool", fake_call_tool)

    with pytest.raises(SystemExit, match="boom"):
        anyio.run(helper.upload, tiny_pdf_bytes, "sample.pdf")


def test_upload_exits_cleanly_on_unexpected_response_shape(
    monkeypatch: pytest.MonkeyPatch, tiny_pdf_bytes: bytes
) -> None:
    async def fake_call_tool(
        self: Client, name: str, arguments: dict | None = None, **kwargs: object
    ) -> object:
        return SimpleNamespace(structured_content={"unexpected_field": "nope"})

    monkeypatch.setattr(Client, "call_tool", fake_call_tool)

    with pytest.raises(SystemExit, match="unexpected response shape"):
        anyio.run(helper.upload, tiny_pdf_bytes, "sample.pdf")
