"""Duplicate entry detection."""

from __future__ import annotations

from bibguard.matching import token_similarity


def detect_duplicates(entries: list[dict]) -> list[dict]:
    """Detect potential duplicate entries (different keys, same paper)."""
    issues = []
    for i, a in enumerate(entries):
        for b in entries[i + 1:]:
            score = token_similarity(a["title"], b["title"])
            if score >= 0.85:
                issues.append({
                    "type": "WARN",
                    "category": "duplicate",
                    "key": f"{a['key']} / {b['key']}",
                    "message": f"Possible duplicate: '{a['key']}' and '{b['key']}' "
                               f"(title similarity {score:.2f})",
                })
    return issues
