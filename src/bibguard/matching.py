"""Field comparison utilities -- title, author, year, venue matching.

Uses RapidFuzz when available for higher precision, falls back to
Jaccard token similarity.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Optional

try:
    from rapidfuzz import fuzz as _rf
    HAS_RAPIDFUZZ = True
except ImportError:
    _rf = None  # type: ignore[assignment]
    HAS_RAPIDFUZZ = False

# ---------------------------------------------------------------------------
# LaTeX handling
# ---------------------------------------------------------------------------

_LATEX_ACCENTS = {
    "`": "\u0300", "'": "\u0301", "^": "\u0302", "~": "\u0303",
    "=": "\u0304", ".": "\u0307", '"': "\u0308", "v": "\u030C",
    "c": "\u0327", "u": "\u0306",
}


def strip_latex(s: str) -> str:
    """Remove LaTeX markup, returning plain Unicode text."""
    if not s:
        return ""
    s = re.sub(r"\\text\w+\{([^}]*)\}", r"\1", s)

    def _accent_repl(m: re.Match) -> str:
        cmd, char = m.group(1), m.group(2)
        combining = _LATEX_ACCENTS.get(cmd, "")
        base = char.strip("{}")
        if combining and base:
            return unicodedata.normalize("NFC", base + combining)
        return base

    s = re.sub(r"\\([`'^~\"=.vc])\{(\w)\}", _accent_repl, s)
    s = re.sub(r"\\([`'^~\"=.vc])(\w)", _accent_repl, s)
    s = re.sub(r"\\(\W)", r"\1", s)
    s = re.sub(r"\\[a-zA-Z]+\s*", "", s)
    s = s.replace("{", "").replace("}", "").replace("$", "")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def strip_accents(s: str) -> str:
    """Strip all accents/diacritics for fuzzy comparison."""
    s = unicodedata.normalize("NFKD", s)
    s = s.replace("\u0131", "i")  # dotless i
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower()


# ---------------------------------------------------------------------------
# Tokenization & similarity
# ---------------------------------------------------------------------------

def _tokenize(s: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", s.lower()))


def token_similarity(a: str, b: str) -> float:
    """Token-level Jaccard similarity after LaTeX stripping."""
    ta, tb = _tokenize(strip_latex(a)), _tokenize(strip_latex(b))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def title_similarity(a: str, b: str) -> float:
    """Best-effort title similarity (RapidFuzz token_set_ratio if available)."""
    if HAS_RAPIDFUZZ:
        return _rf.token_set_ratio(strip_latex(a), strip_latex(b)) / 100.0
    return token_similarity(a, b)


# ---------------------------------------------------------------------------
# Field matchers (return (status, detail))
# ---------------------------------------------------------------------------

def extract_first_surname(author_str: str) -> str:
    """Extract first author's surname from a bib author string."""
    clean = strip_latex(author_str)
    parts = re.split(r"\s+and\s+", clean, maxsplit=1)
    first = parts[0].strip()
    if not first:
        return ""
    if "," in first:
        return first.split(",")[0].strip().split()[-1].lower()
    return first.split()[-1].lower()


def match_title(bib_title: str, api_title: str) -> tuple[str, str]:
    score = title_similarity(bib_title, api_title)
    if score >= 0.85:
        return "OK", f"title match ({score:.2f})"
    elif score >= 0.7:
        return "WARN", f"title partial match ({score:.2f}): '{api_title}'"
    else:
        return "FAIL", f"title mismatch ({score:.2f}): bib='{bib_title}' vs api='{api_title}'"


def match_authors(bib_author: str, api_authors: list[str]) -> tuple[str, str]:
    if not api_authors:
        return "WARN", "no authors from API"

    bib_surname = extract_first_surname(bib_author)
    api_first = api_authors[0]
    api_surname = api_first.split()[-1].lower() if api_first.split() else ""

    if not bib_surname or not api_surname:
        return "WARN", "could not extract surnames"

    bib_surname_n = strip_accents(bib_surname)
    api_surname_n = strip_accents(api_surname)
    surname_ok = bib_surname_n == api_surname_n

    bib_clean = strip_latex(bib_author)
    bib_count = len(re.split(r"\s+and\s+", bib_clean))
    api_count = len(api_authors)
    has_others = "others" in bib_clean.lower()
    count_ok = True if has_others else abs(bib_count - api_count) <= 2

    if surname_ok and count_ok:
        return "OK", f"first author '{bib_surname}' matches, count bib={bib_count} api={api_count}"
    elif surname_ok:
        return "WARN", f"first author matches but count differs: bib={bib_count} api={api_count}"
    else:
        return "FAIL", f"first author mismatch: bib='{bib_surname}' api='{api_surname}'"


