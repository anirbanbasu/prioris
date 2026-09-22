"""Shared connect-or-spawn fastmcp client helper for shared/scripts/manage_*.py task scripts.

Every manage_*.py script needs the same three things: a Client against the one canonical
prioris-mcp HTTP server (spawned on demand, never built in this process - see
_mcp_server_lifecycle.py and docs/superpowers/plans/2026-09-21-single-mcp-server-lifecycle.md),
a validate-or-exit wrapper around call_tool/read_resource so a real
ToolError/MCPError/ValidationError becomes a one-line stderr message and a non-zero exit code -
exactly like pdf_chunk_upload_helper.py's own upload() already does by hand. Factored out here
so every manage_*.py script doesn't duplicate this ~15 lines.
"""

import json
import sys
from collections.abc import Mapping
from typing import cast, overload

from _mcp_server_lifecycle import connect_or_spawn
from fastmcp import Client
from fastmcp.exceptions import ToolError
from mcp.shared.exceptions import MCPError
from mcp.types import TextResourceContents
from pydantic import BaseModel, ValidationError


def client() -> Client:
    """A fresh Client against the one canonical prioris-mcp server, spawning it first if
    nothing is currently running."""
    host, port = connect_or_spawn()
    return Client(f"http://{host}:{port}/mcp", timeout=60)


def _unwrap_fastmcp_result(result: object) -> object | None:
    """The payload inside FastMCP's `{"result": ...}` envelope, or None if not enveloped.

    FastMCP 4.x cannot express a discriminated-union return type (prioris_mcp's
    research_graph_query/research_graph_analyze) as a top-level MCP output schema, so it marks
    such tools `x-fastmcp-wrap-result` and ships the payload as `{"result": {...}}`, flagging
    the wrapping in the call result's `_meta` as `{"fastmcp": {"wrap_result": True}}`. That flag
    - not the envelope's shape - is what we key on, so a tool whose genuine payload happens to
    be a lone `result` field is never mistaken for an envelope.

    `result.data` looks like it should solve this, but it is not reliable here: fastmcp hands
    back an internal `Root` wrapper model rather than a plain dict for some plain-return-type
    tools (research_notes_create/research_notes_search), which pydantic then refuses.
    """
    meta = getattr(result, "meta", None) or {}
    fastmcp_meta = meta.get("fastmcp") if isinstance(meta, Mapping) else None
    if not (isinstance(fastmcp_meta, Mapping) and fastmcp_meta.get("wrap_result")):
        return None
    content = getattr(result, "structured_content", None)
    if not (isinstance(content, Mapping) and "result" in content):
        return None
    return content["result"]


@overload
async def call_tool[ModelT: BaseModel](
    active_client: Client,
    name: str,
    arguments: Mapping[str, object],
    model: type[ModelT],
) -> ModelT: ...


@overload
async def call_tool(
    active_client: Client,
    name: str,
    arguments: Mapping[str, object],
    model: None = None,
) -> object: ...


async def call_tool[ModelT: BaseModel](
    active_client: Client,
    name: str,
    arguments: Mapping[str, object],
    model: type[ModelT] | None = None,
) -> ModelT | object:
    """Call `name`, validate its structured_content against `model`, or exit(1) on failure.

    `model=None` (e.g. research_notes_delete's plain bool result) skips validation and returns
    `result.data` - fastmcp's own already-deserialized value for a non-object tool result - as-is.
    """
    try:
        result = await active_client.call_tool(name, arguments=dict(arguments))
    except (ToolError, MCPError) as exc:
        sys.exit(str(exc))
    if model is None:
        return result.data
    try:
        return model.model_validate(result.structured_content)
    except ValidationError as exc:
        unwrapped = _unwrap_fastmcp_result(result)
        if unwrapped is not None:
            try:
                return model.model_validate(unwrapped)
            except ValidationError:
                pass  # fall through and report the original, un-unwrapped error
        sys.exit(f"unexpected response shape from prioris-mcp: {exc}")


async def read_resource[ModelT: BaseModel](
    active_client: Client, uri: str, model: type[ModelT]
) -> ModelT:
    """Read `uri`'s one text block, parse it as JSON, and validate against `model`, or exit(1)."""
    try:
        contents = await active_client.read_resource(uri)
    except (ToolError, MCPError) as exc:
        sys.exit(str(exc))
    try:
        payload = json.loads(cast(TextResourceContents, contents[0]).text)
        return model.model_validate(payload)
    except (AttributeError, IndexError, json.JSONDecodeError, ValidationError) as exc:
        sys.exit(f"unexpected response shape from prioris-mcp: {exc}")
