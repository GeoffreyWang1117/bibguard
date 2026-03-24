"""arXiv API source."""

from __future__ import annotations

import re
from typing import Optional

import requests

from ._common import HEADERS, rate_limit


def query_arxiv(arxiv_id: str) -> Optional[dict]:
    """Query arXiv API by paper ID."""
    rate_limit("arxiv")
    url = f"http://export.arxiv.org/api/query?id_list={arxiv_id}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
    except requests.RequestException:
        return None

    text = r.text
    titles = re.findall(r"<title[^>]*>(.*?)</title>", text, re.DOTALL)
    if len(titles) < 2:
        return None
    title = re.sub(r"\s+", " ", titles[1]).strip()
    if title.lower().startswith("error"):
        return None

    authors = re.findall(r"<name>(.*?)</name>", text)
    published = re.search(r"<published>(.*?)</published>", text)
    year = published.group(1)[:4] if published else None

    return {
        "source": "arxiv",
        "title": title,
        "authors": authors,
        "year": year,
        "arxiv_id": arxiv_id,
    }