def match_year(bib_year: str, api_year: Optional[str]) -> tuple[str, str]:
    if not api_year:
        return "WARN", "no year from API"
    try:
        by, ay = int(bib_year), int(api_year)
    except (ValueError, TypeError):
        return "WARN", f"unparseable years: bib={bib_year} api={api_year}"
    diff = abs(by - ay)
    if diff == 0:
        return "OK", f"year exact match ({by})"
    elif diff <= 1:
        return "WARN", f"year off by 1: bib={by} api={ay}"
    elif diff <= 2:
        return "WARN", f"year off by 2: bib={by} api={ay} (preprint vs published?)"
    else:
        return "FAIL", f"year mismatch: bib={by} api={ay}"


# ---------------------------------------------------------------------------
# Venue matching with abbreviation awareness
# ---------------------------------------------------------------------------

_VENUE_ABBREVS = {
    # ML/AI conferences
    "icml": "international conference on machine learning",
    "neurips": "advances in neural information processing systems",
    "nips": "advances in neural information processing systems",
    "iclr": "international conference on learning representations",
    "aaai": "association for the advancement of artificial intelligence",
    "ijcai": "international joint conference on artificial intelligence",
    "jmlr": "journal of machine learning research",
    "jair": "journal of artificial intelligence research",
    "kbs": "knowledge-based systems",
    # Vision
    "cvpr": "computer vision and pattern recognition",
    "iccv": "international conference on computer vision",
    "eccv": "european conference on computer vision",
    # NLP
    "acl": "association for computational linguistics",
    "emnlp": "empirical methods in natural language processing",
    "naacl": "north american chapter of the association for computational linguistics",
    "coling": "international conference on computational linguistics",
    "eacl": "european chapter of the association for computational linguistics",
    # Data mining / IR
    "kdd": "knowledge discovery and data mining",
    "www": "world wide web",
    "sigir": "special interest group on information retrieval",
    "wsdm": "web search and data mining",
    "cikm": "conference on information and knowledge management",
    # Systems
    "osdi": "operating systems design and implementation",
    "sosp": "symposium on operating systems principles",
    "nsdi": "networked systems design and implementation",
    # Robotics
    "iros": "intelligent robots and systems",
    "icra": "international conference on robotics and automation",
    # Science
    "pnas": "proceedings of the national academy of sciences",
    "nature": "nature",
    "science": "science",
    # Scientometrics / Library science
    "jasist": "journal of the association for information science and technology",
    "scientometrics": "scientometrics",
    "qss": "quantitative science studies",
    "jcdl": "joint conference on digital libraries",
    "joi": "journal of informetrics",
}

_DBLP_VENUE_MAP = {
    "j. mach. learn. res.": "journal of machine learning research",
    "nat.": "nature",
    "acm comput. surv.": "acm computing surveys",
    "knowl. inf. syst.": "knowledge and information systems",
    "psychol. bull.": "psychological bulletin",
    "proc. natl. acad. sci.": "proceedings of the national academy of sciences",
    "artif. intell.": "artificial intelligence",
    "j. artif. intell. res.": "journal of artificial intelligence research",
    "mach. learn.": "machine learning",
    "corr": "arxiv",
    "sci. rep.": "scientific reports",
    "inf. process. manag.": "information processing and management",
    "j. assoc. inf. sci. technol.": "journal of the association for information science and technology",
    "j. informetr.": "journal of informetrics",
    "int. j. inf. manag.": "international journal of information management",
    "j. am. soc. inf. sci. technol.": "journal of the american society for information science and technology",
    "account. res.": "accountability in research",
    "learn. publ.": "learned publishing",
}


def _normalize_venue(v: str) -> str:
    v = strip_latex(v).lower().strip()
    for abbrev, full in _DBLP_VENUE_MAP.items():
        if v == abbrev or v.startswith(abbrev):
            return full
    return v


def match_venue(bib_venue: str, api_venue: str) -> tuple[str, str]:
    if not api_venue:
        return "WARN", "no venue from API"
    if not bib_venue:
        return "WARN", "no venue in bib"

    bib_v = _normalize_venue(bib_venue)
    api_v = _normalize_venue(api_venue)

    # arXiv/CoRR
    bib_is_arxiv = "arxiv" in bib_v or "corr" in bib_v
    api_is_arxiv = "arxiv" in api_v or "corr" in api_v
    if bib_is_arxiv and api_is_arxiv:
        return "OK", "venue match (both arXiv/CoRR)"

    score = token_similarity(bib_v, api_v)
    if score >= 0.5:
        return "OK", f"venue match ({score:.2f})"

    for abbrev, full in _VENUE_ABBREVS.items():
        bib_has = abbrev in bib_v or full in bib_v
        api_has = abbrev in api_v or full in api_v
        if bib_has and api_has:
            return "OK", f"venue match via abbreviation '{abbrev}'"

    if bib_v in api_v or api_v in bib_v:
        return "OK", "venue match (substring)"

    return "WARN", f"venue unclear: bib='{bib_venue[:50]}' api='{api_venue[:50]}'"
