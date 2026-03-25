#!/usr/bin/env python3
"""Large-scale benchmark on crawled datasets.

Samples from hallucinated (800), chimera (400), real (656), retracted (153).
Converts to bib entries and runs bibguard verification.

Usage:
    python tests/bench_large.py [--sample N] [--full]
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from bibguard.core import verify_entry

DATA_DIR = Path(__file__).resolve().parent.parent / "benchmarks_data"


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def to_bib_entry(item: dict) -> dict:
    """Convert crawled data format to bibguard entry format."""
    authors = item.get("authors", [])
    author_str = " and ".join(authors) if isinstance(authors, list) else str(authors)
    return {
        "key": item.get("id", item.get("doi", "unknown")),
        "type": item.get("type", "article"),
        "title": item.get("title", ""),
        "author": author_str,
        "year": str(item.get("year", "")),
        "doi": item.get("doi", ""),
        "arxiv_id": item.get("arxiv_id"),
        "venue": item.get("venue", ""),
        "journal": item.get("venue", ""),
        "booktitle": "",
        "volume": "",
        "pages": "",
        "url": "",
        "_raw": {},
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=50,
                        help="Samples per category (default: 50)")
    parser.add_argument("--full", action="store_true",
                        help="Run on ALL entries (slow)")
    args = parser.parse_args()

    datasets = {
        "hallucinated": ("hallucinated_papers.jsonl", False, "HIGH"),
        "chimera": ("chimera_papers.jsonl", False, "HIGH"),
        "real": ("real_papers.jsonl", True, "LOW"),
        "retracted": ("crossref_retracted.jsonl", True, "HIGH"),
    }

    all_cases = []
    for cat, (filename, expected_found, expected_risk) in datasets.items():
        path = DATA_DIR / filename
        if not path.exists():
            print(f"  SKIP: {filename} not found")
            continue
        items = load_jsonl(path)
        if not args.full and len(items) > args.sample:
            random.seed(42)
            items = random.sample(items, args.sample)
        for item in items:
            item["_category"] = cat
            item["_expected_found"] = expected_found
        all_cases.extend(items)

    total = len(all_cases)
    print(f"\nbibguard large benchmark — {total} entries\n")

    by_cat = {}
    for item in all_cases:
        cat = item["_category"]
        by_cat.setdefault(cat, [])
        by_cat[cat].append(item)
    for cat, items in by_cat.items():
        print(f"  {cat}: {len(items)}")
    print()

    t0 = time.time()
    results = []
    for i, item in enumerate(all_cases):
        entry = to_bib_entry(item)
        r = verify_entry(entry)
        results.append({
            "key": entry["key"],
            "cat": item["_category"],
            "expected_found": item["_expected_found"],
            "overall": r.overall,
            "sources_hit": r.sources_hit,
        })
        if (i + 1) % 20 == 0 or i + 1 == total:
            elapsed = time.time() - t0
            print(f"  [{i+1}/{total}] {elapsed:.0f}s elapsed "
                  f"({elapsed/(i+1):.1f}s/entry)", flush=True)

    elapsed = time.time() - t0

    # Compute metrics per category
    print(f"\n{'=' * 70}")
    print(f"  Runtime: {elapsed:.0f}s ({elapsed/total:.1f}s/entry)\n")
    print(f"  {'Category':<15} {'N':>5} {'OK':>5} {'WARN':>5} {'FAIL':>5} {'Key Metric':>30}")
    print(f"  {'-'*70}")

    for cat in ["hallucinated", "chimera", "real", "retracted"]:
        cat_results = [r for r in results if r["cat"] == cat]
        if not cat_results:
            continue
        n = len(cat_results)
        ok = sum(1 for r in cat_results if r["overall"] == "OK")
        warn = sum(1 for r in cat_results if r["overall"] == "WARN")
        fail = sum(1 for r in cat_results if r["overall"] == "FAIL")

        if cat in ("hallucinated", "chimera"):
            # Should be FAIL or WARN (detected)
            detected = fail + warn
            metric = f"detected: {detected}/{n} ({100*detected/n:.1f}%)"
        elif cat == "real":
            # Should be OK
            metric = f"clean OK: {ok}/{n} ({100*ok/n:.1f}%)"
        elif cat == "retracted":
            # Should have some issue
            flagged = warn + fail
            metric = f"flagged: {flagged}/{n} ({100*flagged/n:.1f}%)"

        print(f"  {cat:<15} {n:>5} {ok:>5} {warn:>5} {fail:>5} {metric:>30}")

    # Save results
    out_path = Path("/tmp/bibguard_large_bench.json")
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"\n  Results saved to {out_path}")


if __name__ == "__main__":
    main()
