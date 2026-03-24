# Changelog

## [0.2.0] - 2026-03-24

### Changed
- Renamed from `ref-check` to `bibguard` (PyPI name conflict)
- Upgraded to Apache 2.0 license
- Improved CLI output: emoji status, timing, fail summary
- Improved Markdown report: grouped by severity, compact OK entries
- Modular package structure (sources/, parsers/)

### Added
- 58-case golden benchmark (`tests/bench_golden.py`)
- GitHub Pages landing page
- AI assistant skills: Claude Code, OpenAI Codex, Cursor
- CONTRIBUTORS.md with detailed attribution
- CHANGELOG.md
- `py.typed` marker (PEP 561)
- `--json` output mode for CI pipelines
- Bilingual README (English + Chinese)

### Benchmark
- Hallucination recall: 100% (14/14)
- Chimera detection: 100% (5/5)
- Runtime: 95s for 58 entries

## [0.1.0] - 2026-03-24

Initial release (as `ref-check`, not published to PyPI).

- 5-source cascade: arXiv, Crossref, DBLP, Semantic Scholar, OpenAlex
- Phantom DOI/arXiv detection with kill-shot logic
- TeX cross-audit, duplicate detection, auto-fix
- CLI and Python API
