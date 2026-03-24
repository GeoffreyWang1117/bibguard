"""Command-line interface for bibguard."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from bibguard.autofix import generate_fixed_bib
from bibguard.core import VerificationResult, verify_entry
from bibguard.duplicates import detect_duplicates
from bibguard.parsers.bibtex import parse_bib
from bibguard.report import generate_report
from bibguard.tex_audit import audit_tex_bib

_ICON = {"OK": "✅", "WARN": "⚠️ ", "FAIL": "❌"}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="bibguard",
        description="Detect hallucinated and broken citations in academic papers",
    )
    parser.add_argument("bib", help=".bib file path")
    parser.add_argument("--tex", help=".tex file path (enables cross-audit)")
    parser.add_argument("--out", help="Output report path (Markdown or JSON)")
    parser.add_argument("--fix", help="Output auto-fixed .bib path")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of Markdown")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--version", action="version",
                        version=f"%(prog)s {_get_version()}")
    args = parser.parse_args(argv)

    bib_path = args.bib
    if not Path(bib_path).exists():
        print(f"bibguard: error: file not found: {bib_path}", file=sys.stderr)
        sys.exit(2)

    # -- Parse --
    entries = parse_bib(bib_path)
    total = len(entries)
    print(f"\n  bibguard v{_get_version()}")
    print(f"  {bib_path} — {total} entries\n")

    # -- Verify --
    t0 = time.time()
    results: list[VerificationResult] = []
    for i, entry in enumerate(entries):
        key_display = entry["key"][:40]
        print(f"  [{i+1:>{len(str(total))}}/{total}] {key_display:<40s}", end=" ", flush=True)
        r = verify_entry(entry, verbose=args.verbose)
        results.append(r)
        sources = ", ".join(r.sources_hit) if r.sources_hit else "no match"
        print(f"{_ICON[r.overall]} {sources}")

    elapsed = time.time() - t0

    # -- TeX cross-audit --
    tex_issues: list[dict] = []
    if args.tex:
        print(f"\n  TeX cross-audit: {args.tex}")
        tex_issues = audit_tex_bib(args.tex, entries)
        for iss in tex_issues:
            icon = _ICON.get(iss["type"], "❓")
            print(f"    {icon} {iss['message']}")
        if not tex_issues:
            print("    ✅ No issues")

    # -- Duplicates --
    dup_issues = detect_duplicates(entries)
    if dup_issues:
        print(f"\n  Duplicate check:")
        for iss in dup_issues:
            print(f"    ⚠️  {iss['message']}")

    # -- Summary --
    ok = sum(1 for r in results if r.overall == "OK")
    warn = sum(1 for r in results if r.overall == "WARN")
    fail = sum(1 for r in results if r.overall == "FAIL")

    print(f"\n  {'─' * 50}")
    print(f"  ✅ {ok}  ⚠️  {warn}  ❌ {fail}  "
          f"({total} entries in {elapsed:.1f}s)")

    if fail > 0:
        print(f"\n  FAIL entries:")
        for r in results:
            if r.overall == "FAIL":
                # Show most critical check
                critical = [c for c in r.checks if c["status"] == "FAIL"]
                reason = critical[0]["field"] if critical else "unknown"
                print(f"    ❌ {r.key} — {reason}")

    print(f"  {'─' * 50}")

    # -- Output --
    if args.json:
        import json
        data = {
            "version": _get_version(),
            "file": bib_path,
            "summary": {"total": total, "ok": ok, "warn": warn, "fail": fail,
                        "elapsed_seconds": round(elapsed, 1)},
            "results": [
                {
                    "key": r.key,
                    "title": r.title,
                    "overall": r.overall,
                    "sources_tried": r.sources_tried,
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
        print(f"\n  Report saved to {args.out}")

    # Auto-fix
    if args.fix:
        fixed = generate_fixed_bib(bib_path, results)
        Path(args.fix).write_text(fixed, encoding="utf-8")
        n_fixes = sum(1 for r in results if r.suggested_fixes)
        print(f"  Fixed .bib saved to {args.fix} ({n_fixes} entries with fixes)")

    # Print report to stdout if no --out
    if not args.out:
        print()
        print(output)

    # Exit code
    has_fail = any(r.overall == "FAIL" for r in results)
    has_fail = has_fail or any(i["type"] == "FAIL" for i in tex_issues)
    sys.exit(1 if has_fail else 0)


def _get_version() -> str:
    try:
        from bibguard import __version__
        return __version__
    except ImportError:
        return "unknown"


if __name__ == "__main__":
    main()
