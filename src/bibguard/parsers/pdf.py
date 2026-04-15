"""Extract references from a compiled PDF and resolve to BibTeX entries.

Uses PyMuPDF for text extraction, then resolves each reference string
via Crossref and Semantic Scholar APIs to produce structured entries
compatible with bibguard's verification pipeline.
"""

from __future__ import annotations

import re
import textwrap
from pathlib import Path
from typing import Optional

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Step 1: Extract the references section text from a PDF
# ---------------------------------------------------------------------------

_REF_HEADING = re.compile(
    r"^\s*(References|Bibliography|Works\s+Cited|Literature\s+Cited"
    r"|REFERENCES|BIBLIOGRAPHY)\s*$",
    re.MULTILINE,
)

# Common section headings that signal the end of references
_NEXT_SECTION = re.compile(
    r"^\s*(Appendi(?:x|ces)|Supplementary|Acknowledgment|A\.\s|B\.\s|"
    r"APPENDIX|SUPPLEMENTARY|ACKNOWLEDGMENT)",
    re.MULTILINE,
)


def _extract_references_text(pdf_path: str) -> str:
    """Return the raw text of the References section from a PDF."""
    if fitz is None:
        raise ImportError(
            "PyMuPDF is required for PDF parsing. "
            "Install it with: pip install 'bibguard[pdf]'"
        )
    doc = fitz.open(pdf_path)
    full_text = ""
    for page in doc:
        full_text += page.get_text("text") + "\n"
    doc.close()

    # Find the start of the references section
    m = _REF_HEADING.search(full_text)
    if not m:
        raise ValueError(
            f"Could not find a 'References' section in {pdf_path}. "
            "The PDF may not contain a standard reference heading."
        )
    ref_start = m.end()

    # Find the end (next major section or EOF)
    m_end = _NEXT_SECTION.search(full_text, ref_start)
    ref_text = full_text[ref_start : m_end.start()] if m_end else full_text[ref_start:]
    return ref_text.strip()


# ---------------------------------------------------------------------------
# Step 2: Split references text into individual reference strings
# ---------------------------------------------------------------------------

# Numbered references: [1], [2], ...  or  1.  2.  etc.
_NUM_BRACKET = re.compile(r"^\s*\[(\d+)\]\s*", re.MULTILINE)
_NUM_DOT = re.compile(r"^\s*(\d+)\.\s+(?=[A-Z])", re.MULTILINE)


def _split_references(text: str) -> list[str]:
    """Split the references block into individual reference strings."""
    # Try bracket-numbered first: [1] ... [2] ...
    splits = list(_NUM_BRACKET.finditer(text))
    if len(splits) >= 3:
        refs = []
        for i, m in enumerate(splits):
            start = m.end()
            end = splits[i + 1].start() if i + 1 < len(splits) else len(text)
            ref = text[start:end].strip()
            if ref:
                refs.append(_clean_ref(ref))
        return refs

    # Try dot-numbered: 1. ... 2. ...
    splits = list(_NUM_DOT.finditer(text))
    if len(splits) >= 3:
        refs = []
        for i, m in enumerate(splits):
            start = m.end()
            end = splits[i + 1].start() if i + 1 < len(splits) else len(text)
            ref = text[start:end].strip()
            if ref:
                refs.append(_clean_ref(ref))
        return refs

    # Fallback: split by blank lines (author-date style)
    chunks = re.split(r"\n\s*\n", text)
    refs = [_clean_ref(c) for c in chunks if len(c.strip()) > 30]
    return refs


def _clean_ref(text: str) -> str:
    """Normalize whitespace in a reference string."""
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------------------
# Step 3: Parse author/title/year from a raw reference string
# ---------------------------------------------------------------------------

