# Shared: URL Canonicalization

Referenced by `discuss`, `quick-read`, and `quiz-me`. No `prioris-mcp` tool accepts a raw URL as input — if you're handed one, extract the canonical identifier before calling anything.

Run `shared/scripts/extract_identifier.py <url>` (see `scripts/README.md` for how to invoke it) rather than re-deriving this by regex from scratch each time. On success it prints `{"provider": ..., "identifier": ...}` to stdout: `provider` is `arxiv` or `europepmc` — call that provider's tools directly with `identifier` — or `doi`, meaning `identifier` is a bare DOI to pass to `research_resolve_identifier` rather than a provider-specific tool. If nothing matched, it exits non-zero with a message on stderr; say you can't resolve that URL and ask for a paper id, DOI, or search terms instead — don't guess further.

The branches it implements, for reference:

- arXiv landing/PDF/HTML URL (`arxiv.org/abs/...`, `/pdf/...`, `/html/...`) → the arXiv id is the path segment after `abs`/`pdf`/`html`.
- Europe PMC URL containing `/PMC<digits>` → that's the PMCID.
- Europe PMC URL of the form `/article/{source}/{id}` → canonical identifier is `{source}:{id}`.
- `doi.org/...` URL, or a bare DOI on its own → the DOI itself.
- Anything else → unresolved.
