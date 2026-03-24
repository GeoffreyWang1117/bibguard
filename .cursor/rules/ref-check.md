---
description: Citation verification for academic papers using ref-check
globs: ["*.bib", "*.tex"]
---

# ref-check Integration

When the user asks to verify, check, or validate references in a .bib file, use the `ref-check` CLI tool.

## Setup

```bash
pip install ref-check
```

## Commands

```bash
# Basic verification
ref-check references.bib

# With TeX cross-audit
ref-check references.bib --tex main.tex

# Save report + auto-fix
ref-check references.bib --out report.md --fix fixed.bib

# JSON output for programmatic use
ref-check references.bib --json --out report.json
```

## Interpreting Results

- **FAIL (phantom_doi/phantom_arxiv)**: Identifier looks valid but doesn't resolve. Strongest hallucination signal. Search the web to find the correct reference or confirm it's fabricated.
- **FAIL (NO API MATCH)**: Not found in any of 5 databases. Likely hallucinated or title differs significantly.
- **FAIL (retraction)**: Paper has been retracted.
- **WARN**: Metadata mismatch (venue, year, author count). Usually needs human review.
- **OK**: Verified against at least one source.

Exit code 1 means at least one FAIL was found.
