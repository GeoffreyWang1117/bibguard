"""Command-line interface for bibguard."""

from __future__ import annotations

import argparse
import os
import sys
import threading
import time
from pathlib import Path

from bibguard.autofix import generate_fixed_bib
from bibguard.core import VerificationResult, verify_bib
from bibguard.duplicates import detect_duplicates
from bibguard.parsers.bibtex import parse_bib
from bibguard.report import generate_report
from bibguard.tex_audit import audit_tex_bib

_ICON = {"OK": "✅", "WARN": "⚠️ ", "FAIL": "❌"}


def _default_workers(total: int) -> int:
    """Pick a sensible default worker count based on entry count."""
    if total <= 8:
        return 1
    return min(4, os.cpu_count() or 4)


def _run_feedback(argv: list[str]) -> None:
    """Handle the ``bibguard feedback`` subcommand."""
    from bibguard.feedback import log_feedback, show_feedback, feedback_stats

    p = argparse.ArgumentParser(prog="bibguard feedback",
                                description="Log and view feedback for bibguard")
    p.add_argument("--issue", help="Description of the issue")
    p.add_argument("--severity", choices=("critical", "major", "minor", "suggestion"),
                   default="minor")
    p.add_argument("--context", help="What was being verified when the issue occurred")
    p.add_argument("--tag", help="Category tag (e.g. phantom, matching, perf)")
    p.add_argument("--bib", help="Path to the .bib file involved")
    p.add_argument("--expected", help="Expected result")
    p.add_argument("--actual", help="Actual result")
    p.add_argument("--show", action="store_true", help="Show recent feedback")
    p.add_argument("--last", type=int, help="Number of entries to show (with --show)")
    p.add_argument("--stats", action="store_true", help="Show feedback statistics")
    args = p.parse_args(argv)

    if args.stats:
        stats = feedback_stats()
        print(f"  Feedback: {stats['total']} total — "
              f"critical: {stats['critical']}, major: {stats['major']}, "
              f"minor: {stats['minor']}, suggestion: {stats['suggestion']}")
        return

    if args.show:
        entries = show_feedback(last=args.last)
        if not entries:
            print("  No feedback recorded yet.")
            return
        for e in entries:
            sev = e.get("severity", "?")
            ts = e.get("timestamp", "?")[:19]
            issue = e.get("issue", "")
            print(f"  [{ts}] {sev.upper():>10s}  {issue}")
            if e.get("context"):
                print(f"{'':14s}context: {e['context']}")
        return

    if not args.issue:
        p.error("--issue is required when logging feedback (or use --show / --stats)")

    path = log_feedback(
        issue=args.issue, severity=args.severity, context=args.context,
        tag=args.tag, bib_file=args.bib, expected=args.expected, actual=args.actual,
    )
    print(f"  Feedback saved: {path}")


def _run_scan(argv: list[str]) -> None:
    """Handle the ``bibguard scan`` subcommand for injection detection."""
    from bibguard.injection_detect import scan_pdf, format_scan_report

    p = argparse.ArgumentParser(
        prog="bibguard scan",
        description="Scan a PDF for AI-reviewer-targeted prompt injections",
    )
    p.add_argument("pdf", help="PDF file path to scan")
    p.add_argument("--json", action="store_true", help="Output JSON instead of Markdown")
    p.add_argument("--out", help="Save report to file")
    p.add_argument("--no-visible", action="store_true",
                   help="Skip visible text pattern checks")
    p.add_argument("--no-hidden", action="store_true",
                   help="Skip hidden text detection")
    p.add_argument("--no-metadata", action="store_true",
                   help="Skip PDF metadata checks")
    args = p.parse_args(argv)

    if not Path(args.pdf).exists():
        print(f"bibguard scan: error: file not found: {args.pdf}", file=sys.stderr)
        sys.exit(2)

    print(f"\n  bibguard v{_get_version()} — injection scanner")
    print(f"  Scanning: {args.pdf}\n")

    result = scan_pdf(
        args.pdf,
        check_visible=not args.no_visible,
        check_hidden=not args.no_hidden,
        check_metadata=not args.no_metadata,
    )

    # Print findings live
    _SCAN_ICON = {"FAIL": "☠️", "WARN": "⚠️ "}
    for f in result.findings:
        icon = _SCAN_ICON.get(f.severity, "❓")
        page_str = f"p.{f.page}" if f.page else "meta"
        print(f"  {icon} [{page_str}] {f.description}")
        if f.text_snippet:
            snippet = f.text_snippet.replace("\n", " ")[:80]
            print(f"       └─ `{snippet}`")

    # Verdict
    print(f"\n  {'─' * 50}")
    verdict_icon = {"FAIL": "☠️", "WARN": "⚠️ ", "CLEAN": "✅"}[result.verdict]
    print(f"  {verdict_icon} Verdict: {result.verdict} "
          f"({result.fail_count} injections, {result.warn_count} warnings, "
          f"{result.pages_scanned} pages scanned)")
    if result.hidden_text_blocks:
        print(f"  🔍 Hidden text blocks found: {result.hidden_text_blocks}")
    print(f"  {'─' * 50}")

    # Output
    if args.json:
        import json
        output = json.dumps(result.to_dict(), indent=2, ensure_ascii=False)
    else:
        output = format_scan_report(result)

    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
        print(f"\n  Report saved to {args.out}")
    elif not args.json:
        pass  # Already printed live
    else:
        print()
        print(output)

    sys.exit(1 if result.verdict == "FAIL" else 0)


