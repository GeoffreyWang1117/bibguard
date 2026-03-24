Run the bibguard citation verification tool on a .bib file.

Usage: /bibguard <bib-file> [--tex <tex-file>] [--fix]

Instructions:
1. Parse the user's arguments. The first argument is the .bib file path. Optional: --tex for cross-audit, --fix to generate auto-corrected .bib.
2. Run the verification:
   ```
   bibguard <bib-file> [--tex <tex-file>] [--out /tmp/refcheck_report.md] [--fix /tmp/refcheck_fixed.bib]
   ```
   If `bibguard` is not on PATH, use: `python -m bibguard.cli <bib-file> ...`
3. Read the output report and present results to the user.
4. For any WARN or FAIL entries:
   - Summarize what went wrong (phantom DOI, author mismatch, not found, etc.)
   - For phantom_doi / phantom_arxiv FAILs: these are likely hallucinated references. Search the web to find the correct reference or confirm it doesn't exist.
   - For other WARNs: check if the reference needs correction (wrong year, venue mismatch, etc.)
5. If --fix was used, show the auto-fix diff.

$ARGUMENTS
