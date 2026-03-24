"""Command-line interface for ref-check."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ref_check.autofix import generate_fixed_bib
from ref_check.core import VerificationResult, verify_entry
from ref_check.duplicates import detect_duplicates
from ref_check.parsers.bibtex import parse_bib
from ref_check.report import generate_report
from ref_check.tex_audit import audit_tex_bib

_ICON = {"OK": "OK", "WARN": "WARN", "FAIL": "FAIL"}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="ref-check",
        description="Detect hallucinated and broken citations in academic papers",
    )
    parser.add_argument("bib", help=".bib file path")
    parser.add_argument("--tex", help=".tex file path (enables cross-audit)")
    parser.add_argument("--out", help="Output Markdown report path")
    parser.add_argument("--fix", help="Output auto-fixed .bib path")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of Markdown")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--version", action="version",
                        version=f"%(prog)s {_get_version()}")
    args = parser.parse_args(argv)

    bib_path = args.bib
    if not Path(bib_path).exists():
        print(f"Error: file not found: {bib_path}", file=sys.stderr)
        sys.exit(2)

    # Parse
    print(f"Parsing {bib_path}...")
    entries = parse_bib(bib_path)
    print(f"  Found {len(entries)} entries\n")

    # Verify
    results: list[VerificationResult] = []
    for i, entry in enumerate(entries):
        print(f"[{i+1}/{len(entries)}] {entry['key']}...", end=" ", flush=True)
        r = verify_entry(entry, verbose=args.verbose)
        results.append(r)
        sources = ", ".join(r.sources_hit) if r.sources_hit else "no match"
        print(f"{_ICON[r.overall]} ({sources})")

    # TeX cross-audit
    tex_issues: list[dict] = []
    if args.tex:
        print(f"\nCross-auditing {args.tex}...")
        tex_issues = audit_tex_bib(args.tex, entries)
        for iss in tex_issues:
            print(f"  {iss['type']}: {iss['message']}")

    # Duplicates
    print("\nChecking for duplicates...")
    dup_issues = detect_duplicates(entries)
    for iss in dup_issues:
        print(f"  WARN: {iss['message']}")
    if not dup_issues:
        print("  No duplicates found")

    # Report
    if args.json:
        import json
        data = {
            "summary": {
                "total": len(results),
                "ok": sum(1 for r in results if r.overall == "OK"),
                "warn": sum(1 for r in results if r.overall == "WARN"),
                "fail": sum(1 for r in results if r.overall == "FAIL"),
            },
            "results": [
                {
                    "key": r.key,
                    "title": r.title,
                    "overall": r.overall,
                    "sources_hit": r.sources_hit,
                    "checks": r.checks,
                    "suggested_fixes": r.suggested_fixes,
                }
                for r in results
            ],
            "tex_issues": tex_issues,
            "dup_issues": dup_issues,
        }
        output = json.dumps(data, indent=2, ensure_ascii=False)
    else:
        output = generate_report(results, tex_issues, dup_issues)

    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
        print(f"\nReport saved to {args.out}")
    else:
        print("\n" + "=" * 60)
        print(output)

    # Auto-fix
    if args.fix:
        fixed = generate_fixed_bib(bib_path, results)
        Path(args.fix).write_text(fixed, encoding="utf-8")
        n_fixes = sum(1 for r in results if r.suggested_fixes)
        print(f"\nFixed .bib saved to {args.fix} ({n_fixes} entries with fixes)")

    # Exit code: 1 if any FAIL
    has_fail = any(r.overall == "FAIL" for r in results)
    has_fail = has_fail or any(i["type"] == "FAIL" for i in tex_issues)
    sys.exit(1 if has_fail else 0)


def _get_version() -> str:
    try:
        from ref_check import __version__
        return __version__
    except ImportError:
        return "unknown"


if __name__ == "__main__":
    main()
