---
name: bibguard
description: Run citation verification on a .bib file. Detects hallucinated references, phantom DOIs, author mismatches, and retracted papers. Use when user asks to check, verify, or validate references/citations in a paper.
---

# bibguard: Citation Verification

Run the bibguard tool to verify references in a .bib file.

## Usage

```
bibguard <bib-file> [--tex <tex-file>] [--out report.md] [--fix fixed.bib] [--json]
```

If `bibguard` is not on PATH, use: `pip install bibguard && bibguard <bib-file>`

## Instructions

1. Parse the user's request. Identify the .bib file path and any optional flags.
2. Run verification: `bibguard <bib-file> --out /tmp/refcheck_report.md`
3. Read the output report and present results.
4. For FAIL entries:
   - **phantom_doi / phantom_arxiv**: The identifier has valid format but doesn't resolve. This is the strongest hallucination signal. Search the web to find the correct reference.
   - **verification (NO API MATCH)**: Not found in any database. May be hallucinated or have a very different title.
   - **retraction**: Paper has been retracted.
5. For WARN entries: Check if venue/year/author mismatches need correction.
6. If `--fix` was used, show what was auto-corrected.

## Arguments

$ARGUMENTS
