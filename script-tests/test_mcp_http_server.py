import os
import subprocess
import sys
import time
from pathlib import Path

import _mcp_server_lifecycle as lifecycle
from fastmcp.client.client import CallToolResult

_SCRIPT = Path(__file__).parent.parent / "shared" / "scripts" / "mcp_http_server.py"


def _spawn(tmp_path: Path, idle_timeout: str) -> tuple[subprocess.Popen, Path]:
    lock_file = tmp_path / "mcp-server.lock"
    env = {
        **os.environ,
        "MCP_LIFECYCLE_LOCK_PATH": str(lock_file),
        "MCP_PROXY_IDLE_TIMEOUT_SECONDS": idle_timeout,
        "PRIORIS_MCP_STORAGE_DIR": str(tmp_path / "storage"),
        "PRIORIS_MCP_NOTES_DIR": str(tmp_path / "notes"),
        "PRIORIS_MCP_VECTOR_DIR": str(tmp_path / "vectors"),
        "PRIORIS_MCP_GRAPH_DIR": str(tmp_path / "graph"),
    }
    proc = subprocess.Popen([sys.executable, str(_SCRIPT)], env=env)
    return proc, lock_file


def _wait_for_lock(lock_file: Path, timeout: float = 10.0) -> lifecycle.LockEntry:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        entry = lifecycle.read_lock(lock_file)
        if entry is not None and lifecycle.is_live(entry):
            return entry
        time.sleep(0.1)
    raise TimeoutError("server never became live")


def test_server_binds_writes_lock_and_serves_a_real_call(tmp_path):
    proc, lock_file = _spawn(tmp_path, idle_timeout="900")
    try:
        entry = _wait_for_lock(lock_file)
        assert entry["pid"] == proc.pid

        async def _call() -> CallToolResult:
            from fastmcp import Client

            async with Client(f"http://127.0.0.1:{entry['port']}/mcp") as c:
                return await c.call_tool(
                    "research_graph_write",
                    {
                        "op": "upsert_pointer",
                        "ref_type": "note",
                        "ref_id": "lifecycle-test",
                    },
                )

        import anyio

        result = anyio.run(_call)
        assert result.data is not None
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_server_self_shuts_down_after_idle_timeout_and_removes_lock(tmp_path):
    proc, lock_file = _spawn(tmp_path, idle_timeout="1")
    try:
        _wait_for_lock(lock_file)
        proc.wait(
            timeout=15
        )  # watchdog polls every 5s - a 1s idle timeout trips well inside this
        assert proc.returncode is not None
        assert not lock_file.exists()
    finally:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=10)
