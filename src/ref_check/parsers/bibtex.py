"""BibTeX parser -- extracts standardized entries from .bib files."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import bibtexparser
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode

from ref_check.matching import strip_latex


def extract_arxiv_id(entry: dict) -> Optional[str]:
    """Extract arXiv ID from journal, eprint, url, or note fields."""
    patterns = [
        r"arXiv[:\s]*(\d{4}\.\d{4,5}(?:v\d+)?)",
        r"arXiv[:\s]*([a-z\-]+/\d{7}(?:v\d+)?)",
    ]
    for field in ("journal", "eprint", "url", "note", "archiveprefix"):
        val = entry.get(field, "")
        for pat in patterns:
            m = re.search(pat, val, re.IGNORECASE)
            if m:
                return m.group(1)
    eprint = entry.get("eprint", "").strip()
    if re.match(r"\d{4}\.\d{4,5}", eprint):
        return eprint
    return None


def parse_bib(path: str) -> list[dict]:
    """Parse .bib file and return list of standardized entries."""
    text = Path(path).read_text(encoding="utf-8")
    parser = BibTexParser(common_strings=True)
    parser.customization = convert_to_unicode
    bib_db = bibtexparser.loads(text, parser=parser)
    entries = []
    for e in bib_db.entries:
        entry = {
            "key": e.get("ID", ""),
            "type": e.get("ENTRYTYPE", ""),
            "title": strip_latex(e.get("title", "")),
            "title_raw": e.get("title", ""),
            "author": e.get("author", ""),
            "author_clean": strip_latex(e.get("author", "")),
            "year": e.get("year", ""),
            "journal": e.get("journal", ""),
            "booktitle": e.get("booktitle", ""),
            "volume": e.get("volume", ""),
            "pages": e.get("pages", ""),
            "doi": e.get("doi", ""),
            "url": e.get("url", ""),
            "arxiv_id": extract_arxiv_id(e),
            "_raw": e,
        }
        entry["venue"] = entry["booktitle"] or entry["journal"]
        entries.append(entry)
    return entries
