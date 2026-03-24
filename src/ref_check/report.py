"""Markdown report generation."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ref_check.core import VerificationResult

_STATUS_ICON = {"OK": "OK", "WARN": "WARN", "FAIL": "FAIL"}


def generate_report(results: list[VerificationResult],
                    tex_issues: list[dict],
                    dup_issues: list[dict]) -> str:
    """Generate Markdown verification report."""
    lines = ["# ref-check Verification Report\n"]

    ok = sum(1 for r in results if r.overall == "OK")
    warn = sum(1 for r in results if r.overall == "WARN")
    fail = sum(1 for r in results if r.overall == "FAIL")
    total = len(results)
    lines.append(f"**Total entries:** {total}  |  "
                 f"OK: {ok}  |  WARN: {warn}  |  FAIL: {fail}\n")

    any_hit = sum(1 for r in results if r.sources_hit)
    lines.append(f"**API coverage:** {any_hit}/{total} entries matched at least one source\n")

    source_counts: dict[str, int] = defaultdict(int)
    for r in results:
        for s in r.sources_hit:
            source_counts[s] += 1
    lines.append("**Source breakdown:** " + ", ".join(
        f"{s}: {c}" for s, c in sorted(source_counts.items())) + "\n")

    if tex_issues:
        lines.append("## TeX Cross-Audit\n")
        for iss in tex_issues:
            lines.append(f"- **{iss['type']}** [{iss['category']}] `{iss['key']}`: {iss['message']}")
        lines.append("")

    if dup_issues:
        lines.append("## Duplicate Detection\n")
        for iss in dup_issues:
            lines.append(f"- WARN: {iss['message']}")
        lines.append("")

    lines.append("## Per-Entry Verification\n")
    sorted_results = sorted(results, key=lambda r: {"FAIL": 0, "WARN": 1, "OK": 2}[r.overall])

    for r in sorted_results:
        sources = ", ".join(r.sources_hit) if r.sources_hit else "none"
        lines.append(f"### [{r.overall}] `{r.key}`")
        lines.append(f"**Title:** {r.title}  ")
        lines.append(f"**Verified by:** {sources}\n")

        for c in r.checks:
            src = f" [{c['source']}]" if c["source"] else ""
            lines.append(f"- {c['status']}: {c['field']}: {c['detail']}{src}")

        if r.suggested_fixes:
            lines.append(f"\n**Suggested fixes:** {r.suggested_fixes}")
        lines.append("")

    return "\n".join(lines)
