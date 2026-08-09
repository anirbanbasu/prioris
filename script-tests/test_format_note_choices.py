import json
import sys

import format_note_choices as fnc
import pytest


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("## Methodology\n\nThey use a transformer.", "Methodology"),
        ("Just plain text, no heading.", "Just plain text, no heading."),
        ("\n\n   \n# Title Only", "Title Only"),
        ("", "(empty note)"),
        ("   \n   ", "(empty note)"),
    ],
)
def test_first_line(text: str, expected: str) -> None:
    assert fnc.first_line(text) == expected


@pytest.mark.parametrize(
    ("tags", "expected"),
    [
        (
            ["skill:discuss", "topic:federated-learning", "project:foo"],
            "topic:federated-learning",
        ),
        (["skill:quiz-me", "type:question"], "type:question"),
        (["skill:quick-read", "section:methodology"], "section:methodology"),
        (["skill:discuss", "project:foo"], None),
        ([], None),
    ],
)
def test_topic_tag(tags: list[str], expected: str | None) -> None:
    assert fnc.topic_tag(tags) == expected


def test_build_choice_truncates_long_labels() -> None:
    note = {"id": "abc123", "text": "x" * 200, "tags": ["topic:long"]}
    choice = fnc.build_choice(note)
    assert choice["id"] == "abc123"
    assert choice["label"].endswith("... [topic:long]")
    assert len(choice["label"]) <= 80 + len(" [topic:long]") + 3


def test_build_choice_without_tags() -> None:
    note = {"id": "n1", "text": "Short note.", "tags": []}
    assert fnc.build_choice(note) == {"id": "n1", "label": "Short note."}


def test_build_choices_respects_order() -> None:
    notes = [
        {"id": "1", "text": "First", "tags": []},
        {"id": "2", "text": "Second", "tags": []},
    ]
    assert [c["id"] for c in fnc.build_choices(notes)] == ["1", "2"]


def test_main_reads_stdin_and_prints_json(
    capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    notes = [{"id": "1", "text": "## A note", "tags": ["topic:x"]}]
    monkeypatch.setattr(sys, "argv", ["format_note_choices.py"])
    monkeypatch.setattr(sys, "stdin", __import__("io").StringIO(json.dumps(notes)))
    assert fnc.main() == 0
    assert json.loads(capsys.readouterr().out) == [
        {"id": "1", "label": "A note [topic:x]"}
    ]


def test_main_respects_max_flag(
    capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    notes = [{"id": str(i), "text": f"Note {i}", "tags": []} for i in range(6)]
    monkeypatch.setattr(sys, "argv", ["format_note_choices.py", "--max", "2"])
    monkeypatch.setattr(sys, "stdin", __import__("io").StringIO(json.dumps(notes)))
    assert fnc.main() == 0
    assert len(json.loads(capsys.readouterr().out)) == 2


def test_main_rejects_invalid_json(
    capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "argv", ["format_note_choices.py"])
    monkeypatch.setattr(sys, "stdin", __import__("io").StringIO("not json"))
    assert fnc.main() == 1
    assert "valid JSON" in capsys.readouterr().err


def test_main_rejects_non_list_json(
    capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "argv", ["format_note_choices.py"])
    monkeypatch.setattr(
        sys, "stdin", __import__("io").StringIO(json.dumps({"not": "a list"}))
    )
    assert fnc.main() == 1
    assert "list of note objects" in capsys.readouterr().err
