You have access to `bibguard`, a citation verification CLI tool.

## When to use
When the user asks you to verify, check, or audit a .bib / BibTeX file for correctness.

## How to run
```bash
bibguard <bib-file> --json --out /tmp/bibguard_report.json
```

Key flags:
- `--json` — machine-readable output (recommended for agents)
- `--tex <file>` — cross-audit against .tex for unused/missing citations
- `--fix <path>` — generate auto-corrected .bib

## Interpreting results
- **OK**: entry verified against at least one authoritative source
- **WARN**: partial match or unverifiable entry type (@misc, @online)
- **FAIL**: phantom DOI/arXiv ID, author mismatch, or completely unverifiable — likely hallucinated

## Follow-up actions
- For FAIL entries: search the web to find the real paper or confirm it doesn't exist
- For WARN entries with year/venue mismatch: suggest corrections to the user
- If `--fix` was used, show the diff between original and fixed .bib
