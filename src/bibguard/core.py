"""Core verification engine.

Five-source cascade: arXiv -> Crossref -> DBLP -> Semantic Scholar -> OpenAlex.
Phantom-ID detection with kill-shot override.
"""

from __future__ import annotations

import re
from typing import Optional

from bibguard.matching import (
    extract_first_surname,
    match_authors,
    match_title,
    match_venue,
    match_year,
    strip_accents,
    token_similarity,
)
from bibguard.parsers.bibtex import extract_arxiv_id, parse_bib
from bibguard.sources.arxiv import query_arxiv
from bibguard.sources.crossref import query_crossref
from bibguard.sources.dblp import query_dblp
from bibguard.sources.openalex import query_openalex
from bibguard.sources.s2 import query_s2


class VerificationResult:
    """Result of verifying a single bib entry."""

    def __init__(self, key: str, title: str):
        self.key = key
        self.title = title
        self.sources_tried: list[str] = []
        self.sources_hit: list[str] = []
        self.checks: list[dict] = []
        self.api_data: dict = {}
        self.overall = "OK"
        self.suggested_fixes: dict = {}

    def add_check(self, field: str, status: str, detail: str, source: str = ""):
        self.checks.append({"field": field, "status": status, "detail": detail, "source": source})
        if status == "FAIL" and self.overall != "FAIL":
            self.overall = "FAIL"
        elif status == "WARN" and self.overall == "OK":
            self.overall = "WARN"


def _validate_api_match(entry: dict, data: dict, require_author: bool = False) -> bool:
    """Check if an API result is a plausible match for the bib entry."""
    if not data:
        return False
    api_authors = data.get("authors", [])
    if api_authors:
        bib_surname = extract_first_surname(entry["author"])
        api_first = api_authors[0]
        api_surname = api_first.split()[-1].lower() if api_first.split() else ""
        author_match = strip_accents(bib_surname) == strip_accents(api_surname)

        if require_author and not author_match:
            return False

        if not author_match:
            api_year = data.get("year")
            if api_year:
                try:
                    year_diff = abs(int(entry["year"]) - int(api_year))
                except (ValueError, TypeError):
                    year_diff = 0
                if year_diff >= 2:
                    return False
            api_title = data.get("title", "")
            if token_similarity(entry.get("title", ""), api_title) < 0.85:
                return False
    return True


def _check_source(result: VerificationResult, entry: dict, data: dict,
                  source: str, check_venue: bool = True) -> None:
    """Run field checks against one API source and record results."""
    result.sources_hit.append(source)
    result.api_data[source] = data

    s, d = match_title(entry["title"], data["title"])
    result.add_check("title", s, d, source)
    s, d = match_authors(entry["author"], data["authors"])
    result.add_check("authors", s, d, source)
    s, d = match_year(entry["year"], data["year"])
    result.add_check("year", s, d, source)
    if check_venue and data.get("venue"):
        s, d = match_venue(entry["venue"], data["venue"])
        result.add_check("venue", s, d, source)


