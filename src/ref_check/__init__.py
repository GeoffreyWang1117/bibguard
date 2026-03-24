"""ref-check: Detect hallucinated and broken citations in academic papers.

Five-source cascade verification (arXiv, Crossref, DBLP, Semantic Scholar,
OpenAlex) with phantom-ID detection, TeX cross-audit, duplicate detection,
and auto-fix.

Quick start::

    from ref_check import verify_bib
    results, report = verify_bib("references.bib")

CLI::

    ref-check paper.bib
    ref-check paper.bib --tex main.tex --fix
"""

__version__ = "0.1.0"

from ref_check.core import verify_bib, verify_entry, VerificationResult
from ref_check.parsers.bibtex import parse_bib
from ref_check.tex_audit import audit_tex_bib
from ref_check.duplicates import detect_duplicates
from ref_check.report import generate_report
from ref_check.autofix import generate_fixed_bib

__all__ = [
    "verify_bib",
    "verify_entry",
    "VerificationResult",
    "parse_bib",
    "audit_tex_bib",
    "detect_duplicates",
    "generate_report",
    "generate_fixed_bib",
]
