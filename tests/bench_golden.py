#!/usr/bin/env python3
"""Benchmark bibguard against the 58-case golden test set.

The golden test set contains publicly available references:
- 10 real papers (well-known, should pass)
- 28 retracted papers (famous retractions, should flag)
- 15 LLM-hallucinated citations (fabricated, should FAIL)
  - includes 1 control: a real paper with an arXiv-style DOI
- 5 metadata chimeras (real titles + wrong metadata, should FAIL/WARN)

Usage:
    python tests/bench_golden.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from bibguard.core import verify_entry
from bibguard.parsers.bibtex import parse_bib


def main() -> None:
    bib_path = Path(__file__).parent / "golden_benchmark.bib"
    labels_path = Path(__file__).parent / "golden_labels.json"

    if not bib_path.exists() or not labels_path.exists():
        print("Error: golden_benchmark.bib or golden_labels.json not found in tests/")
        sys.exit(1)

    entries = parse_bib(str(bib_path))
    labels = json.loads(labels_path.read_text())

    print(f"\nbibguard benchmark — {len(entries)} entries\n")
    print(f"{'#':>3}  {'Status':<6} {'Category':<14} {'Key':<35} Sources")
    print("─" * 85)

    t0 = time.time()
    results = []
    for i, entry in enumerate(entries):
        r = verify_entry(entry)
        cat = labels.get(entry["key"], "?")
        results.append({"key": entry["key"], "cat": cat, "overall": r.overall,
                        "sources_hit": r.sources_hit, "checks": r.checks})
        src = ", ".join(r.sources_hit) if r.sources_hit else "none"
        icon = {"OK": "✅", "WARN": "⚠️ ", "FAIL": "❌"}[r.overall]
        print(f"{i+1:>3}  {icon:<6} {cat:<14} {entry['key']:<35} {src}")

    elapsed = time.time() - t0

    # -- Metrics --
    cats: dict[str, dict] = {}
    for r in results:
        c = r["cat"]
        cats.setdefault(c, {"OK": 0, "WARN": 0, "FAIL": 0, "total": 0})
        cats[c][r["overall"]] += 1
        cats[c]["total"] += 1

    print(f"\n{'═' * 85}")
    print(f"  Runtime: {elapsed:.1f}s ({elapsed/len(entries):.1f}s/entry)\n")

    real = cats.get("real", {})
    halluc = cats.get("hallucinated", {})
    chim = cats.get("chimera", {})
    ret = cats.get("retracted", {})

    # halluc_014 is a control (real paper), adjust counts
    # Count truly hallucinated = FAIL among hallucinated minus controls
    # For simplicity, report raw numbers and note the control
    halluc_fail = halluc.get("FAIL", 0)
    halluc_warn = halluc.get("WARN", 0)
    halluc_total = halluc.get("total", 0)

    print(f"  {'Metric':<45} {'Result':>10}")
    print(f"  {'─' * 55}")
    print(f"  {'Real papers — clean pass (OK)':<45} {real.get('OK',0):>3}/{real.get('total',0)}")
    print(f"  {'Real papers — false positive (FAIL)':<45} {real.get('FAIL',0):>3}/{real.get('total',0)}")
    print(f"  {'Hallucinated — detected (FAIL)':<45} {halluc_fail:>3}/{halluc_total}  *")
    print(f"  {'Hallucinated — detected (>=WARN)':<45} {halluc_fail+halluc_warn:>3}/{halluc_total}  *")
    print(f"  {'Chimera — detected (>=WARN)':<45} {chim.get('FAIL',0)+chim.get('WARN',0):>3}/{chim.get('total',0)}")
    print(f"  {'Retracted — any issue (>=WARN)':<45} {ret.get('WARN',0)+ret.get('FAIL',0):>3}/{ret.get('total',0)}")
    print()
    print("  * halluc group includes 1 control (real paper); 14/15 are truly fabricated")
    print()


if __name__ == "__main__":
    main()
