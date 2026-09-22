import contextlib
import os
import time
from pathlib import Path

import anyio
from fastmcp import Client
from fastmcp.client.transports import PythonStdioTransport

_SCRIPT = Path(__file__).parent.parent / "shared" / "scripts" / "mcp_stdio_proxy.py"


def test_proxy_relays_a_real_tool_call_over_stdio_to_the_canonical_server(tmp_path):
    async def _call():
        # mcp's stdio_client only forwards a small safe-list of env vars (HOME, PATH, etc.)
        # to a spawned subprocess unless an explicit env is given - Client(str(_SCRIPT)) alone
        # would silently drop conftest.py's PRIORIS_MCP_GRAPH_DIR/etc. overrides, so the proxy
        # subprocess would fall back to the real default data dir instead of sharing this
        # session's canonical server. Pass the full parent env through explicitly.
        #
        # log_file must be a real file, not fastmcp's default of sys.stderr: it's handed to
        # subprocess.Popen(stderr=...), which needs a real fileno(). Under pytest's
        # --capture=tee-sys (as CI runs), sys.stderr is a fileno-less TeeCaptureIO, so the
        # default raises "UnsupportedOperation: fileno" while connecting.
        transport = PythonStdioTransport(
            script_path=_SCRIPT,
            env=dict(os.environ),
            log_file=tmp_path / "proxy-stderr.log",
        )
        async with Client(transport) as c:
            return await c.call_tool(
                "research_graph_write",
                {"op": "upsert_pointer", "ref_type": "note", "ref_id": "proxy-test"},
            )

    result = anyio.run(_call)
    assert result.data is not None


def _server_entry(lock_file: Path):
    import _mcp_server_lifecycle as lifecycle

    return lifecycle.read_lock(lock_file)


def test_proxy_respawns_the_canonical_server_after_it_idle_times_out(tmp_path):
    """The proxy must re-resolve the canonical server per request, not once at startup.

    The server self-terminates after MCP_PROXY_IDLE_TIMEOUT_SECONDS of quiet, but the proxy
    lives as long as the Claude Code session - which routinely idles longer than that. A URL
    captured at startup left every later native tool call pinned to a dead port for the rest
    of the session. Here the idle timeout is 1s: make a call, let the server actually die,
    then call again and require it to work against a genuinely new server process.
    """
    lock_file = tmp_path / "mcp-server.lock"
    env = {
        **os.environ,
        "MCP_PROXY_IDLE_TIMEOUT_SECONDS": "1",
        "PRIORIS_MCP_STORAGE_DIR": str(tmp_path / "storage"),
        "PRIORIS_MCP_NOTES_DIR": str(tmp_path / "notes"),
        "PRIORIS_MCP_VECTOR_DIR": str(tmp_path / "vectors"),
        "PRIORIS_MCP_GRAPH_DIR": str(tmp_path / "graph"),
    }

    async def _call() -> tuple[int, int]:
        transport = PythonStdioTransport(
            script_path=_SCRIPT,
            env=env,
            log_file=tmp_path / "proxy-stderr.log",
        )
        async with Client(transport, timeout=90) as c:
            first = await c.call_tool(
                "research_graph_write",
                {"op": "upsert_pointer", "ref_type": "note", "ref_id": "proxy-idle-1"},
            )
            assert first.data is not None
            entry = _server_entry(lock_file)
            assert entry is not None and entry["pid"] is not None
            first_pid = entry["pid"]

            # Watchdog polls every 5s against a 1s idle timeout, so this is the real thing:
            # the server we just talked to genuinely exits and clears its own entry.
            deadline = time.monotonic() + 40
            while time.monotonic() < deadline and _server_entry(lock_file) is not None:
                await anyio.sleep(0.2)
            assert _server_entry(lock_file) is None, "server never idled out"

            second = await c.call_tool(
                "research_graph_write",
                {"op": "upsert_pointer", "ref_type": "note", "ref_id": "proxy-idle-2"},
            )
            assert second.data is not None
            entry = _server_entry(lock_file)
            assert entry is not None and entry["pid"] is not None
            return first_pid, entry["pid"]

    try:
        first_pid, second_pid = anyio.run(_call)
        assert second_pid != first_pid  # transparently respawned, not a stale reconnect
    finally:
        import _mcp_server_lifecycle as lifecycle

        entry = lifecycle.read_lock(lock_file)
        pid = entry.get("pid") if entry is not None else None
        if pid is not None:
            with contextlib.suppress(ProcessLookupError):
                os.kill(pid, 15)
