"""The one canonical prioris-mcp server process - the sole thing that ever calls
prioris_mcp.server.app() and holds the Ladybug graph Database open.

Spawned on demand by _mcp_server_lifecycle.connect_or_spawn() (from
shared/scripts/_mcp_client.py or shared/scripts/mcp_stdio_proxy.py), never invoked directly.
Binds an OS-assigned port on 127.0.0.1, writes {"pid","port","started_at"} to its lock file
once actually serving, and shuts itself down (removing that lock) after
MCP_PROXY_IDLE_TIMEOUT_SECONDS (default 900) with no incoming request. See
docs/superpowers/plans/2026-09-21-single-mcp-server-lifecycle.md.
"""

import asyncio
import os
import signal
import time
from pathlib import Path

from _mcp_server_lifecycle import (
    HOST,
    default_lock_path,
    find_free_port,
    remove_lock,
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
        return await call_next(request)


async def _idle_watchdog(tracker: _ActivityTracker) -> None:
    while True:
        await asyncio.sleep(_WATCHDOG_INTERVAL_SECONDS)
        if time.monotonic() - tracker.last_request_at > _IDLE_TIMEOUT_SECONDS:
            os.kill(os.getpid(), signal.SIGTERM)
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
    write_live_lock(_LOCK_FILE, os.getpid(), port)
    try:
        await app().run_http_async(
            host=HOST,
            port=port,
            middleware=[Middleware(_IdleTrackingMiddleware, tracker=tracker)],
            show_banner=False,
        )
    finally:
        watchdog.cancel()
        remove_lock(_LOCK_FILE)


def main() -> int:
    asyncio.run(_serve(find_free_port()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
