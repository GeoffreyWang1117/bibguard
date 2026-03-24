# ref-check

**Detect hallucinated and broken citations in academic papers.**

One command to verify every reference in your `.bib` file against five scholarly databases. Catches phantom DOIs, fabricated arXiv IDs, author mismatches, retracted papers, and AI-hallucinated citations.

```bash
pip install ref-check
ref-check paper.bib
```

---

## Why

Large language models hallucinate citations. Copy-paste errors corrupt metadata. Retracted papers slip through review. `ref-check` catches these problems **before** submission.

- **5 sources**: arXiv, Crossref, DBLP, Semantic Scholar, OpenAlex
- **Phantom ID detection**: Valid-format DOI/arXiv that doesn't resolve = hallucination signal
- **Kill-shot logic**: A phantom ID cannot be overridden by a similar search result
- **TeX cross-audit**: Find `\cite{key}` with no `.bib` entry, and orphan entries never cited
- **Duplicate detection**: Flag near-identical entries with different keys
- **Auto-fix**: Generate a corrected `.bib` with missing DOIs and eprint IDs filled in
- **Zero heavy dependencies**: Core requires only `requests` + `bibtexparser`

## Install

```bash
pip install ref-check            # minimal
pip install ref-check[fast]      # + RapidFuzz for better title matching
pip install ref-check[all]       # + RapidFuzz + PyMuPDF for PDF parsing
```

Requires Python 3.9+.

## Usage

### CLI

```bash
# Basic: verify all entries in a .bib file
ref-check references.bib

# With TeX cross-audit (finds phantom \cite and orphan entries)
ref-check references.bib --tex main.tex

# Save report + auto-fix
ref-check references.bib --tex main.tex --out report.md --fix fixed.bib

# JSON output (for CI pipelines)
ref-check references.bib --json --out report.json
```

### Python API

```python
from ref_check import verify_bib, verify_entry

# Verify entire .bib file
results, report = verify_bib("references.bib", tex_path="main.tex")
for r in results:
    if r.overall != "OK":
        print(f"{r.overall}: {r.key} -- {r.title}")

# Verify a single entry
from ref_check.parsers.bibtex import parse_bib
entries = parse_bib("references.bib")
result = verify_entry(entries[0])
print(result.overall, result.checks)
```

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | All entries OK or WARN |
| 1 | At least one FAIL (hallucination, phantom ID, no match, or retraction) |
| 2 | Input error (file not found) |

Use in CI: `ref-check references.bib || echo "Citation issues found"`

## How it works

```
Input (.bib)
  |
  v
Parse entries (bibtexparser)
  |
  v
For each entry:
  1. arXiv lookup (by arXiv ID)        -- direct ID resolution
  2. Crossref lookup (by DOI)           -- direct ID resolution
  3. Phantom ID detection               -- valid format but doesn't resolve?
  4. DBLP search (by title + author)    -- with author disambiguation
  5. Semantic Scholar search             -- fallback + citation count
  6. OpenAlex search                     -- fallback for non-CS / old papers
  |
  v
Post-processing:
  - Source-aware status (confirmed source overrides noisy cross-checks)
  - Kill-shot: phantom ID overrides search-confirmed status
  - Suggested fixes (missing DOI, eprint)
  |
  v
Report (Markdown / JSON)
  + TeX cross-audit (phantom refs, orphan entries)
  + Duplicate detection
  + Auto-fixed .bib
```

## Benchmark

Tested on a 58-case golden test set with known hallucinated, retracted, chimera, and real papers:

| Metric | Result |
|--------|--------|
| Hallucination recall (FAIL/WARN) | **100% (14/14)** |
| Real paper accuracy | 70% (7/10 clean pass, 3 manual-reviewable WARN) |
| Phantom ID detection | 4/4 fake DOIs and arXiv IDs caught |
| Runtime (58 entries) | ~92 seconds |

For deeper verification (semantic NLI, citation graph analysis, Bayesian risk scoring), see [IntegriRef](https://github.com/GeoffreyWang1117/IntegriRef).

## Claude Code Integration

`ref-check` works as a [Claude Code](https://docs.anthropic.com/en/docs/claude-code) slash command. Claude runs the verification, analyzes WARN/FAIL entries, and searches the web to find correct references.

### Install as slash command

```bash
mkdir -p ~/.claude/commands
curl -o ~/.claude/commands/ref-check.md \
  https://raw.githubusercontent.com/GeoffreyWang1117/ref-check/main/.claude/commands/ref-check.md
```

### Use in Claude Code

```
/ref-check paper.bib
/ref-check paper.bib --tex main.tex --fix
```

## Optional dependencies

| Package | Purpose | Install |
|---------|---------|---------|
| `rapidfuzz` | Better title matching (token_set_ratio) | `pip install ref-check[fast]` |
| `pymupdf` | PDF reference extraction (no GROBID needed) | `pip install ref-check[pdf]` |

## API sources

| Source | Lookup method | Coverage |
|--------|--------------|----------|
| arXiv | ID resolution | CS, Physics, Math, ... |
| Crossref | DOI resolution | 150M+ records |
| DBLP | Title search | CS papers (gold standard) |
| Semantic Scholar | Title search | 200M+ papers |
| OpenAlex | Title search | 250M+ works (all disciplines) |

All queries respect rate limits. No API keys required.

## Contributing

Issues and PRs welcome. To run tests:

```bash
git clone https://github.com/GeoffreyWang1117/ref-check.git
cd ref-check
pip install -e ".[dev]"
pytest
```

## Related

- [IntegriRef](https://github.com/GeoffreyWang1117/IntegriRef) -- Full L0-L4 verification stack (semantic NLI, citation graph analysis, Bayesian risk scoring)
- [Rebiber](https://github.com/yuchenlin/rebiber) -- Normalize BibTeX with DBLP/ACL Anthology

## License

MIT
