"""DBLP API source -- gold standard for CS papers."""

from __future__ import annotations

import re
from typing import Optional

import requests

from ._common import HEADERS, rate_limit
from bibguard.matching import token_similarity, extract_first_surname


def _clean_dblp_author(name: str) -> str:
    return re.sub(r"\s+\d{4}$", "", name).strip()


def query_dblp(title: str, bib_first_author: str = "") -> Optional[dict]:
    """Query DBLP API by title with author disambiguation."""
    rate_limit("dblp")
    url = "https://dblp.org/search/publ/api"
    params = {"q": title, "format": "json", "h": 10}
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
    except (requests.RequestException, ValueError):
        return None

    hits = data.get("result", {}).get("hits", {}).get("hit", [])
    if not hits:
        return None

    bib_surname = extract_first_surname(bib_first_author) if bib_first_author else ""

    candidates = []
    for hit in hits:
        info = hit.get("info", {})
        hit_title = info.get("title", "").rstrip(".")
        title_score = token_similarity(title, hit_title)
        if title_score < 0.6:
            continue

        authors_data = info.get("authors", {}).get("author", [])
        if isinstance(authors_data, dict):
            authors_data = [authors_data]
        authors = [
            _clean_dblp_author(a.get("text", a) if isinstance(a, dict) else str(a))
            for a in authors_data
        ]

        author_bonus = 0
        if bib_surname and authors:
            api_surname = authors[0].split()[-1].lower() if authors[0].split() else ""
            if api_surname == bib_surname:
                author_bonus = 0.3

        candidates.append((title_score + author_bonus, info, authors))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0], reverse=True)
    best_score, best, authors = candidates[0]
    if best_score < 0.6:
        return None

    venue = best.get("venue", "")
    if isinstance(venue, list):
        venue = venue[0] if venue else ""

    return {
        "source": "dblp",
        "title": best.get("title", "").rstrip("."),
        "authors": authors,
        "year": best.get("year"),
        "venue": venue,
        "pages": best.get("pages", ""),
        "doi": best.get("doi", ""),
        "url": best.get("ee", ""),
    }
