"""The .mcp.json entry point - a thin stdio<->HTTP relay, not a server.

Speaks MCP over stdio to Claude Code (or any other MCP host), exactly like the old
`uv run prioris-mcp` did, but never touches prioris_mcp/Ladybug itself: every call is relayed
to the one canonical HTTP server (shared/scripts/mcp_http_server.py), started on demand via
_mcp_server_lifecycle.connect_or_spawn() if not already running. See
docs/superpowers/plans/2026-09-21-single-mcp-server-lifecycle.md.
"""

import anyio
from _mcp_server_lifecycle import connect_or_spawn
from fastmcp.server import create_proxy


async def _run(url: str) -> None:
    proxy = create_proxy(url)
    await proxy.run_stdio_async(show_banner=False)


def main() -> int:
    host, port = connect_or_spawn()
    anyio.run(_run, f"http://{host}:{port}/mcp")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
