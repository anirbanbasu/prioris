import sys
from pathlib import Path

import pytest
import update_notes_section as uns
import yaml

NOTE = """---
title: Some Paper
tags: [foo, bar]
fetched_at: 2026-07-28T01:47:45Z
---

## Quick read

Original quick read content.

## Discussion

Original discussion content.
"""


def test_split_frontmatter_preserves_iso_timestamp_as_string() -> None:
    frontmatter, body = uns.split_frontmatter(NOTE)
    assert frontmatter["fetched_at"] == "2026-07-28T01:47:45Z"
    assert isinstance(frontmatter["fetched_at"], str)
    assert "## Quick read" in body


def test_split_frontmatter_missing_opening_delimiter() -> None:
    with pytest.raises(ValueError, match="frontmatter delimiter"):
        uns.split_frontmatter("no frontmatter here\n")


def test_split_frontmatter_unclosed_block() -> None:
    with pytest.raises(ValueError, match="never closed"):
        uns.split_frontmatter("---\ntitle: x\n")


def test_split_frontmatter_non_mapping() -> None:
    with pytest.raises(TypeError, match="YAML mapping"):
        uns.split_frontmatter("---\n- just\n- a\n- list\n---\nbody\n")


def test_parse_sections_splits_on_headers() -> None:
    _, body = uns.split_frontmatter(NOTE)
    sections = uns.parse_sections(body)
    assert [header for header, _ in sections] == ["## Quick read", "## Discussion"]
    assert sections[0][1] == "Original quick read content."
    assert sections[1][1] == "Original discussion content."


def test_render_round_trips_through_split_and_parse() -> None:
    frontmatter, body = uns.split_frontmatter(NOTE)
    sections = uns.parse_sections(body)
    rendered = uns.render(frontmatter, sections)
    frontmatter2, body2 = uns.split_frontmatter(rendered)
    assert frontmatter2 == frontmatter
    assert uns.parse_sections(body2) == sections


def _run_main(monkeypatch: pytest.MonkeyPatch, *args: str) -> int:
    monkeypatch.setattr(sys, "argv", ["update_notes_section.py", *args])
    return uns.main()


def test_main_creates_new_file_with_frontmatter(
    tmp_path: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "note.md"
    content_file = tmp_path / "content.md"
    frontmatter_file = tmp_path / "fm.yaml"
    content_file.write_text("First quick read.\n")
    frontmatter_file.write_text(yaml.dump({"title": "Some Paper"}))

    assert (
        _run_main(
            monkeypatch,
            str(target),
            "## Quick read",
            str(content_file),
            "--frontmatter",
            str(frontmatter_file),
        )
        == 0
    )
    assert "created" in capsys.readouterr().err
    text = target.read_text()
    assert "title: Some Paper" in text
    assert "## Quick read" in text
    assert "First quick read." in text


def test_main_replaces_existing_section_preserving_others(
    tmp_path: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "note.md"
    target.write_text(NOTE)
    content_file = tmp_path / "content.md"
    content_file.write_text("Updated quick read.\n")

    assert _run_main(monkeypatch, str(target), "## Quick read", str(content_file)) == 0
    assert "updated" in capsys.readouterr().err
    text = target.read_text()
    assert "Updated quick read." in text
    assert "Original discussion content." in text
    assert "Original quick read content." not in text


def test_main_appends_new_section(
    tmp_path: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "note.md"
    target.write_text(NOTE)
    content_file = tmp_path / "content.md"
    content_file.write_text("New notes.\n")

    assert _run_main(monkeypatch, str(target), "## New Section", str(content_file)) == 0
    assert "appended to" in capsys.readouterr().err
    text = target.read_text()
    assert text.index("## Discussion") < text.index("## New Section")


def test_main_warns_but_still_creates_file_without_frontmatter(
    tmp_path: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "note.md"
    content_file = tmp_path / "content.md"
    content_file.write_text("Body.\n")

    assert _run_main(monkeypatch, str(target), "## Quick read", str(content_file)) == 0
    err = capsys.readouterr().err
    assert "no --frontmatter was given" in err
    assert target.exists()


def test_main_rejects_header_without_hash(
    tmp_path: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    content_file = tmp_path / "content.md"
    content_file.write_text("x\n")

    assert (
        _run_main(
            monkeypatch, str(tmp_path / "note.md"), "Quick read", str(content_file)
        )
        == 2
    )
    assert "must start with" in capsys.readouterr().err


def test_main_missing_content_file(
    tmp_path: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert (
        _run_main(
            monkeypatch,
            str(tmp_path / "note.md"),
            "## Header",
            str(tmp_path / "missing.md"),
        )
        == 1
    )
    assert "couldn't read content file" in capsys.readouterr().err


def test_main_wrong_arg_count(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _run_main(monkeypatch, "one", "two") == 2


def test_main_frontmatter_flag_missing_path_argument(
    tmp_path: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    content_file = tmp_path / "content.md"
    content_file.write_text("x\n")

    assert (
        _run_main(
            monkeypatch,
            str(tmp_path / "note.md"),
            "## Header",
            str(content_file),
            "--frontmatter",
        )
        == 2
    )
    assert "requires a path argument" in capsys.readouterr().err


def test_main_existing_target_with_broken_frontmatter(
    tmp_path: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "note.md"
    target.write_text("not a frontmatter file at all\n")
    content_file = tmp_path / "content.md"
    content_file.write_text("x\n")

    assert _run_main(monkeypatch, str(target), "## Header", str(content_file)) == 1
    assert "doesn't look safe to merge into" in capsys.readouterr().err


def test_main_frontmatter_file_does_not_exist(
    tmp_path: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    content_file = tmp_path / "content.md"
    content_file.write_text("x\n")

    assert (
        _run_main(
            monkeypatch,
            str(tmp_path / "note.md"),
            "## Header",
            str(content_file),
            "--frontmatter",
            str(tmp_path / "missing-fm.yaml"),
        )
        == 1
    )
    assert "couldn't read frontmatter file" in capsys.readouterr().err


def test_main_existing_target_with_non_mapping_frontmatter(
    tmp_path: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "note.md"
    target.write_text("---\n- a\n- b\n---\nbody\n")
    content_file = tmp_path / "content.md"
    content_file.write_text("x\n")

    assert _run_main(monkeypatch, str(target), "## Header", str(content_file)) == 1
    assert "doesn't look safe to merge into" in capsys.readouterr().err


def test_main_frontmatter_file_not_a_mapping(
    tmp_path: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    content_file = tmp_path / "content.md"
    content_file.write_text("x\n")
    frontmatter_file = tmp_path / "fm.yaml"
    frontmatter_file.write_text("- just\n- a\n- list\n")

    assert (
        _run_main(
            monkeypatch,
            str(tmp_path / "note.md"),
            "## Header",
            str(content_file),
            "--frontmatter",
            str(frontmatter_file),
        )
        == 1
    )
    assert "must be a YAML mapping" in capsys.readouterr().err
