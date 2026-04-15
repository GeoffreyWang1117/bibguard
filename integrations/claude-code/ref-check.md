Run bibguard citation verification on a .bib file.

Usage: /ref-check <bib-file> [--tex <tex-file>] [--fix]

Instructions:
1. Parse the user's arguments. The first argument is the .bib file path. Optional: --tex for cross-audit, --fix to generate auto-corrected .bib.
2. Run the verification:
   ```
   bibguard <bib-file> [--tex <tex-file>] [--out /tmp/bibguard_report.md] [--fix /tmp/bibguard_fixed.bib]
   ```
   If `bibguard` is not on PATH, install first: `pip install bibguard`
3. Read the output report and present results to the user.
4. For any WARN or FAIL entries:
   - Summarize what went wrong (phantom DOI, author mismatch, not found, etc.)
   - For phantom_doi / phantom_arxiv FAILs: these are likely hallucinated references. Search the web to find the correct reference or confirm it doesn't exist.
   - For @misc/@online entries with WARN: non-article types have limited API coverage, this is expected.
   - For other WARNs: check if the reference needs correction (wrong year, venue mismatch, etc.)
5. If --fix was used, show the auto-fix diff.
6. If the user reports issues with the results, log feedback:
   ```
   bibguard feedback --issue "<description>" --severity <critical|major|minor|suggestion> --context "<what was verified>"
   ```

$ARGUMENTS
