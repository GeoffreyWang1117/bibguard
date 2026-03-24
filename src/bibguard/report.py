"""Markdown report generation."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bibguard.core import VerificationResult

_ICON = {"OK": "✅", "WARN": "⚠️", "FAIL": "❌"}


def generate_report(results: list[VerificationResult],
                    tex_issues: list[dict],
                    dup_issues: list[dict]) -> str:
    """Generate Markdown verification report."""
    lines = ["# bibguard Report\n"]

    ok = sum(1 for r in results if r.overall == "OK")
    warn = sum(1 for r in results if r.overall == "WARN")
    fail = sum(1 for r in results if r.overall == "FAIL")
    total = len(results)

    lines.append(f"| Metric | Count |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Total entries | {total} |")
    lines.append(f"| ✅ OK | {ok} |")
    lines.append(f"| ⚠️ WARN | {warn} |")
    lines.append(f"| ❌ FAIL | {fail} |")
    lines.append("")

    any_hit = sum(1 for r in results if r.sources_hit)
    source_counts: dict[str, int] = defaultdict(int)
    for r in results:
        for s in r.sources_hit:
            source_counts[s] += 1
    lines.append(f"**API coverage:** {any_hit}/{total} entries found in at least one source  ")
    if source_counts:
        lines.append("**Sources:** " + " · ".join(
            f"{s} ({c})" for s, c in sorted(source_counts.items(),
                                             key=lambda x: -x[1])))
    lines.append("")

    # TeX cross-audit
    if tex_issues:
        lines.append("## TeX Cross-Audit\n")
        for iss in tex_issues:
            icon = _ICON.get(iss["type"], "❓")
            lines.append(f"- {icon} `{iss['key']}` — {iss['message']}")
        lines.append("")

    # Duplicates
    if dup_issues:
        lines.append("## Duplicates\n")
        for iss in dup_issues:
            lines.append(f"- ⚠️ {iss['message']}")
        lines.append("")

    # FAIL entries first (expanded)
    fail_results = [r for r in results if r.overall == "FAIL"]
    warn_results = [r for r in results if r.overall == "WARN"]
    ok_results = [r for r in results if r.overall == "OK"]

    if fail_results:
        lines.append(f"## ❌ Issues ({len(fail_results)})\n")
        for r in fail_results:
            _render_entry(lines, r, verbose=True)

    if warn_results:
        lines.append(f"## ⚠️ Warnings ({len(warn_results)})\n")
        for r in warn_results:
            _render_entry(lines, r, verbose=True)

    if ok_results:
        lines.append(f"## ✅ Verified ({len(ok_results)})\n")
        for r in ok_results:
            _render_entry(lines, r, verbose=False)

    return "\n".join(lines)


def _render_entry(lines: list[str], r: VerificationResult, verbose: bool) -> None:
    """Render a single entry in the report."""
    icon = _ICON[r.overall]
    sources = ", ".join(r.sources_hit) if r.sources_hit else "no match"
    lines.append(f"### {icon} `{r.key}`\n")
    lines.append(f"**{r.title}**  ")
    lines.append(f"Sources: {sources}\n")

    if verbose:
        # Show non-OK checks (the interesting ones)
        issues = [c for c in r.checks if c["status"] != "OK"]
        if issues:
            for c in issues:
                ci = _ICON.get(c["status"], "❓")
                src = f" [{c['source']}]" if c["source"] else ""
                lines.append(f"- {ci} **{c['field']}**: {c['detail']}{src}")
        else:
            # All OK but still WARN overall? Show all checks
            for c in r.checks:
                ci = _ICON.get(c["status"], "❓")
                src = f" [{c['source']}]" if c["source"] else ""
                lines.append(f"- {ci} {c['field']}: {c['detail']}{src}")

        if r.suggested_fixes:
            lines.append("")
            lines.append("**Suggested fixes:**")
            for field, value in r.suggested_fixes.items():
                lines.append(f"- Add `{field} = {{{value}}}`")
    else:
        # Compact: just source list + fix suggestions
        if r.suggested_fixes:
            fixes = ", ".join(f"`{f}={v}`" for f, v in r.suggested_fixes.items())
            lines.append(f"- Fixes available: {fixes}")

    lines.append("")
