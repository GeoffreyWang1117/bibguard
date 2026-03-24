"""Semantic Scholar API source."""

from __future__ import annotations

from typing import Optional

import requests

from ._common import HEADERS, rate_limit
from bibguard.matching import token_similarity, extract_first_surname


def query_s2(title: str, bib_first_author: str = "") -> Optional[dict]:
    """Query Semantic Scholar API by title."""
    rate_limit("s2")
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        "query": title,
        "limit": 10,
        "fields": "title,authors,year,venue,citationCount,isOpenAccess,externalIds",
    }
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
    except (requests.RequestException, ValueError):
        return None

    papers = data.get("data", [])
    if not papers:
        return None

    bib_surname = extract_first_surname(bib_first_author) if bib_first_author else ""

    candidates = []
    for p in papers:
        title_score = token_similarity(title, p.get("title", ""))
        if title_score < 0.6:
            continue
        author_bonus = 0
        p_authors = [a.get("name", "") for a in p.get("authors", [])]
        if bib_surname and p_authors:
            api_surname = p_authors[0].split()[-1].lower() if p_authors[0].split() else ""
            if api_surname == bib_surname:
                author_bonus = 0.3
        candidates.append((title_score + author_bonus, p))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0], reverse=True)
    best_score, best = candidates[0]
    if best_score < 0.6:
        return None

    authors = [a.get("name", "") for a in best.get("authors", [])]
    ext_ids = best.get("externalIds", {}) or {}

    return {
        "source": "s2",
        "title": best.get("title", ""),
        "authors": authors,
        "year": str(best["year"]) if best.get("year") else None,
        "venue": best.get("venue", ""),
        "citation_count": best.get("citationCount"),
        "doi": ext_ids.get("DOI"),
        "arxiv_id": ext_ids.get("ArXiv"),
        "s2_id": best.get("paperId"),
    }
