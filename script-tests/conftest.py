"""Shared setup/fixtures for shared/scripts/ tests.

The env vars below must be set before anything imports `prioris_mcp`: its `EnvVars` class
(see prioris_mcp/__init__.py) reads them once, at class-body execution time, into plain class
attributes - a monkeypatch.setenv() inside a test or fixture is always too late, since by then
prioris_mcp has typically already been imported (transitively, via importing one of the scripts
under test). pytest imports conftest.py before any test_*.py in this directory, which is the
only point early enough.
"""

import contextlib
import os
import shutil
import tempfile
import time
from pathlib import Path

import pytest

# One session root with the four data dirs *nested under it*, not four independent
# mkdtemp()s. _mcp_server_lifecycle.default_lock_path() derives the canonical server's lock
# from `Path(PRIORIS_MCP_GRAPH_DIR).parent`, so with independent temp dirs that parent was
# literally /tmp - putting this session's lock and log at the shared, world-writable
# /tmp/mcp-server.{lock,log}, where concurrent pytest runs would fight over them and the log
# would grow forever because nothing ever cleaned it up. Nested, they land at
# _TEST_ROOT/mcp-server.{lock,log} and die with the root in pytest_sessionfinish.
_TEST_ROOT = Path(tempfile.mkdtemp(prefix="prioris-mcp-script-tests-"))
for _var, _sub in (
    ("PRIORIS_MCP_STORAGE_DIR", "storage"),
    ("PRIORIS_MCP_NOTES_DIR", "notes"),
    ("PRIORIS_MCP_VECTOR_DIR", "vectors"),
    ("PRIORIS_MCP_GRAPH_DIR", "graph"),
):
    _dir = _TEST_ROOT / _sub
    _dir.mkdir(parents=True, exist_ok=True)
    os.environ[_var] = str(_dir)
os.environ.setdefault("PRIORIS_MCP_LOG_LEVEL", "WARNING")


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    import _mcp_server_lifecycle as lifecycle

    entry = lifecycle.read_lock(lifecycle.default_lock_path())
    pid = entry.get("pid") if entry is not None else None
    if pid is not None:
        with contextlib.suppress(ProcessLookupError):
            os.kill(pid, 15)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and lifecycle._pid_alive(pid):
            time.sleep(0.1)
    shutil.rmtree(_TEST_ROOT, ignore_errors=True)


@pytest.fixture
def tiny_pdf_bytes() -> bytes:
    """Content that sniffs as a PDF by magic-byte prefix only.

    LocalFileProvider._validate_and_persist never parses PDF structure on upload (only
    parse_full_text does, via the LiteParse backend) - see prioris-mcp's providers/localfile.py -
    so this is sufficient for every upload-path test here without needing a real PDF fixture.
    """
    return b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n%%EOF\n"
