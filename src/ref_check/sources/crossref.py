"""Crossref API source."""

from __future__ import annotations

from typing import Optional

import requests

from ._common import HEADERS, rate_limit


def query_crossref(doi: str) -> Optional[dict]:
    """Query Crossref API by DOI."""
    rate_limit("crossref")
    url = f"https://api.crossref.org/works/{doi}"
    try:
        r = requests.get(url, headers={**HEADERS, "Accept": "application/json"}, timeout=15)
        r.raise_for_status()
        data = r.json()["message"]
    except (requests.RequestException, KeyError, ValueError):
        return None

    title = data.get("title", [""])[0]
    authors = []
    for a in data.get("author", []):
        name = f"{a.get('given', '')} {a.get('family', '')}".strip()
        if name:
            authors.append(name)
    year = None
    for date_field in ("published-print", "published-online", "created"):
        if date_field in data:
            parts = data[date_field].get("date-parts", [[]])[0]
            if parts:
                year = str(parts[0])
                break
    venue = ""
    for v in data.get("container-title", []):
        if v:
            venue = v
            break
    is_retracted = "retracted-article" in [
        u.get("type", "") for u in data.get("update-to", [])
    ]

    return {
        "source": "crossref",
        "title": title,
        "authors": authors,
        "year": year,
        "venue": venue,
        "doi": doi,
        "is_retracted": is_retracted,
    }