def _parse_ref_string(ref: str) -> dict:
    """Best-effort extraction of author, title, year from a reference string."""
    # Year: look for (2023) or , 2023, or . 2023.
    year_m = re.search(r"[\(\.,]\s*((?:19|20)\d{2})\s*[\)\.,]", ref)
    year = year_m.group(1) if year_m else ""

    # Title: typically the first quoted or italicized string,
    # or the text between the author block and the venue.
    # Heuristic: after the year (in author-date) or after "." following authors.
    title = ""
    # Try: text between first period and second period (common format)
    parts = ref.split(".")
    if len(parts) >= 3:
        # First part is typically authors, second is title
        candidate = parts[1].strip()
        # Remove year if embedded
        candidate = re.sub(r"\(?\d{4}\)?\.?\s*", "", candidate).strip()
        if len(candidate) > 10:
            title = candidate

    # Fallback: try to find quoted title
    if not title:
        quoted = re.search(r'["\u201c](.+?)["\u201d]', ref)
        if quoted:
            title = quoted.group(1)

    # Fallback: longest sentence-like chunk
    if not title:
        sentences = re.split(r"\.\s+", ref)
        if len(sentences) >= 2:
            title = max(sentences[:3], key=len).strip()

    # Author: text before the year or first period
    author = ""
    if year_m:
        author = ref[: year_m.start()].strip().rstrip(",. ")
    elif parts:
        author = parts[0].strip()

    return {
        "raw": ref,
        "title": title,
        "author": author,
        "year": year,
    }


# ---------------------------------------------------------------------------
# Step 4: Resolve references via APIs → BibTeX entries
# ---------------------------------------------------------------------------

def _resolve_via_crossref_query(ref_str: str) -> Optional[dict]:
    """Use Crossref's free-text query API to resolve a reference string."""
    import requests
    from bibguard.sources._common import HEADERS, rate_limit

    rate_limit("crossref")
    url = "https://api.crossref.org/works"
    # Use the full reference string as a bibliographic query
    params = {"query.bibliographic": ref_str[:300], "rows": 3}
    try:
        r = requests.get(url, params=params, headers={**HEADERS, "Accept": "application/json"},
                         timeout=15)
        r.raise_for_status()
        items = r.json()["message"]["items"]
    except (requests.RequestException, KeyError, ValueError):
        return None

    if not items:
        return None

    best = items[0]
    score = best.get("score", 0)
    if score < 50:
        return None

    title = (best.get("title") or [""])[0]
    authors = []
    for a in best.get("author", []):
        name = f"{a.get('given', '')} {a.get('family', '')}".strip()
        if name:
            authors.append(name)
    year = None
    for df in ("published-print", "published-online", "created"):
        if df in best:
            parts = best[df].get("date-parts", [[]])[0]
            if parts:
                year = str(parts[0])
                break
    venue = ""
    for v in best.get("container-title", []):
        if v:
            venue = v
            break
    doi = best.get("DOI", "")

    return {
        "title": title,
        "authors": authors,
        "year": year,
        "venue": venue,
        "doi": doi,
        "score": score,
    }


def _resolve_via_s2(title: str, author: str = "") -> Optional[dict]:
    """Use Semantic Scholar title search to resolve a reference."""
    from bibguard.sources.s2 import query_s2
    return query_s2(title, bib_first_author=author)


def _make_bib_key(authors: list[str], year: str, index: int) -> str:
    """Generate a BibTeX key like 'wang2023' from author list and year."""
    if authors:
        surname = authors[0].split()[-1].lower() if authors[0].split() else "unknown"
        surname = re.sub(r"[^a-z]", "", surname)
    else:
        surname = "ref"
    return f"{surname}{year or 'xxxx'}_{index}"


