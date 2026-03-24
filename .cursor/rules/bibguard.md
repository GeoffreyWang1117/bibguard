---
description: Citation verification for academic papers using bibguard
globs: ["*.bib", "*.tex"]
---

# bibguard Integration

When the user asks to verify, check, or validate references in a .bib file, use the `bibguard` CLI tool.

## Setup

```bash
pip install bibguard
```

## Commands

```bash
# Basic verification
bibguard references.bib

# With TeX cross-audit
bibguard references.bib --tex main.tex

# Save report + auto-fix
bibguard references.bib --out report.md --fix fixed.bib

# JSON output for programmatic use
bibguard references.bib --json --out report.json
```

## Interpreting Results

- **FAIL (phantom_doi/phantom_arxiv)**: Identifier looks valid but doesn't resolve. Strongest hallucination signal. Search the web to find the correct reference or confirm it's fabricated.
- **FAIL (NO API MATCH)**: Not found in any of 5 databases. Likely hallucinated or title differs significantly.
- **FAIL (retraction)**: Paper has been retracted.
- **WARN**: Metadata mismatch (venue, year, author count). Usually needs human review.
- **OK**: Verified against at least one source.

Exit code 1 means at least one FAIL was found.
