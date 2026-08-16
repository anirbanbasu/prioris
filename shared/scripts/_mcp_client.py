"""Shared in-process fastmcp client helper for shared/scripts/manage_*.py task scripts.

Every manage_*.py script needs the same three things: prioris_mcp's RichHandler logging
suppressed before import (see below), a Client against the same in-process
prioris_mcp.server.app() instance .mcp.json launches, and a validate-or-exit wrapper around
call_tool/read_resource so a real ToolError/McpError/ValidationError becomes a one-line stderr
message and a non-zero exit code - exactly like pdf_chunk_upload_helper.py's own upload() already
does by hand. Factored out here so every manage_*.py script doesn't duplicate this ~15 lines.

Import this module (or anything that imports it) before importing anything else that
transitively imports prioris_mcp: the PRIORIS_MCP_LOG_LEVEL default below must land before
prioris_mcp/__init__.py's own import-time logging.basicConfig() runs, or its RichHandler starts
writing to stdout and corrupts these scripts' one-JSON-line-per-call stdout contract. See
pdf_chunk_upload_helper.py's own identical comment for the original precedent.
"""

import json
import os
import sys
from collections.abc import Mapping
from typing import cast, overload

os.environ.setdefault("PRIORIS_MCP_LOG_LEVEL", "WARNING")

from fastmcp import Client
from fastmcp.exceptions import ToolError
from mcp.shared.exceptions import McpError
from mcp.types import TextResourceContents
from prioris_mcp.server import app
from pydantic import BaseModel, ValidationError


def client() -> Client:
    """A fresh Client against the same in-process server .mcp.json launches."""
    return Client(transport=app(), timeout=60)


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
    except ToolError as exc:
        sys.exit(str(exc))
    if model is None:
        return result.data
    try:
        return model.model_validate(result.structured_content)
    except ValidationError as exc:
        sys.exit(f"unexpected response shape from prioris-mcp: {exc}")


async def read_resource[ModelT: BaseModel](
    active_client: Client, uri: str, model: type[ModelT]
) -> ModelT:
    """Read `uri`'s one text block, parse it as JSON, and validate against `model`, or exit(1)."""
    try:
        contents = await active_client.read_resource(uri)
    except McpError as exc:
        sys.exit(str(exc))
    try:
        payload = json.loads(cast(TextResourceContents, contents[0]).text)
        return model.model_validate(payload)
    except (AttributeError, IndexError, json.JSONDecodeError, ValidationError) as exc:
        sys.exit(f"unexpected response shape from prioris-mcp: {exc}")
