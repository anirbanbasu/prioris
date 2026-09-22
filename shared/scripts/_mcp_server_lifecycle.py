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

Mutual exclusion between would-be spawners is a real OS-level mutex, not a staleness
heuristic. Two files are involved, with deliberately different lifetimes:

- The claim file (`mcp-server.flock`, see claim_path()) is created once and never unlinked.
  Its only job is to anchor an `fcntl.flock(LOCK_EX | LOCK_NB)`. A caller that wins that
  flock has won the exclusive right to spawn; a caller that doesn't knows, with no timing
  guesswork at all, that someone else is either mid-spawn or already serving. Because the
  file is never removed, there is no unlink/recreate window for two racers to slip through -
  the flock itself, not the file's existence, is the mutex.

  The winner hands the still-locked descriptor straight to the server it spawns, via
  `subprocess.Popen(pass_fds=...)`: fork/exec preserves the *open file description*, and an
  flock belongs to that description rather than to a process, so the lock passes to the child
  without ever being released. The spawner then closes its own copy and the server holds the
  lock for its entire lifetime. The kernel drops it the instant that process dies - cleanly,
  by SIGKILL, or by crashing - so a "stale lock" state simply does not exist here, and
  neither does a staleness timeout to tune against connect_or_spawn()'s own timeout.

- The info file (`mcp-server.lock`, the path default_lock_path() returns) carries the
  server's `{pid, port, started_at}` for everyone else to read. Only the flock holder ever
  writes it, and write_live_lock() writes it atomically (temp file + os.replace), so a
  concurrent reader sees either the whole previous entry or the whole new one, never a
  half-written one. Readers still never trust its mere presence: is_live() also confirms the
  pid exists and the port actually accepts a TCP connection.
"""

import fcntl
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
_POLL_INTERVAL_SECONDS = 0.2

# Env var carrying the inherited, already-flocked claim descriptor to a spawned server.
CLAIM_FD_ENV = "MCP_LIFECYCLE_CLAIM_FD"

# Canonical servers *this* process spawned, kept so they can be reaped rather than left as
# zombies. A zombie still answers os.kill(pid, 0), which would make _pid_alive() - and every
# "wait for it to exit" poll built on it - structurally unable to observe a clean exit.
_SPAWNED: dict[int, "subprocess.Popen[bytes]"] = {}


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


def claim_path(lock_file: Path) -> Path:
    """The flock anchor beside `lock_file`. Created once, never unlinked - see module
    docstring for why removing it would reintroduce the race it exists to close."""
    return lock_file.with_name("mcp-server.flock")


def find_free_port() -> int:
    """An OS-assigned free port on HOST, via the standard bind-to-0/close/reuse trick. Small
    window between this call returning and the caller actually binding that port - acceptable
    on a loopback, single-user, single-plugin server; a collision just means the next
    connect_or_spawn() call retries."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, 0))
        return s.getsockname()[1]


def reap_spawned() -> None:
    """Collect any canonical server this process spawned that has since exited, so its pid
    stops resolving instead of lingering as a zombie. Cheap and non-blocking (waitpid
    WNOHANG, via Popen.poll)."""
    for pid, proc in list(_SPAWNED.items()):
        if proc.poll() is not None:
            _SPAWNED.pop(pid, None)


