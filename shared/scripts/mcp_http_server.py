"""The one canonical prioris-mcp server process - the sole thing that ever calls
prioris_mcp.server.app() and holds the Ladybug graph Database open.

Spawned on demand by _mcp_server_lifecycle.connect_or_spawn() (from
shared/scripts/_mcp_client.py or shared/scripts/mcp_stdio_proxy.py), never invoked directly.
Binds an OS-assigned port on 127.0.0.1, publishes {"pid","port","started_at"} to its info
file once that port genuinely accepts connections, and shuts itself down (removing that
info file) after MCP_PROXY_IDLE_TIMEOUT_SECONDS (default 900) with no incoming request.

This process holds the cross-process spawn mutex - an fcntl.flock on
_mcp_server_lifecycle.claim_path() - for its entire lifetime, so no second canonical server
can ever start while it lives, and the kernel releases that lock the moment it dies however
it dies. Normally the descriptor is inherited already-locked from whoever spawned us (see
_mcp_server_lifecycle._spawn_server); run directly, we take the lock ourselves and refuse to
start if someone else holds it. See
docs/superpowers/plans/2026-09-21-single-mcp-server-lifecycle.md.
"""

import asyncio
import contextlib
import fcntl
import os
import signal
import time
from pathlib import Path

from _mcp_server_lifecycle import (
    CLAIM_FD_ENV,
    HOST,
    claim_path,
    default_lock_path,
    find_free_port,
    read_lock,
    remove_lock,
    try_claim,
    write_live_lock,
)
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_IDLE_TIMEOUT_SECONDS = float(os.environ.get("MCP_PROXY_IDLE_TIMEOUT_SECONDS", "900"))
_WATCHDOG_INTERVAL_SECONDS = 5.0
_LOCK_FILE = (
    Path(os.environ["MCP_LIFECYCLE_LOCK_PATH"])
    if "MCP_LIFECYCLE_LOCK_PATH" in os.environ
    else default_lock_path()
)


class _ActivityTracker:
    def __init__(self) -> None:
        self.last_request_at = time.monotonic()

    def touch(self) -> None:
        self.last_request_at = time.monotonic()


class _IdleTrackingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, tracker: _ActivityTracker) -> None:
        super().__init__(app)
        self._tracker = tracker

    async def dispatch(self, request: Request, call_next) -> Response:
        self._tracker.touch()
        try:
            return await call_next(request)
        finally:
            # Also touch on the way out, so a single request that runs longer than the idle
            # timeout can't be SIGTERM'd out from under itself by the watchdog below.
            self._tracker.touch()


async def _idle_watchdog(tracker: _ActivityTracker) -> None:
    while True:
        await asyncio.sleep(_WATCHDOG_INTERVAL_SECONDS)
        if time.monotonic() - tracker.last_request_at > _IDLE_TIMEOUT_SECONDS:
            os.kill(os.getpid(), signal.SIGTERM)
            return


async def _announce_when_bound(port: int) -> None:
    """Publish the info file only once `port` actually accepts a connection.

    run_http_async() gives us no "server started" hook, and announcing before uvicorn has
    bound would make read_lock() briefly advertise a port nothing is listening on. Waiters
    do defend against that (is_live() TCP-connects), but announcing truthfully keeps the
    file's meaning simple and closes the window rather than relying on every reader to."""
    while True:
        try:
            _, writer = await asyncio.open_connection(HOST, port)
        except OSError:
            await asyncio.sleep(0.05)
            continue
        writer.close()
        with contextlib.suppress(Exception):
            await writer.wait_closed()
        write_live_lock(_LOCK_FILE, os.getpid(), port)
        return


async def _serve(port: int) -> None:
    # Deferred: this process only imports prioris_mcp once it has committed to being the one
    # canonical server - never at module import time.
    from prioris_mcp.server import app

    # uvicorn.Server.serve() (which run_http_async calls into) installs its own SIGTERM
    # handler for the duration of serving, then - once it exits, e.g. after our watchdog's
    # os.kill() below triggers a graceful shutdown - restores whatever handler was active
    # before and re-raises the captured signal so that handler can decide what to do. We
    # never installed one of our own, so that restored handler is Python's default
    # (terminate immediately), which kills this process before control ever returns to the
    # `finally` block below. A no-op handler here means that re-raised SIGTERM is safely
    # swallowed instead, so run_http_async can return normally and remove_lock() actually
    # runs.
    signal.signal(signal.SIGTERM, lambda signum, frame: None)

    tracker = _ActivityTracker()
    watchdog = asyncio.create_task(_idle_watchdog(tracker))
    announce = asyncio.create_task(_announce_when_bound(port))
    try:
        await app().run_http_async(
            host=HOST,
            port=port,
            middleware=[Middleware(_IdleTrackingMiddleware, tracker=tracker)],
            show_banner=False,
        )
    finally:
        watchdog.cancel()
        announce.cancel()
        # Only clear an entry we actually published. Blanket removal would let a doomed
        # second server (however it got started) delete a healthy peer's entry on its way
        # out, wedging every client into respawn attempts against a server that is fine.
        entry = read_lock(_LOCK_FILE)
        if entry is not None and entry.get("pid") == os.getpid():
            remove_lock(_LOCK_FILE)


def _inherited_claim() -> int | None:
    """The descriptor our spawner passed down, if it really is an already-held claim on our
    own claim file.

    A stale MCP_LIFECYCLE_CLAIM_FD left in the environment (it is inherited like any other
    var) would otherwise make us believe we hold the mutex when we don't, so verify rather
    than trust: the descriptor must point at the same inode as claim_path(), and re-flocking
    it must succeed - which it always does for a lock this open file description already
    holds, and never does for one someone else holds."""
    raw = os.environ.get(CLAIM_FD_ENV)
    if raw is None:
        return None
    claim = claim_path(_LOCK_FILE)
    try:
        fd = int(raw)
        if not claim.exists() or os.fstat(fd).st_ino != claim.stat().st_ino:
            return None
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (OSError, ValueError):
        return None
    return fd


def _hold_claim() -> int:
    """This process's handle on the cross-process spawn mutex, held until we exit.

    Almost always inherited already-locked from our spawner, which is what makes the claim
    seamless: the flock is never momentarily unheld between the spawn decision and this
    process taking over. Run directly (as the tests do), take it here instead."""
    inherited = _inherited_claim()
    if inherited is not None:
        return inherited
    fd = try_claim(_LOCK_FILE)
    if fd is None:
        raise SystemExit(
            "another prioris-mcp canonical server already holds "
            f"{claim_path(_LOCK_FILE)} - refusing to start a second one"
        )
    return fd


def main() -> int:
    _hold_claim()  # deliberately never closed: the kernel releases it when we die
    asyncio.run(_serve(find_free_port()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
