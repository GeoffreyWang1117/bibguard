"""TeX cross-audit: find phantom references and orphan bib entries."""

from __future__ import annotations

import re
from pathlib import Path


def _read_tex_with_includes(tex_path: str) -> str:
    """Read a .tex file and recursively resolve \\input{} and \\include{}."""
    p = Path(tex_path)
    if not p.exists():
        return ""
    text = p.read_text(encoding="utf-8")
    base_dir = p.parent

    def _resolve(m: re.Match) -> str:
        inc_path = m.group(1).strip()
        if not inc_path.endswith(".tex"):
            inc_path += ".tex"
        full = base_dir / inc_path
        if full.exists():
            return full.read_text(encoding="utf-8")
        return m.group(0)

    text = re.sub(r"\\(?:input|include)\{([^}]+)\}", _resolve, text)
    return text


def audit_tex_bib(tex_path: str, bib_entries: list[dict]) -> list[dict]:
    """Cross-audit .tex citations against .bib entries.

    Returns list of issues, each with type/category/key/message.
    """
    text = _read_tex_with_includes(tex_path)
    # Remove comments
    text = re.sub(r"(?<!\\)%.*", "", text)

    # Find all \\cite variants
    cite_pattern = (
        r"\\(?:cite[tp]?|citealp|citeauthor|citeyear|Cite[tp]?)\*?"
        r"\s*(?:\[[^\]]*\]\s*)*\{([^}]+)\}"
    )
    cited_keys: set[str] = set()
    for m in re.finditer(cite_pattern, text):
        for k in m.group(1).split(","):
            k = k.strip()
            if k:
                cited_keys.add(k)

    bib_keys = {e["key"] for e in bib_entries}
    issues = []

    for k in sorted(cited_keys - bib_keys):
        issues.append({
            "type": "FAIL",
            "category": "phantom_ref",
            "key": k,
            "message": f"Phantom reference: \\cite{{{k}}} used in .tex but not defined in .bib",
        })

    for k in sorted(bib_keys - cited_keys):
        issues.append({
            "type": "WARN",
            "category": "orphan_entry",
            "key": k,
            "message": f"Orphan entry: '{k}' defined in .bib but never cited in .tex",
        })

    return issues
