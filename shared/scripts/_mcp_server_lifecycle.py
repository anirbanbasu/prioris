"""Connect-or-spawn helper for prioris-mcp's single canonical HTTP server.

Ladybug (this plugin's graph backend) allows exactly one READ_WRITE Database handle across
all processes on this machine - a second concurrent open raises a hard RuntimeError (see
docs.ladybugdb.com/concurrency). Before this module, _mcp_client.py's client() called
prioris_mcp.server.app() fresh in every shared/scripts/*.py process, each building its own
Database handle - which collided with the .mcp.json-spawned server the instant both were
alive at once (e.g. hooks/sync_note_pointer.sh firing while a script ran). See
docs/superpowers/plans/2026-09-21-single-mcp-server-lifecycle.md for the empirical
reproduction and full design.

Now exactly one process ever calls prioris_mcp.server.app(): the canonical HTTP server this
module spawns on demand (shared/scripts/mcp_http_server.py). Every other consumer -
shared/scripts/_mcp_client.py's client() and shared/scripts/mcp_stdio_proxy.py (.mcp.json's
stdio entry point) - calls connect_or_spawn() to get that one server's (host, port) and
connects to it as an HTTP client instead.
"""

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import TypedDict

os.environ.setdefault("PRIORIS_MCP_LOG_LEVEL", "WARNING")

HOST = "127.0.0.1"
_CLAIM_STALE_SECONDS = 30.0
_POLL_INTERVAL_SECONDS = 0.2


class LockEntry(TypedDict):
    pid: int | None
    port: int | None
    started_at: float


def default_lock_path() -> Path:
    """`<data_home>/prioris-mcp/mcp-server.lock` - sibling of the graph/notes/vector/downloads
    dirs prioris_mcp.EnvVars already defines, so this resolves to the same global location
    those do (or the same per-test tmp dir, under script-tests/conftest.py's env override)."""
    from prioris_mcp import EnvVars

    return Path(EnvVars.PRIORIS_MCP_GRAPH_DIR).parent / "mcp-server.lock"


def log_path(lock_file: Path) -> Path:
    return lock_file.with_name("mcp-server.log")


def find_free_port() -> int:
    """An OS-assigned free port on HOST, via the standard bind-to-0/close/reuse trick. Small
    window between this call returning and the caller actually binding that port - acceptable
    on a loopback, single-user, single-plugin server; a collision just means the next
    connect_or_spawn() call retries."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, 0))
        return s.getsockname()[1]


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, owned by someone else - still alive
    return True


def _port_open(port: int) -> bool:
    try:
        with socket.create_connection((HOST, port), timeout=0.5):
            return True
    except OSError:
        return False


def read_lock(lock_file: Path) -> LockEntry | None:
    try:
        return json.loads(lock_file.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def write_live_lock(lock_file: Path, pid: int, port: int) -> None:
    """Called by mcp_http_server.py once it's actually bound and serving."""
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    lock_file.write_text(
        json.dumps({"pid": pid, "port": port, "started_at": time.time()})
    )


def remove_lock(lock_file: Path) -> None:
    lock_file.unlink(missing_ok=True)


def is_live(entry: LockEntry) -> bool:
    pid, port = entry.get("pid"), entry.get("port")
    return pid is not None and port is not None and _pid_alive(pid) and _port_open(port)


def _attempt_exclusive_create(lock_file: Path) -> bool:
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w") as f:
        json.dump({"pid": None, "port": None, "started_at": time.time()}, f)
    return True


def _try_claim(lock_file: Path) -> bool:
    """Atomically create lock_file as a placeholder, claiming the right to spawn. Returns
    False if someone else already holds a live-or-recent claim."""
    if _attempt_exclusive_create(lock_file):
        return True
    existing = read_lock(lock_file)
    if existing is not None and (
        is_live(existing)
        or time.time() - existing.get("started_at", 0) < _CLAIM_STALE_SECONDS
    ):
        return False
    remove_lock(lock_file)  # stale placeholder or dead server - clear it and retry once
    return _attempt_exclusive_create(lock_file)


def _spawn_server(lock_file: Path) -> None:
    script = Path(__file__).with_name("mcp_http_server.py")
    env = {**os.environ, "MCP_LIFECYCLE_LOCK_PATH": str(lock_file)}
    with open(log_path(lock_file), "a") as log:
        subprocess.Popen(
            [sys.executable, str(script)],
            env=env,
            stdout=log,
            stderr=log,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
