"""Upload a local PDF to prioris-mcp via the three-phase chunked-upload flow.

Drives research_localfile_begin_upload -> research_localfile_upload_chunk (looped) ->
research_localfile_finalize_upload itself, as its own in-process fastmcp client against the
same prioris_mcp.server.app() instance .mcp.json launches - so the base64 of every chunk stays
inside this script's own memory and never has to pass through the calling agent's context. Only
the final result (or a one-line error) is printed. See ../local-file-handling.md.

Usage:
    uv run --project <plugin root> python shared/scripts/pdf_chunk_upload_helper.py <path-to-pdf> [--filename NAME]

On success, prints the finalize_upload result JSON to stdout (same shape as
research_localfile_fetch_full_text: id, location, format, size_bytes, served_from_storage,
resource_uri) and exits 0. On failure - a local problem (missing file, not a PDF), an MCP-side
ToolError raised by any of the three calls, or a response that doesn't validate against the
expected output model - prints a one-line reason to stderr and exits non-zero. Deliberately does
not retry with variations; a `file_too_large`/`invalid_request` failure is a property of the
file's actual content, not something fixable by re-encoding it differently.
"""

import argparse
import base64
import os
import sys
from pathlib import Path

# Must precede importing prioris_mcp: its RichHandler-based logging.basicConfig() (configured at
# import time, from PRIORIS_MCP_LOG_LEVEL) writes to stdout by default, which would otherwise mix
# server log lines into the one JSON line this script promises on stdout. Only overridden if the
# caller hasn't already set a level explicitly.
os.environ.setdefault("PRIORIS_MCP_LOG_LEVEL", "WARNING")

import anyio
from fastmcp import Client
from fastmcp.exceptions import ToolError
from prioris_mcp.models.localfile import (
    LocalFileBeginUploadResult,
    LocalFileFetchResult,
    LocalFileUploadChunkResult,
)
from prioris_mcp.server import app
from pydantic import ValidationError

PDF_MAGIC_PREFIX = b"%PDF-"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument(
        "--filename",
        default=None,
        help="Filename hint stored for reference only (default: basename)",
    )
    return parser.parse_args()


def read_and_sniff(path: Path) -> bytes:
    try:
        content = path.read_bytes()
    except FileNotFoundError:
        sys.exit(f"no such file: {path}")
    except IsADirectoryError:
        sys.exit(f"is a directory, not a file: {path}")
    except OSError as exc:
        sys.exit(f"couldn't read {path}: {exc}")
    if not content.startswith(PDF_MAGIC_PREFIX):
        sys.exit(f"{path} does not sniff as a PDF (missing %PDF- header)")
    return content


def chunk_base64(encoded: str, max_chunk_bytes: int) -> list[str]:
    """Split a base64 string into pieces that each decode to at most `max_chunk_bytes`.

    Slicing at a multiple-of-4-chars boundary keeps every piece independently valid base64 (each
    encodes a whole number of 3-byte groups, with '=' padding only ever appearing in the final
    piece), so the server can decode each `chunk_base64` argument on its own.
    """
    chars_per_chunk = (max_chunk_bytes // 3) * 4
    return [
        encoded[i : i + chars_per_chunk]
        for i in range(0, len(encoded), chars_per_chunk)
    ] or [""]


async def upload(content: bytes, filename: str | None) -> LocalFileFetchResult:
    encoded = base64.b64encode(content).decode("ascii")
    async with Client(transport=app(), timeout=60) as client:
        try:
            begin_result = await client.call_tool(
                "research_localfile_begin_upload", arguments={"filename": filename}
            )
            begin = LocalFileBeginUploadResult.model_validate(
                begin_result.structured_content
            )

            for index, piece in enumerate(chunk_base64(encoded, begin.max_chunk_bytes)):
                chunk_result = await client.call_tool(
                    "research_localfile_upload_chunk",
                    arguments={
                        "session_id": begin.session_id,
                        "index": index,
                        "chunk_base64": piece,
                    },
                )
                LocalFileUploadChunkResult.model_validate(
                    chunk_result.structured_content
                )

            finalize_result = await client.call_tool(
                "research_localfile_finalize_upload",
                arguments={"session_id": begin.session_id},
            )
            return LocalFileFetchResult.model_validate(
                finalize_result.structured_content
            )
        except ToolError as exc:
            sys.exit(str(exc))
        except ValidationError as exc:
            sys.exit(f"unexpected response shape from prioris-mcp: {exc}")


def main() -> int:
    args = parse_args()
    content = read_and_sniff(args.path)
    filename = args.filename or args.path.name

    result = anyio.run(upload, content, filename)
    print(result.model_dump_json(by_alias=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
