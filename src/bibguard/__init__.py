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

__version__ = "0.4.0"

from bibguard.core import verify_bib, verify_entry, VerificationResult
from bibguard.parsers.bibtex import parse_bib
from bibguard.tex_audit import audit_tex_bib
from bibguard.duplicates import detect_duplicates
from bibguard.report import generate_report
from bibguard.autofix import generate_fixed_bib
from bibguard.feedback import log_feedback, show_feedback, feedback_stats

# PDF features (require pymupdf optional dependency)
from bibguard.parsers.pdf import extract_refs_from_pdf, pdf_to_bib
from bibguard.injection_detect import scan_pdf, format_scan_report, ScanResult

__all__ = [
    "verify_bib",
    "verify_entry",
    "VerificationResult",
    "parse_bib",
    "audit_tex_bib",
    "detect_duplicates",
    "generate_report",
    "generate_fixed_bib",
    "log_feedback",
    "show_feedback",
    "feedback_stats",
    # PDF features
    "extract_refs_from_pdf",
    "pdf_to_bib",
    "scan_pdf",
    "format_scan_report",
    "ScanResult",
]
