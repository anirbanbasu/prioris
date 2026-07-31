#!/usr/bin/env python3
"""Base64-encode a local PDF for research_localfile_fetch_full_text's content_base64.

Exists because shell base64 flags aren't portable (`base64 -i` on macOS/BSD vs
`base64 -w0` on GNU coreutils) - this gives one command that behaves the same
everywhere Python does. See ../local-file-handling.md.

Usage:
    uv run --project <plugin root> python shared/scripts/encode_local_pdf.py <path-to-pdf>

Prints the base64 string to stdout (no trailing newline, so it can be used
as-is) on success. On failure, prints a one-line reason to stderr and exits
non-zero - this is a diagnosis of the *local* file, not the server call, so
it deliberately doesn't retry with variations (see local-file-handling.md).
"""

import base64
import sys
from pathlib import Path

PDF_MAGIC_PREFIX = b"%PDF-"


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {Path(sys.argv[0]).name} <path-to-pdf>", file=sys.stderr)
        return 2

    path = Path(sys.argv[1])
    try:
        content = path.read_bytes()
    except FileNotFoundError:
        print(f"no such file: {path}", file=sys.stderr)
        return 1
    except IsADirectoryError:
        print(f"is a directory, not a file: {path}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"couldn't read {path}: {exc}", file=sys.stderr)
        return 1

    if not content.startswith(PDF_MAGIC_PREFIX):
        print(f"{path} does not sniff as a PDF (missing %PDF- header)", file=sys.stderr)
        return 1

    sys.stdout.write(base64.b64encode(content).decode("ascii"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
