# bibguard

[![PyPI version](https://img.shields.io/pypi/v/bibguard)](https://pypi.org/project/bibguard/)
[![Python](https://img.shields.io/pypi/pyversions/bibguard)](https://pypi.org/project/bibguard/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-58%20cases-green)]()

**Detect hallucinated and broken citations in academic papers.**

One command to verify every reference in your `.bib` file against five scholarly databases. Catches phantom DOIs, fabricated arXiv IDs, author mismatches, retracted papers, and AI-hallucinated citations.

```bash
pip install bibguard
bibguard paper.bib
```

![bibguard architecture](docs/figures/architecture.png)

[Landing Page](https://geoffreywang1117.github.io/bibguard/) | [PyPI](https://pypi.org/project/bibguard/) | [Changelog](CHANGELOG.md)

---

## Why

Large language models hallucinate citations. Copy-paste errors corrupt metadata. Retracted papers slip through review. `bibguard` catches these problems **before** submission.

- **5 sources**: arXiv, Crossref, DBLP, Semantic Scholar, OpenAlex
- **Phantom ID detection**: Valid-format DOI/arXiv that doesn't resolve = hallucination signal
- **Kill-shot logic**: A phantom ID cannot be overridden by a similar search result
- **TeX cross-audit**: Find `\cite{key}` with no `.bib` entry, and orphan entries never cited
- **Duplicate detection**: Flag near-identical entries with different keys
- **Auto-fix**: Generate a corrected `.bib` with missing DOIs and eprint IDs filled in
- **Zero heavy dependencies**: Core requires only `requests` + `bibtexparser`

## Install

```bash
pip install bibguard            # minimal
pip install bibguard[fast]      # + RapidFuzz for better title matching
pip install bibguard[all]       # + RapidFuzz + PyMuPDF for PDF parsing
```

Requires Python 3.9+.

## Usage

### CLI

```bash
# Basic: verify all entries in a .bib file
bibguard references.bib

# With TeX cross-audit (finds phantom \cite and orphan entries)
bibguard references.bib --tex main.tex

# Save report + auto-fix
bibguard references.bib --tex main.tex --out report.md --fix fixed.bib

# JSON output (for CI pipelines)
bibguard references.bib --json --out report.json
```

### Python API

```python
from bibguard import verify_bib, verify_entry

# Verify entire .bib file
results, report = verify_bib("references.bib", tex_path="main.tex")
for r in results:
    if r.overall != "OK":
        print(f"{r.overall}: {r.key} -- {r.title}")

# Verify a single entry
from bibguard.parsers.bibtex import parse_bib
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

Use in CI: `bibguard references.bib || echo "Citation issues found"`

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

Tested on a 58-case golden test set (`tests/golden_benchmark.bib`). Reproduce with `python tests/bench_golden.py`.

| Category | Metric | Result |
|----------|--------|--------|
| **Hallucinated** (14 fabricated + 1 control) | Detected as FAIL | **14/14 (100%)** |
| | Detected as >= WARN | **15/15 (100%)** |
| **Chimera** (5 mixed-metadata) | Detected as >= WARN | **5/5 (100%)** |
| **Real papers** (10 legitimate) | Clean pass (OK) | 4/10 (40%) |
| | False positive (FAIL) | 1/10 (10%) |
| **Retracted** (28 retractions) | Any issue flagged | 19/28 (68%) |
| **Runtime** | 58 entries | **95s (~1.6s/entry)** |

**Notes:**
- The 1 false-positive FAIL is a 1962 book with no DOI — a known edge case for API-based verification.
- WARN on real papers are mostly venue/author-count mismatches — reviewable by humans.
- All 14 truly fabricated citations are caught at FAIL level.

For semantic NLI, citation graph analysis, and Bayesian risk scoring, see [IntegriRef](https://github.com/GeoffreyWang1117/IntegriRef).

## AI Coding Assistant Integration

bibguard ships with skill/rule definitions for major AI coding assistants. The AI runs verification, analyzes FAIL entries, and searches the web to find correct references.

### Claude Code

```bash
mkdir -p ~/.claude/commands
curl -o ~/.claude/commands/bibguard.md \
  https://raw.githubusercontent.com/GeoffreyWang1117/bibguard/main/.claude/commands/bibguard.md
```
Then use `/bibguard paper.bib` in Claude Code.

### OpenAI Codex CLI

```bash
mkdir -p ~/.codex/skills/bibguard
curl -o ~/.codex/skills/bibguard/SKILL.md \
  https://raw.githubusercontent.com/GeoffreyWang1117/bibguard/main/.codex/skills/bibguard/SKILL.md
```

### Cursor

```bash
mkdir -p .cursor/rules
curl -o .cursor/rules/bibguard.md \
  https://raw.githubusercontent.com/GeoffreyWang1117/bibguard/main/.cursor/rules/bibguard.md
```

### Any other assistant

bibguard is a standard CLI tool. Any AI assistant that can run shell commands can use it:
```
bibguard paper.bib --json --out report.json
```

## Optional dependencies

| Package | Purpose | Install |
|---------|---------|---------|
| `rapidfuzz` | Better title matching (token_set_ratio) | `pip install bibguard[fast]` |
| `pymupdf` | PDF reference extraction (no GROBID needed) | `pip install bibguard[pdf]` |

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
git clone https://github.com/GeoffreyWang1117/bibguard.git
cd bibguard
pip install -e ".[dev]"
pytest
```

## Related

- [IntegriRef](https://github.com/GeoffreyWang1117/IntegriRef) -- Full L0-L4 verification stack with semantic NLI (93.5% accuracy), citation graph analysis, and Bayesian risk scoring
- [Rebiber](https://github.com/yuchenlin/rebiber) -- Normalize BibTeX with DBLP/ACL Anthology

## Contributors

See [CONTRIBUTORS.md](CONTRIBUTORS.md) for detailed attribution.

- **Geoffrey Wang** — Architecture, core algorithms, phantom-ID detection, kill-shot logic, benchmark design
- **Claude (Anthropic)** — Modular refactoring, output formatting, packaging, documentation

## License

Apache License 2.0. See [LICENSE](LICENSE) for details.

---

<details>
<summary><strong>中文说明</strong></summary>

# bibguard — 学术论文引用幻觉检测工具

**一行命令，检测论文中的虚假引用。**

大语言模型会"幻觉"出格式正确但根本不存在的参考文献。bibguard 用 5 个学术数据库（arXiv、Crossref、DBLP、Semantic Scholar、OpenAlex）交叉验证你的 `.bib` 文件。

```bash
pip install bibguard
bibguard paper.bib
```

### 核心能力

- **幽灵 DOI / arXiv ID 检测** — 格式正确但不存在 = 最强幻觉信号
- **Kill-shot 逻辑** — 幽灵 ID 不会被相似论文的搜索结果覆盖
- **TeX 交叉审计** — 检测 `\cite{key}` 在 `.bib` 中无定义，以及定义了但从未引用的条目
- **自动修复** — 补全缺失的 DOI 和 eprint 字段
- **极轻依赖** — 仅需 `requests` + `bibtexparser`

### 基准测试 (58 条公开测试集)

| 类别 | 指标 | 结果 |
|------|------|------|
| AI 幻觉引用 (14 条) | 检出率 (FAIL) | **100%** |
| 元数据嵌合体 (5 条) | 检出率 (>=WARN) | **100%** |
| 真实论文 (10 条) | 假阳率 (FAIL) | 10% (1 本 1962 年书籍) |
| 运行时间 | 58 条 | 95 秒 |

### AI 编程助手集成

支持 Claude Code (`/bibguard`)、OpenAI Codex、Cursor 自动触发。

### 深度验证

bibguard 是 L0（存在性验证）层。如需语义 NLI 验证 (93.5%)、引文图谱异常检测、贝叶斯风险评分，请使用 [IntegriRef](https://github.com/GeoffreyWang1117/IntegriRef)。

</details>
