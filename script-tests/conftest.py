"""Shared setup/fixtures for shared/scripts/ tests.

The env vars below must be set before anything imports `prioris_mcp`: its `EnvVars` class
(see prioris_mcp/__init__.py) reads them once, at class-body execution time, into plain class
attributes - a monkeypatch.setenv() inside a test or fixture is always too late, since by then
prioris_mcp has typically already been imported (transitively, via importing one of the scripts
under test). pytest imports conftest.py before any test_*.py in this directory, which is the
only point early enough.
"""

import os
import shutil
import tempfile

import pytest

_TEST_STORAGE_DIR = tempfile.mkdtemp(prefix="prioris-mcp-script-tests-")
os.environ["PRIORIS_MCP_STORAGE_DIR"] = _TEST_STORAGE_DIR
_TEST_NOTES_DIR = tempfile.mkdtemp(prefix="prioris-mcp-script-tests-notes-")
os.environ["PRIORIS_MCP_NOTES_DIR"] = _TEST_NOTES_DIR
_TEST_VECTOR_DIR = tempfile.mkdtemp(prefix="prioris-mcp-script-tests-vectors-")
os.environ["PRIORIS_MCP_VECTOR_DIR"] = _TEST_VECTOR_DIR
os.environ.setdefault("PRIORIS_MCP_LOG_LEVEL", "WARNING")


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    shutil.rmtree(_TEST_STORAGE_DIR, ignore_errors=True)
    shutil.rmtree(_TEST_NOTES_DIR, ignore_errors=True)
    shutil.rmtree(_TEST_VECTOR_DIR, ignore_errors=True)


@pytest.fixture
def tiny_pdf_bytes() -> bytes:
    """Content that sniffs as a PDF by magic-byte prefix only.

    LocalFileProvider._validate_and_persist never parses PDF structure on upload (only
    parse_full_text does, via the LiteParse backend) - see prioris-mcp's providers/localfile.py -
    so this is sufficient for every upload-path test here without needing a real PDF fixture.
    """
    return b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n%%EOF\n"