def _to_bib_entry(data: dict, key: str) -> str:
    """Format a resolved reference as a BibTeX @article entry."""
    authors_bib = " and ".join(data.get("authors", []))
    lines = [f"@article{{{key},"]
    if data.get("title"):
        lines.append(f'  title     = {{{data["title"]}}},')
    if authors_bib:
        lines.append(f"  author    = {{{authors_bib}}},")
    if data.get("year"):
        lines.append(f'  year      = {{{data["year"]}}},')
    if data.get("venue"):
        lines.append(f'  journal   = {{{data["venue"]}}},')
    if data.get("doi"):
        lines.append(f'  doi       = {{{data["doi"]}}},')
    if data.get("arxiv_id"):
        lines.append(f'  eprint    = {{{data["arxiv_id"]}}},')
        lines.append("  archiveprefix = {arXiv},")
    lines.append("}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_refs_from_pdf(pdf_path: str) -> list[dict]:
    """Extract and parse references from a PDF.

    Returns a list of dicts with keys: raw, title, author, year.
    Does NOT call any APIs -- fast, local-only.
    """
    text = _extract_references_text(pdf_path)
    raw_refs = _split_references(text)
    return [_parse_ref_string(r) for r in raw_refs]


def pdf_to_bib(
    pdf_path: str,
    output_path: str | None = None,
    workers: int = 1,
    progress: object = None,
) -> tuple[str, list[dict]]:
    """Extract references from PDF and resolve them to BibTeX.

    Returns (bib_string, resolution_log) where resolution_log contains
    details about each reference resolution attempt.

    Args:
        pdf_path:    Path to the PDF file.
        output_path: If given, write the .bib to this file.
        workers:     Concurrent workers for API resolution.
        progress:    Optional callback(index, total, ref_dict).
    """
    if not Path(pdf_path).exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    refs = extract_refs_from_pdf(pdf_path)
    if not refs:
        raise ValueError(f"No references found in {pdf_path}")

    log: list[dict] = []
    bib_entries: list[str] = []

    def _resolve_one(idx: int, ref: dict) -> None:
        entry = {
            "index": idx + 1,
            "raw": ref["raw"],
            "resolved": False,
            "source": None,
            "key": None,
        }

        # Strategy 1: Crossref bibliographic query (best for full ref strings)
        data = _resolve_via_crossref_query(ref["raw"])
        if data:
            key = _make_bib_key(data.get("authors", []), data.get("year", ""), idx + 1)
            entry["resolved"] = True
            entry["source"] = "crossref"
            entry["key"] = key
            entry["data"] = data
            bib_entries.append(_to_bib_entry(data, key))
            log.append(entry)
            if progress:
                progress(idx, len(refs), entry)  # type: ignore[operator]
            return

        # Strategy 2: Semantic Scholar title search
        if ref["title"]:
            data = _resolve_via_s2(ref["title"], ref["author"])
            if data:
                key = _make_bib_key(data.get("authors", []), data.get("year", ""), idx + 1)
                entry["resolved"] = True
                entry["source"] = "s2"
                entry["key"] = key
                entry["data"] = data
                bib_entries.append(_to_bib_entry(data, key))
                log.append(entry)
                if progress:
                    progress(idx, len(refs), entry)  # type: ignore[operator]
                return

        # Unresolved
        entry["title_guess"] = ref["title"]
        log.append(entry)
        if progress:
            progress(idx, len(refs), entry)  # type: ignore[operator]

    if workers <= 1:
        for i, ref in enumerate(refs):
            _resolve_one(i, ref)
    else:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading

        lock = threading.Lock()

        def _work(idx: int, ref: dict) -> None:
            # Each thread appends to shared lists under lock
            local_entry = {"index": idx + 1, "raw": ref["raw"], "resolved": False,
                           "source": None, "key": None}

            data = _resolve_via_crossref_query(ref["raw"])
            if not data and ref["title"]:
                data = _resolve_via_s2(ref["title"], ref["author"])
                src = "s2"
            else:
                src = "crossref"

            if data:
                key = _make_bib_key(data.get("authors", []), data.get("year", ""), idx + 1)
                local_entry.update(resolved=True, source=src, key=key, data=data)
                bib_str = _to_bib_entry(data, key)
                with lock:
                    bib_entries.append(bib_str)
                    log.append(local_entry)
            else:
                local_entry["title_guess"] = ref["title"]
                with lock:
                    log.append(local_entry)

            if progress:
                progress(idx, len(refs), local_entry)  # type: ignore[operator]

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(_work, i, r) for i, r in enumerate(refs)]
            for f in as_completed(futures):
                f.result()  # propagate exceptions

    bib_text = "\n\n".join(bib_entries) + "\n" if bib_entries else ""

    if output_path:
        Path(output_path).write_text(bib_text, encoding="utf-8")

    return bib_text, log
