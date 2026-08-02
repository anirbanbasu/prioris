"""Extract a canonical (provider, identifier) pair from a paper URL or bare DOI.

Implements the exact branches in ../url-handling.md - no prioris-mcp tool
accepts a raw URL, so this replaces re-deriving the same regex/string logic
by hand (and risking a slipped branch) every time a skill is handed one.

Usage:
    uv run --project <plugin root> python shared/scripts/extract_identifier.py <url-or-doi>

On success, prints a single-line JSON object {"provider": ..., "identifier": ...}
to stdout and exits 0. `provider` is one of "arxiv", "europepmc", or "doi" -
"doi" means: pass this bare identifier to research_resolve_identifier, it is
not itself a provider-specific tool argument.

If the input doesn't match any known pattern, exits 1 with a message on
stderr - per url-handling.md, that means telling the user directly rather
than guessing: ask for a paper id, DOI, or search terms instead.
"""

import json
import re
import sys
from urllib.parse import urlparse

_BARE_DOI_RE = re.compile(r"10\.\d{4,9}/\S+")
_PMC_RE = re.compile(r"/(PMC\d+)\b")


def _host_matches(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def extract(raw: str) -> tuple[str, str] | None:
    raw = raw.strip()

    if _BARE_DOI_RE.fullmatch(raw):
        return ("doi", raw)

    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    host = (parsed.hostname or "").lower()
    parts = [p for p in parsed.path.split("/") if p]

    if (
        _host_matches(host, "arxiv.org")
        and parts
        and parts[0] in ("abs", "pdf", "html")
    ):
        identifier = "/".join(parts[1:])
        identifier = identifier.removesuffix(".pdf")
        if identifier:
            return ("arxiv", identifier)

    if _host_matches(host, "doi.org"):
        identifier = parsed.path.lstrip("/")
        if identifier:
            return ("doi", identifier)

    pmc_match = _PMC_RE.search(parsed.path)
    if pmc_match:
        return ("europepmc", pmc_match.group(1))

    if len(parts) >= 3 and parts[0] == "article":
        return ("europepmc", f"{parts[1]}:{parts[2]}")

    return None


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <url-or-doi>", file=sys.stderr)
        return 2

    result = extract(sys.argv[1])
    if result is None:
        print(
            "not a recognized research URL (arXiv/Europe PMC/DOI pattern) - "
            "ask for a paper id, DOI, or search terms instead",
            file=sys.stderr,
        )
        return 1

    provider, identifier = result
    print(json.dumps({"provider": provider, "identifier": identifier}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
