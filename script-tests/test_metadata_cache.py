import json
import sys
from pathlib import Path

import metadata_cache as mc
import pytest


def test_cache_path_sanitises_colon(tmp_path: Path) -> None:
    path = mc.cache_path(tmp_path, "europepmc", "MED:26551875")
    assert (
        path
        == tmp_path / ".prioris" / ".metadata-cache" / "europepmc" / "MED_26551875.json"
    )


def test_read_cached_returns_none_when_missing(tmp_path: Path) -> None:
    assert mc.read_cached(tmp_path, "arxiv", "2401.12345") is None


def test_write_then_read_round_trips(tmp_path: Path) -> None:
    mc.write_cached(
        tmp_path,
        "arxiv",
        "2401.12345",
        title="A Paper",
        authors=["A. One", "B. Two"],
        year="2026",
    )
    assert mc.read_cached(tmp_path, "arxiv", "2401.12345") == {
        "title": "A Paper",
        "authors": ["A. One", "B. Two"],
        "year": "2026",
    }


def test_read_cached_returns_none_on_corrupt_json(tmp_path: Path) -> None:
    path = mc.cache_path(tmp_path, "arxiv", "2401.12345")
    path.parent.mkdir(parents=True)
    path.write_text("not json")
    assert mc.read_cached(tmp_path, "arxiv", "2401.12345") is None


def test_write_cached_overwrites(tmp_path: Path) -> None:
    mc.write_cached(tmp_path, "arxiv", "2401.12345", title="Old", authors=[])
    mc.write_cached(tmp_path, "arxiv", "2401.12345", title="New", authors=["X"])
    result = mc.read_cached(tmp_path, "arxiv", "2401.12345")
    assert result is not None
    assert result["title"] == "New"


def _run_main(monkeypatch: pytest.MonkeyPatch, *args: str) -> int:
    monkeypatch.setattr(sys, "argv", ["metadata_cache.py", *args])
    return mc.main()


def test_main_write_then_read(
    tmp_path: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert (
        _run_main(
            monkeypatch,
            "write",
            "arxiv",
            "2401.12345",
            "--title",
            "A Paper",
            "--author",
            "A. One",
            "--author",
            "B. Two",
            "--root",
            str(tmp_path),
        )
        == 0
    )
    capsys.readouterr()

    assert (
        _run_main(monkeypatch, "read", "arxiv", "2401.12345", "--root", str(tmp_path))
        == 0
    )
    out = json.loads(capsys.readouterr().out)
    assert out == {"title": "A Paper", "authors": ["A. One", "B. Two"], "year": None}


def test_main_read_missing_exits_1(
    tmp_path: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert (
        _run_main(monkeypatch, "read", "arxiv", "9999.99999", "--root", str(tmp_path))
        == 1
    )
    assert "no cached metadata" in capsys.readouterr().err
