# Shared: URL Canonicalization

Referenced by `discuss`, `quick-read`, and `quiz-me`. No `prioris-mcp` tool accepts a raw URL as input — if you're handed one, extract the canonical identifier yourself before calling anything:

- arXiv landing/PDF/HTML URL (`arxiv.org/abs/...`, `/pdf/...`, `/html/...`) → the arXiv id is the path segment after `abs`/`pdf`/`html`; call the arXiv tools directly with it.
- Europe PMC URL containing `/PMC<digits>` → that's the PMCID; call the Europe PMC tools directly with it.
- Europe PMC URL of the form `/article/{source}/{id}` → canonical identifier is `{source}:{id}`.
- `doi.org/...` URL, or any other DOI → pass the bare DOI (e.g. `10.1234/...`, not the URL) to `research_resolve_identifier`, which resolves it via a doi.org redirect.
- Anything else → say you can't resolve that URL and ask for a paper id, DOI, or search terms instead.
