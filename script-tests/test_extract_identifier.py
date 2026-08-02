import json
import sys

import extract_identifier as ei
import pytest


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("10.1234/abcd.efgh", ("doi", "10.1234/abcd.efgh")),
        ("https://arxiv.org/abs/2401.12345", ("arxiv", "2401.12345")),
        ("https://arxiv.org/pdf/2401.12345.pdf", ("arxiv", "2401.12345")),
        ("https://arxiv.org/abs/2401.12345v2", ("arxiv", "2401.12345v2")),
        ("arxiv.org/abs/2401.12345", ("arxiv", "2401.12345")),
        ("https://export.arxiv.org/abs/2401.12345", ("arxiv", "2401.12345")),
        ("https://doi.org/10.1234/abcd.efgh", ("doi", "10.1234/abcd.efgh")),
        (
            "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC1234567/",
            ("europepmc", "PMC1234567"),
        ),
        ("https://europepmc.org/article/MED/12345678", ("europepmc", "MED:12345678")),
        ("https://evilarxiv.org/abs/2401.12345", None),
        ("not a url or doi at all", None),
        ("https://example.com/some/random/path", None),
    ],
)
def test_extract(raw: str, expected: tuple[str, str] | None) -> None:
    assert ei.extract(raw) == expected


def test_main_prints_json_on_success(
    capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "argv", ["extract_identifier.py", "10.1234/abcd.efgh"])
    assert ei.main() == 0
    assert json.loads(capsys.readouterr().out) == {
        "provider": "doi",
        "identifier": "10.1234/abcd.efgh",
    }


def test_main_exits_nonzero_on_unrecognised_input(
    capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "argv", ["extract_identifier.py", "nonsense"])
    assert ei.main() == 1
    assert "not a recognized research URL" in capsys.readouterr().err


def test_main_usage_on_wrong_arg_count(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["extract_identifier.py"])
    assert ei.main() == 2
