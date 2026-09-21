"""The .mcp.json entry point - a thin stdio<->HTTP relay, not a server.

Speaks MCP over stdio to Claude Code (or any other MCP host), exactly like the old
`uv run prioris-mcp` did, but never touches prioris_mcp/Ladybug itself: every call is relayed
to the one canonical HTTP server (shared/scripts/mcp_http_server.py), started on demand via
_mcp_server_lifecycle.connect_or_spawn() if not already running.

Crucially, that resolution happens per relayed request, not once at startup. This process
outlives the canonical server by design - the server self-terminates after
MCP_PROXY_IDLE_TIMEOUT_SECONDS (default 900) of quiet, while a Claude Code session routinely
goes longer than that between native tool calls. A URL captured at startup would leave every
later call pinned to a dead port for the rest of the session; re-resolving makes this relay
self-healing (it transparently respawns the server), the same way _mcp_client.client()
already is for shared/scripts/*.py. See
docs/superpowers/plans/2026-09-21-single-mcp-server-lifecycle.md.
"""

import sys

import anyio
import anyio.to_thread
from _mcp_server_lifecycle import connect_or_spawn
from fastmcp.client import Client
from fastmcp.server.providers.proxy import FastMCPProxy, ProxyClient

_backend: tuple[str, ProxyClient] | None = None


async def _client_factory() -> Client:
    """A fresh backend client for one relayed request, aimed at wherever the canonical
    server lives *right now*.

    FastMCPProxy calls this per request (ProxyTool.run and friends each do
    `await self._get_client()`, which awaits an async factory), which is the whole point:
    connect_or_spawn() re-resolves - and respawns, if the server has since idled out - on
    every call. It is synchronous and can block for seconds while a replacement server boots,
    so it runs in a worker thread rather than stalling the stdio loop this process is also
    serving Claude Code on. The ProxyClient itself is cached per URL and copied with .new()
    per request, mirroring what fastmcp's own create_proxy() factory does, so building its
    forwarding handlers costs once per server generation, not once per tool call."""
    global _backend
    host, port = await anyio.to_thread.run_sync(connect_or_spawn)
    url = f"http://{host}:{port}/mcp"
    if _backend is None or _backend[0] != url:
        _backend = (url, ProxyClient(url))
    return _backend[1].new()


async def _run() -> None:
    proxy = FastMCPProxy(client_factory=_client_factory)
    await proxy.run_stdio_async(show_banner=False)


def main() -> int:
    try:
        connect_or_spawn()  # fail fast, and with one clean line, if it can't come up at all
    except RuntimeError as exc:
        sys.exit(str(exc))
    anyio.run(_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
