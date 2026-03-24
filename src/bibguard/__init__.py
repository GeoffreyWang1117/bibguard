"""bibguard: Detect hallucinated and broken citations in academic papers.

Five-source cascade verification (arXiv, Crossref, DBLP, Semantic Scholar,
OpenAlex) with phantom-ID detection, TeX cross-audit, duplicate detection,
and auto-fix.

Quick start::

    from bibguard import verify_bib
    results, report = verify_bib("references.bib")

CLI::

    bibguard paper.bib
    bibguard paper.bib --tex main.tex --fix
"""

__version__ = "0.2.0"

from bibguard.core import verify_bib, verify_entry, VerificationResult
from bibguard.parsers.bibtex import parse_bib
from bibguard.tex_audit import audit_tex_bib
from bibguard.duplicates import detect_duplicates
from bibguard.report import generate_report
from bibguard.autofix import generate_fixed_bib

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
