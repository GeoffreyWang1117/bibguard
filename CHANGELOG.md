# Changelog

## [0.3.1] - 2026-03-27

### Added
- **Parallel verification** via `--workers N` / `-w N` CLI flag
- `concurrent.futures.ThreadPoolExecutor` for concurrent entry verification
- Thread-safe per-source rate limiting (`threading.Lock` per API source)
- `workers` and `progress` callback parameters in `verify_bib()` Python API
- Auto-selects worker count for files with >8 entries (default: `min(4, cpu_count)`)

### Performance
- 58-entry golden benchmark: **95.8s → 62.6s** with 4 workers (1.5× speedup)
- Speedup increases with larger files as more entries interleave across rate-limited sources

## [0.3.0] - 2026-03-25

### Changed
- `@misc`/`@online`/`@manual` entries downgrade to WARN (not FAIL) when not found
- Year tolerance: +/-2 is WARN instead of FAIL (preprint vs published)
- Confirmed matches (title+author OK) accept year off-by-1 as OK
- Expanded venue abbreviation map (+25 entries: NLP, CV, DM, systems, scientometrics)
- Expanded DBLP abbreviation map (+8 journal short forms)
- Removed third-party references from README

### Added
- Large-scale benchmark (`tests/bench_large.py`) on 2000+ crawled entries
- npm badge in README

### Benchmark
- 200-case large-scale: 100% hallucination recall, 0% false positive, 86% real paper OK
- IntegriRef refs.bib (48 entries): OK 29->37, WARN 17->10, FAIL 2->1 vs v0.2.0

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