def _run_pdf(argv: list[str]) -> None:
    """Handle the ``bibguard pdf`` subcommand for PDF reference extraction."""
    from bibguard.parsers.pdf import pdf_to_bib
    from bibguard.injection_detect import scan_pdf

    p = argparse.ArgumentParser(
        prog="bibguard pdf",
        description="Extract references from a PDF and verify them",
    )
    p.add_argument("pdf", help="PDF file path")
    p.add_argument("--bib-out", help="Save extracted .bib to this path")
    p.add_argument("--verify", action="store_true",
                   help="Run full verification on extracted references")
    p.add_argument("--scan", action="store_true", default=True,
                   help="Run injection scan (default: on)")
    p.add_argument("--no-scan", action="store_true",
                   help="Skip injection scan")
    p.add_argument("-w", "--workers", type=int, default=None,
                   help="Concurrent workers for API resolution")
    p.add_argument("--json", action="store_true", help="Output JSON")
    p.add_argument("--out", help="Save report to file")
    args = p.parse_args(argv)

    if not Path(args.pdf).exists():
        print(f"bibguard pdf: error: file not found: {args.pdf}", file=sys.stderr)
        sys.exit(2)

    print(f"\n  bibguard v{_get_version()} — PDF mode")
    print(f"  {args.pdf}\n")

    has_fail = False

    # Step 1: Injection scan (always first -- reject poisoned PDFs early)
    if not args.no_scan:
        print("  ── Injection Scan ──")
        scan_result = scan_pdf(args.pdf)
        if scan_result.findings:
            _SCAN_ICON = {"FAIL": "☠️", "WARN": "⚠️ "}
            for f in scan_result.findings:
                icon = _SCAN_ICON.get(f.severity, "❓")
                page_str = f"p.{f.page}" if f.page else "meta"
                print(f"    {icon} [{page_str}] {f.description}")
        else:
            print("    ✅ No injections detected")

        if scan_result.verdict == "FAIL":
            print(f"\n  ☠️  INJECTION DETECTED — paper is REJECTED.")
            print(f"  Aborting reference extraction (untrusted document).\n")
            sys.exit(1)
        print()

    # Step 2: Extract references from PDF
    print("  ── Reference Extraction ──")
    t0 = time.time()
    _print_lock = threading.Lock()
    _counter = [0]

    def _progress(idx: int, total: int, entry: dict) -> None:
        with _print_lock:
            _counter[0] += 1
            n = _counter[0]
            status = "✅" if entry.get("resolved") else "❌"
            source = entry.get("source", "—")
            raw_short = entry.get("raw", "")[:60]
            print(f"    [{n:>{len(str(total))}}/{total}] {status} ({source}) {raw_short}")

    workers = args.workers if args.workers is not None else _default_workers(50)
    bib_text, log = pdf_to_bib(args.pdf, output_path=args.bib_out,
                                workers=workers, progress=_progress)
    elapsed = time.time() - t0

    resolved = sum(1 for e in log if e.get("resolved"))
    unresolved = len(log) - resolved
    print(f"\n    Resolved: {resolved}/{len(log)} refs in {elapsed:.1f}s")
    if unresolved:
        print(f"    ❌ Unresolved ({unresolved}):")
        for e in log:
            if not e.get("resolved"):
                title = e.get("title_guess", e.get("raw", "")[:60])
                print(f"       — {title}")

    if args.bib_out:
        print(f"    📄 BibTeX saved to {args.bib_out}")

    # Step 3: Optional full verification
    if args.verify and bib_text and args.bib_out:
        print(f"\n  ── Verification ──")
        from bibguard.core import verify_bib
        results, report = verify_bib(args.bib_out, verbose=False, workers=workers)
        ok = sum(1 for r in results if r.overall == "OK")
        warn = sum(1 for r in results if r.overall == "WARN")
        fail = sum(1 for r in results if r.overall == "FAIL")
        print(f"    ✅ {ok}  ⚠️  {warn}  ❌ {fail}")
        if fail > 0:
            has_fail = True

    print(f"\n  {'─' * 50}")
    sys.exit(1 if has_fail else 0)


def main(argv: list[str] | None = None) -> None:
    # Handle subcommands before argparse
    raw = argv if argv is not None else sys.argv[1:]
    if raw and raw[0] == "feedback":
        _run_feedback(raw[1:])
        return
    if raw and raw[0] == "scan":
        _run_scan(raw[1:])
        return
    if raw and raw[0] == "pdf":
        _run_pdf(raw[1:])
        return

    parser = argparse.ArgumentParser(
        prog="bibguard",
        description="Detect hallucinated and broken citations in academic papers",
    )
    parser.add_argument("bib", help=".bib file path")
    parser.add_argument("--tex", help=".tex file path (enables cross-audit)")
    parser.add_argument("--out", help="Output report path (Markdown or JSON)")
    parser.add_argument("--fix", help="Output auto-fixed .bib path")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of Markdown")
    parser.add_argument("-w", "--workers", type=int, default=None,
                        help="Concurrent workers (default: auto, 1=sequential)")
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
    workers = args.workers if args.workers is not None else _default_workers(total)
    print(f"\n  bibguard v{_get_version()}")
    mode = f"{workers} workers" if workers > 1 else "sequential"
    print(f"  {bib_path} — {total} entries ({mode})\n")

    # -- Verify --
    t0 = time.time()
    _print_lock = threading.Lock()
    _counter = [0]  # mutable counter for thread-safe progress

    def _progress(idx: int, total_n: int, r: VerificationResult) -> None:
        sources = ", ".join(r.sources_hit) if r.sources_hit else "no match"
        key_display = r.key[:40]
        with _print_lock:
            _counter[0] += 1
            n = _counter[0]
            print(f"  [{n:>{len(str(total_n))}}/{total_n}] {key_display:<40s} "
                  f"{_ICON[r.overall]} {sources}")

    results, _ = verify_bib(bib_path, tex_path=None, verbose=args.verbose,
                            workers=workers, progress=_progress)

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
