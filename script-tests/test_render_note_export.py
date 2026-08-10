import json
import sys
from pathlib import Path

import pytest
import render_note_export as rne
import yaml

_EXPORT = {
    "suggested_filename": "note-uuid-1234",
    "frontmatter": {
        "id": "note-uuid-1234",
        "provider": "arxiv",
        "canonical_identifier": "2401.12345v2",
        "format": "pdf",
        "anchors": [],
        "author_name": None,
        "tags": ["project:github.com/x/y", "skill:discuss", "topic:evaluation"],
        "metadata": None,
        "created_at": "2026-08-01T00:00:00+00:00",
        "updated_at": "2026-08-01T00:00:00+00:00",
    },
    "markdown_body": "The paper's evaluation methodology is sound because...",
}


def test_render_produces_yaml_frontmatter_then_body() -> None:
    rendered = rne.render(_EXPORT)
    assert rendered.startswith("---\n")
    fm_text, _, body = rendered[4:].partition("---\n")
    frontmatter = yaml.safe_load(fm_text)
    assert frontmatter == _EXPORT["frontmatter"]
    assert body.strip() == _EXPORT["markdown_body"]


def test_write_export_creates_file_named_after_suggested_filename(
    tmp_path: Path,
) -> None:
    written = rne.write_export(_EXPORT, tmp_path)
    assert written == tmp_path / "note-uuid-1234.md"
    assert written.exists()
    assert "evaluation methodology" in written.read_text()


def test_write_export_creates_vault_dir_if_missing(tmp_path: Path) -> None:
    vault = tmp_path / "does" / "not" / "exist"
    written = rne.write_export(_EXPORT, vault)
    assert written.exists()


def test_write_export_overwrites_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "note-uuid-1234.md"
    target.write_text("stale content")
    rne.write_export(_EXPORT, tmp_path)
    assert "evaluation methodology" in target.read_text()
    assert "stale content" not in target.read_text()


def test_main_reads_stdin_writes_file_prints_path(
    tmp_path: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "argv", ["render_note_export.py", str(tmp_path)])
    monkeypatch.setattr(sys, "stdin", __import__("io").StringIO(json.dumps(_EXPORT)))
    assert rne.main() == 0
    printed = capsys.readouterr().out.strip()
    assert printed == str(tmp_path / "note-uuid-1234.md")


def test_main_rejects_invalid_json(
    tmp_path: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "argv", ["render_note_export.py", str(tmp_path)])
    monkeypatch.setattr(sys, "stdin", __import__("io").StringIO("not json"))
    assert rne.main() == 1
    assert "valid JSON" in capsys.readouterr().err


def test_main_rejects_wrong_argument_count(
    capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "argv", ["render_note_export.py"])
    assert rne.main() == 2
    assert "usage:" in capsys.readouterr().err
