"""OpenAlex API source -- covers all disciplines including old/non-CS papers."""

from __future__ import annotations

from typing import Optional

import requests

from ._common import HEADERS, rate_limit
from ref_check.matching import token_similarity, extract_first_surname


def query_openalex(title: str, bib_first_author: str = "") -> Optional[dict]:
    """Query OpenAlex API by title."""
    rate_limit("openalex")
    url = "https://api.openalex.org/works"
    params = {
        "search": title,
        "per_page": 5,
        "mailto": "ref-check@example.com",
    }
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
    except (requests.RequestException, ValueError):
        return None

    results = data.get("results", [])
    if not results:
        return None

    bib_surname = extract_first_surname(bib_first_author) if bib_first_author else ""

    candidates = []
    for work in results:
        work_title = work.get("title", "") or ""
        title_score = token_similarity(title, work_title)
        if title_score < 0.6:
            continue

        authors = []
        for a in work.get("authorships", []):
            name = a.get("author", {}).get("display_name", "")
            if name:
                authors.append(name)

        author_bonus = 0
        if bib_surname and authors:
            api_surname = authors[0].split()[-1].lower() if authors[0].split() else ""
            if api_surname == bib_surname:
                author_bonus = 0.3

        candidates.append((title_score + author_bonus, work, authors))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0], reverse=True)
    best_score, best, authors = candidates[0]
    if best_score < 0.6:
        return None

    year = str(best["publication_year"]) if best.get("publication_year") else None
    primary_loc = best.get("primary_location", {}) or {}
    source = primary_loc.get("source", {}) or {}
    venue = source.get("display_name", "")

    doi = best.get("doi", "")
    if doi and doi.startswith("https://doi.org/"):
        doi = doi[len("https://doi.org/"):]

    return {
        "source": "openalex",
        "title": best.get("title", ""),
        "authors": authors,
        "year": year,
        "venue": venue,
        "doi": doi,
        "cited_by_count": best.get("cited_by_count"),
        "is_retracted": best.get("is_retracted", False),
    }
