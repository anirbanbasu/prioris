import os
from pathlib import Path

import anyio
from fastmcp import Client
from fastmcp.client.transports import PythonStdioTransport

_SCRIPT = Path(__file__).parent.parent / "shared" / "scripts" / "mcp_stdio_proxy.py"


def test_proxy_relays_a_real_tool_call_over_stdio_to_the_canonical_server():
    async def _call():
        # mcp's stdio_client only forwards a small safe-list of env vars (HOME, PATH, etc.)
        # to a spawned subprocess unless an explicit env is given - Client(str(_SCRIPT)) alone
        # would silently drop conftest.py's PRIORIS_MCP_GRAPH_DIR/etc. overrides, so the proxy
        # subprocess would fall back to the real default data dir instead of sharing this
        # session's canonical server. Pass the full parent env through explicitly.
        transport = PythonStdioTransport(script_path=_SCRIPT, env=dict(os.environ))
        async with Client(transport) as c:
            return await c.call_tool(
                "research_graph_write",
                {"op": "upsert_pointer", "ref_type": "note", "ref_id": "proxy-test"},
            )

    result = anyio.run(_call)
    assert result.data is not None
