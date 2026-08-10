import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import review_schedule as rs


def test_interval_days_caps_at_last_level() -> None:
    assert rs.interval_days(0) == 1
    assert rs.interval_days(1) == 2
    assert rs.interval_days(6) == 64
    assert rs.interval_days(99) == 64


def test_load_schedule_missing_file_returns_empty(tmp_path: Path) -> None:
    assert rs.load_schedule(tmp_path) == {}


def test_load_schedule_corrupt_file_returns_empty(tmp_path: Path) -> None:
    path = rs.schedule_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text("not json")
    assert rs.load_schedule(tmp_path) == {}


def test_record_result_first_correct_sets_level_1(tmp_path: Path) -> None:
    now = "2026-08-09T10:00:00+00:00"
    entry = rs.record_result(tmp_path, "note-1", "correct", now)
    assert entry == {
        "level": 1,
        "times_asked": 1,
        "last_result": "correct",
        "last_asked_at": now,
    }
    assert rs.load_schedule(tmp_path)["note-1"] == entry


def test_record_result_incorrect_resets_level(tmp_path: Path) -> None:
    rs.record_result(tmp_path, "note-1", "correct", "2026-08-01T00:00:00+00:00")
    rs.record_result(tmp_path, "note-1", "correct", "2026-08-02T00:00:00+00:00")
    entry = rs.record_result(
        tmp_path, "note-1", "incorrect", "2026-08-03T00:00:00+00:00"
    )
    assert entry["level"] == 0
    assert entry["times_asked"] == 3


def test_record_result_partial_keeps_level(tmp_path: Path) -> None:
    rs.record_result(tmp_path, "note-1", "correct", "2026-08-01T00:00:00+00:00")
    entry = rs.record_result(tmp_path, "note-1", "partial", "2026-08-02T00:00:00+00:00")
    assert entry["level"] == 1
    assert entry["times_asked"] == 2


def test_record_result_rejects_bad_result(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="correct/partial/incorrect"):
        rs.record_result(tmp_path, "note-1", "maybe", "2026-08-01T00:00:00+00:00")


def test_prune_removes_existing_entry(tmp_path: Path) -> None:
    rs.record_result(tmp_path, "note-1", "correct", "2026-08-01T00:00:00+00:00")
    assert rs.prune(tmp_path, "note-1") is True
    assert "note-1" not in rs.load_schedule(tmp_path)


def test_prune_missing_entry_returns_false(tmp_path: Path) -> None:
    assert rs.prune(tmp_path, "does-not-exist") is False


def test_due_order_never_asked_comes_first(tmp_path: Path) -> None:
    now = datetime(2026, 8, 9, tzinfo=UTC)
    rs.record_result(
        tmp_path, "asked", "correct", (now - timedelta(days=100)).isoformat()
    )
    order = rs.due_order(["asked", "never-asked"], tmp_path, now)
    assert order == ["never-asked", "asked"]


def test_due_order_orders_by_most_overdue_first(tmp_path: Path) -> None:
    now = datetime(2026, 8, 9, tzinfo=UTC)
    rs.record_result(
        tmp_path, "a", "correct", (now - timedelta(days=2, hours=1)).isoformat()
    )  # level1, due 2d, overdue by 1h
    rs.record_result(
        tmp_path, "b", "correct", (now - timedelta(days=11)).isoformat()
    )  # level1, due 2d, overdue by 9d
    assert rs.due_order(["a", "b"], tmp_path, now) == ["b", "a"]


def test_due_order_treats_malformed_timestamp_as_epoch(tmp_path: Path) -> None:
    now = datetime(2026, 8, 9, tzinfo=UTC)
    rs.save_schedule(
        tmp_path,
        {"corrupt": {"level": 0, "times_asked": 1, "last_asked_at": "not-a-date"}},
    )
    rs.record_result(tmp_path, "fresh", "correct", now.isoformat())
    assert rs.due_order(["fresh", "corrupt"], tmp_path, now) == ["corrupt"]


def test_due_order_excludes_not_yet_due(tmp_path: Path) -> None:
    now = datetime(2026, 8, 9, tzinfo=UTC)
    rs.record_result(
        tmp_path, "fresh", "correct", now.isoformat()
    )  # level1, due in 2 days
    assert rs.due_order(["fresh"], tmp_path, now) == []


def _run_main(monkeypatch: pytest.MonkeyPatch, *args: str) -> int:
    monkeypatch.setattr(sys, "argv", ["review_schedule.py", *args])
    return rs.main()


def test_main_record_and_due(
    tmp_path: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert (
        _run_main(
            monkeypatch,
            "record",
            "note-1",
            "incorrect",
            "--asked-at",
            "2026-08-01T00:00:00+00:00",
            "--root",
            str(tmp_path),
        )
        == 0
    )
    capsys.readouterr()
    assert (
        _run_main(
            monkeypatch,
            "due",
            "note-1",
            "note-2",
            "--now",
            "2026-08-09T00:00:00+00:00",
            "--root",
            str(tmp_path),
        )
        == 0
    )
    due = json.loads(capsys.readouterr().out)
    assert due == [
        "note-2",
        "note-1",
    ]  # note-2 never asked (epoch, most overdue); note-1 overdue since 2026-08-02


def test_main_record_defaults_asked_at_to_now(
    tmp_path: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert (
        _run_main(monkeypatch, "record", "note-1", "correct", "--root", str(tmp_path))
        == 0
    )
    capsys.readouterr()
    entry = rs.load_schedule(tmp_path)["note-1"]
    datetime.fromisoformat(entry["last_asked_at"])  # does not raise


def test_main_prune(
    tmp_path: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    _run_main(monkeypatch, "record", "note-1", "correct", "--root", str(tmp_path))
    capsys.readouterr()
    assert _run_main(monkeypatch, "prune", "note-1", "--root", str(tmp_path)) == 0
    assert capsys.readouterr().out.strip() == "true"
    assert _run_main(monkeypatch, "prune", "note-1", "--root", str(tmp_path)) == 0
    assert capsys.readouterr().out.strip() == "false"


def test_main_record_rejects_bad_result(
    tmp_path: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert (
        _run_main(monkeypatch, "record", "note-1", "maybe", "--root", str(tmp_path))
        == 2
    )
    assert "correct/partial/incorrect" in capsys.readouterr().err
