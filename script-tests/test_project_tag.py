import subprocess
import sys
from pathlib import Path

import project_tag as pt
import pytest


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "https://github.com/anirbanbasu/prioris.git",
            "github.com/anirbanbasu/prioris",
        ),
        ("https://github.com/anirbanbasu/prioris", "github.com/anirbanbasu/prioris"),
        ("git@github.com:anirbanbasu/prioris.git", "github.com/anirbanbasu/prioris"),
        (
            "https://gitlab.example.com/Team/Sub Group/repo.git",
            "gitlab.example.com/team/sub-group/repo",
        ),
        ("not a url at all", None),
        ("https://", None),
    ],
)
def test_from_remote_url(url: str, expected: str | None) -> None:
    assert pt._from_remote_url(url) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Prioris", "prioris"),
        ("My Cool Project!!", "my-cool-project"),
        ("  ", "unnamed"),
        ("___", "unnamed"),
    ],
)
def test_slugify(raw: str, expected: str) -> None:
    assert pt._slugify(raw) == expected


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def test_derive_project_tag_uses_remote_when_present(tmp_path: Path) -> None:
    repo = tmp_path / "myrepo"
    repo.mkdir()
    _git("init", "-q", cwd=repo)
    _git(
        "remote",
        "add",
        "origin",
        "https://github.com/anirbanbasu/prioris.git",
        cwd=repo,
    )
    assert pt.derive_project_tag(repo) == "project:github.com/anirbanbasu/prioris"


def test_derive_project_tag_falls_back_to_toplevel_folder_name(tmp_path: Path) -> None:
    repo = tmp_path / "MyLocalRepo"
    repo.mkdir()
    _git("init", "-q", cwd=repo)
    nested = repo / "sub" / "dir"
    nested.mkdir(parents=True)
    assert pt.derive_project_tag(nested) == "project:mylocalrepo"


def test_derive_project_tag_falls_back_to_cwd_name_outside_git(tmp_path: Path) -> None:
    plain = tmp_path / "NotARepo"
    plain.mkdir()
    assert pt.derive_project_tag(plain) == "project:notarepo"


def test_derive_project_tag_handles_missing_git_binary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _raise(*_args: object, **_kwargs: object) -> None:
        raise FileNotFoundError("git not found")

    monkeypatch.setattr(pt.subprocess, "run", _raise)
    assert pt.derive_project_tag(tmp_path) == f"project:{pt._slugify(tmp_path.name)}"


def test_main_prints_tag(
    tmp_path: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "argv", ["project_tag.py", "--cwd", str(tmp_path)])
    assert pt.main() == 0
    assert capsys.readouterr().out.strip() == f"project:{pt._slugify(tmp_path.name)}"


def test_main_defaults_to_current_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "argv", ["project_tag.py"])
    monkeypatch.chdir(tmp_path)
    assert pt.main() == 0
    assert capsys.readouterr().out.strip() == f"project:{pt._slugify(tmp_path.name)}"
