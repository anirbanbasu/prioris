"""Derive a stable "project:<slug>" tag for the current repo/working directory.

NotesBackend is one global, non-project-scoped store per prioris-mcp instance
(see docs/superpowers/specs/2026-08-09-notes-backend-integration-design.md's
"Tagging convention"). Every note this plugin creates carries this tag so
research_notes_search's tags_all filter can recover project boundaries the
server itself doesn't know about.

Usage:
    uv run --project <plugin root> python shared/scripts/project_tag.py [--cwd PATH]

Prints exactly one line, "project:<slug>", to stdout and exits 0. Never
fails: every resolution branch (git remote -> git toplevel folder name ->
plain folder name) has a fallback below it.
"""

import argparse
import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse


def _git_output(args: list[str], cwd: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, check=False
        )
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _slugify(raw: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", raw.lower()).strip("-")
    return slug or "unnamed"


def _from_remote_url(url: str) -> str | None:
    url = url.strip().removesuffix(".git")
    if url.startswith("git@"):
        host, _, path = url[len("git@") :].partition(":")
    else:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        path = parsed.path.lstrip("/")
    if not host or not path:
        return None
    path_parts = [_slugify(part) for part in path.split("/")]
    return f"{host.lower()}/{'/'.join(path_parts)}"


def derive_project_tag(cwd: Path) -> str:
    remote_url = _git_output(["remote", "get-url", "origin"], cwd)
    if remote_url:
        from_remote = _from_remote_url(remote_url)
        if from_remote:
            return f"project:{from_remote}"
    toplevel = _git_output(["rev-parse", "--show-toplevel"], cwd)
    folder = Path(toplevel) if toplevel else cwd
    return f"project:{_slugify(folder.name)}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cwd", default=".")
    args = parser.parse_args()
    print(derive_project_tag(Path(args.cwd).resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