def verify_entry(entry: dict, verbose: bool = False) -> VerificationResult:
    """Verify a single bib entry against all available sources."""
    result = VerificationResult(entry["key"], entry["title"])

    # -- Source 1: arXiv (by ID) --
    if entry.get("arxiv_id"):
        result.sources_tried.append("arxiv")
        data = query_arxiv(entry["arxiv_id"])
        if data:
            _check_source(result, entry, data, "arxiv", check_venue=False)

    # -- Source 2: Crossref (by DOI) --
    doi = entry.get("doi", "")
    if doi:
        result.sources_tried.append("crossref")
        data = query_crossref(doi)
        if data:
            _check_source(result, entry, data, "crossref")
            if data.get("is_retracted"):
                result.add_check("retraction", "FAIL", "RETRACTED PAPER!", "crossref")

    # -- Phantom ID detection --
    has_phantom_doi = False
    if doi and re.match(r"^10\.\d{4,}/", doi) and "crossref" not in result.sources_hit:
        has_phantom_doi = True
        result.add_check("phantom_doi", "FAIL",
                         f"DOI '{doi}' has valid format but doesn't resolve "
                         f"-- likely hallucinated or incorrect", "crossref")

    arxiv_id = entry.get("arxiv_id") or extract_arxiv_id(entry)
    has_phantom_arxiv = False
    if arxiv_id and re.match(r"^\d{4}\.\d{4,5}", arxiv_id) and "arxiv" not in result.sources_hit:
        has_phantom_arxiv = True
        result.add_check("phantom_arxiv", "FAIL",
                         f"arXiv ID '{arxiv_id}' has valid format but doesn't exist "
                         f"-- likely hallucinated or incorrect", "arxiv")

    has_phantom_id = has_phantom_doi or has_phantom_arxiv

    # Search title variants
    search_title = entry["title"]
    alt_title = re.sub(r"(\b[A-Z]+)(\d+)\b", r"\1", entry["title"])
    search_titles = [search_title]
    if alt_title != search_title:
        search_titles.append(alt_title)

    # -- Source 3: DBLP (by title search) --
    result.sources_tried.append("dblp")
    data = None
    for st in search_titles:
        data = query_dblp(st, bib_first_author=entry["author"])
        if data and _validate_api_match(entry, data, require_author=has_phantom_id):
            break
        data = None
    if data:
        _check_source(result, entry, data, "dblp")
        if data.get("doi") and not entry.get("doi"):
            result.suggested_fixes["doi"] = data["doi"]

    # -- Source 4: Semantic Scholar (by title search) --
    result.sources_tried.append("s2")
    data = None
    for st in search_titles:
        data = query_s2(st, bib_first_author=entry["author"])
        if data and _validate_api_match(entry, data, require_author=has_phantom_id):
            break
        data = None
    if data:
        _check_source(result, entry, data, "s2")
        if data.get("doi") and not entry.get("doi") and "doi" not in result.suggested_fixes:
            result.suggested_fixes["doi"] = data["doi"]
        if data.get("arxiv_id") and not entry.get("arxiv_id"):
            result.suggested_fixes["eprint"] = data["arxiv_id"]
        if data.get("citation_count") is not None:
            result.add_check("citations", "OK", f"citation count: {data['citation_count']}", "s2")

    # -- Source 5: OpenAlex (fallback for non-CS / old papers) --
    if not result.sources_hit:
        result.sources_tried.append("openalex")
        data = None
        for st in search_titles:
            data = query_openalex(st, bib_first_author=entry["author"])
            if data and _validate_api_match(entry, data, require_author=has_phantom_id):
                break
            data = None
        if data:
            _check_source(result, entry, data, "openalex")
            if data.get("doi") and not entry.get("doi") and "doi" not in result.suggested_fixes:
                result.suggested_fixes["doi"] = data["doi"]
            if data.get("is_retracted"):
                result.add_check("retraction", "FAIL", "RETRACTED PAPER!", "openalex")
            if data.get("cited_by_count") is not None:
                result.add_check("citations", "OK",
                                 f"citation count: {data['cited_by_count']}", "openalex")

    # -- No source hit --
    if not result.sources_hit:
        result.add_check("verification", "FAIL",
                         f"NO API MATCH -- paper may be hallucinated or title differs significantly "
                         f"(tried: {', '.join(result.sources_tried)})")
        result.overall = "FAIL"

    # -- Post-processing: source-aware overall status --
    source_statuses = {}
    for src in result.sources_hit:
        src_checks = [c for c in result.checks if c["source"] == src]
        title_ok = any(c["field"] == "title" and c["status"] == "OK" for c in src_checks)
        author_ok = any(c["field"] == "authors" and c["status"] in ("OK", "WARN") for c in src_checks)
        if title_ok and author_ok:
            source_statuses[src] = "confirmed"
            for c in result.checks:
                if c["source"] == src and c["field"] == "year" and c["status"] == "FAIL":
                    c["status"] = "WARN"
                    c["detail"] += " (downgraded: title+author match)"

    if any(v == "confirmed" for v in source_statuses.values()):
        confirmed_sources = {s for s, v in source_statuses.items() if v == "confirmed"}
        result.overall = "OK"
        for c in result.checks:
            if c["source"] not in confirmed_sources:
                continue
            if c["status"] == "FAIL":
                result.overall = "FAIL"
                break
            elif c["status"] == "WARN" and result.overall == "OK":
                result.overall = "WARN"
    else:
        result.overall = "OK"
        for c in result.checks:
            if c["status"] == "FAIL":
                result.overall = "FAIL"
                break
            elif c["status"] == "WARN" and result.overall == "OK":
                result.overall = "WARN"

    # -- Kill-shot: phantom ID overrides search-confirmed status --
    if has_phantom_id and result.overall == "OK":
        result.overall = "WARN"
        if has_phantom_doi:
            result.add_check("hallucination_risk", "WARN",
                             "Search found a similar paper but DOI doesn't resolve "
                             "-- verify this is the correct reference", "bibguard")
        if has_phantom_arxiv:
            result.add_check("hallucination_risk", "WARN",
                             "Search found a similar paper but arXiv ID doesn't exist "
                             "-- verify this is the correct reference", "bibguard")

    return result


def verify_bib(bib_path: str, tex_path: str | None = None,
               verbose: bool = False) -> tuple[list[VerificationResult], str]:
    """Verify all entries in a .bib file. Returns (results, markdown_report)."""
    from bibguard.duplicates import detect_duplicates
    from bibguard.report import generate_report
    from bibguard.tex_audit import audit_tex_bib

    entries = parse_bib(bib_path)
    results = []
    for entry in entries:
        results.append(verify_entry(entry, verbose=verbose))

    tex_issues = audit_tex_bib(tex_path, entries) if tex_path else []
    dup_issues = detect_duplicates(entries)
    report = generate_report(results, tex_issues, dup_issues)
    return results, report