def _pid_alive(pid: int) -> bool:
    reap_spawned()  # a zombie answers kill(pid, 0); reap ours first so this stays truthful
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
    """Publish the canonical server's `{pid, port, started_at}`, atomically.

    Called by mcp_http_server.py once its port is genuinely accepting connections (it polls
    its own socket before announcing), and only ever by the process holding the flock. The
    temp-file-plus-os.replace dance matters because connect_or_spawn()'s waiters poll this
    file: a plain write_text() can be read mid-write and parsed as truncated JSON."""
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = lock_file.with_name(f"{lock_file.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps({"pid": pid, "port": port, "started_at": time.time()}))
    os.replace(tmp, lock_file)


def remove_lock(lock_file: Path) -> None:
    """Drop the info file. Never touches the flock anchor, which outlives every process."""
    lock_file.unlink(missing_ok=True)


def is_live(entry: LockEntry) -> bool:
    pid, port = entry.get("pid"), entry.get("port")
    return pid is not None and port is not None and _pid_alive(pid) and _port_open(port)


def try_claim(lock_file: Path) -> int | None:
    """Try to win the exclusive right to spawn the canonical server.

    Returns an open descriptor holding `flock(LOCK_EX | LOCK_NB)` on claim_path(lock_file),
    or None if another process holds it (already serving, or mid-spawn). The caller owns the
    returned descriptor: hand it to the spawned server via Popen(pass_fds=...) and then close
    this copy, or close it outright to release the claim. Letting it leak would hold the
    mutex for the rest of this process's life."""
    path = claim_path(lock_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        # BlockingIOError when someone else holds it. Any other OSError (e.g. ENOLCK) is
        # treated the same way on purpose: "assume a server may exist and wait" is the safe
        # direction to fail, since the unsafe one is spawning a second graph writer.
        os.close(fd)
        return None
    return fd


def _spawn_server(lock_file: Path, claim_fd: int) -> "subprocess.Popen[bytes]":
    """Launch the canonical server, handing it `claim_fd` so the flock is never released
    between "this process decided to spawn" and "that process is serving"."""
    script = Path(__file__).with_name("mcp_http_server.py")
    env = {
        **os.environ,
        "MCP_LIFECYCLE_LOCK_PATH": str(lock_file),
        CLAIM_FD_ENV: str(claim_fd),
    }
    with open(log_path(lock_file), "a") as log:
        proc = subprocess.Popen(
            [sys.executable, str(script)],
            env=env,
            stdout=log,
            stderr=log,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            pass_fds=(claim_fd,),
        )
    _SPAWNED[proc.pid] = proc
    return proc


def connect_or_spawn(
    *, timeout: float = 30.0, lock_file: Path | None = None
) -> tuple[str, int]:
    """The (host, port) of the one canonical prioris-mcp HTTP server, spawning it first (as a
    detached background process) if nothing is currently alive at lock_file.

    Safe to call from any number of processes at once: at most one of them wins the flock in
    try_claim() and spawns; the rest keep polling until that winner publishes its (host,
    port). Cheap enough to call on every single request - callers should, since re-resolving
    is what makes them self-healing against the server's idle timeout.

    The claim is retried, not attempted once, because "someone holds the flock" is not the
    same as "a server is coming up". A server that has already torn down its listener and
    cleared its info file still holds the flock until its process fully exits, and that exit
    can take a moment (interpreter teardown, closing the graph database). Waiting through
    that is correct - starting a replacement before the old process released the database is
    exactly the collision this module exists to prevent - but the waiter has to re-attempt
    the claim afterwards rather than wait forever for a publisher that will never come."""
    lock_file = lock_file or default_lock_path()
    deadline = time.monotonic() + timeout
    spawned = False
    while True:
        reap_spawned()
        entry = read_lock(lock_file)
        if entry is not None and is_live(entry):
            port = entry["port"]
            assert port is not None
            return HOST, port
        if not spawned:
            # Only ever once per call: if our own server died on startup, respawning on a
            # 200ms loop would just restart a crashing process until the deadline.
            claim_fd = try_claim(lock_file)
            if claim_fd is not None:
                try:
                    _spawn_server(lock_file, claim_fd)
                    spawned = True
                finally:
                    # The spawned server now shares this descriptor's open file description,
                    # so the flock stays held by it once we drop our own copy.
                    os.close(claim_fd)
        if time.monotonic() >= deadline:
            raise RuntimeError(
                f"prioris-mcp canonical server did not become ready within {timeout}s "
                f"(see {log_path(lock_file)})"
            )
        time.sleep(_POLL_INTERVAL_SECONDS)
