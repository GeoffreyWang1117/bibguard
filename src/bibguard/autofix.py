"""Auto-fix .bib files with corrections from verification results."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bibguard.core import VerificationResult


def generate_fixed_bib(bib_path: str, results: list[VerificationResult]) -> str:
    """Generate a fixed .bib file with corrections applied.

    Adds missing DOI and eprint fields based on API results.
    """
    text = Path(bib_path).read_text(encoding="utf-8")

    fixes_by_key = {r.key: r for r in results if r.suggested_fixes}
    if not fixes_by_key:
        return text

    lines = text.split("\n")
    output: list[str] = []
    current_key: str | None = None
    brace_depth = 0

    for line in lines:
        entry_match = re.match(r"@\w+\{(\w+),", line)
        if entry_match:
            current_key = entry_match.group(1)
            brace_depth = 1
            output.append(line)
            continue

        if current_key:
            brace_depth += line.count("{") - line.count("}")
            if brace_depth <= 0:
                if current_key in fixes_by_key:
                    # Ensure trailing comma on last field
                    for j in range(len(output) - 1, -1, -1):
                        prev = output[j].rstrip()
                        if prev and not prev.isspace():
                            if prev[-1] not in (",", "{"):
                                output[j] = prev + ","
                            break
                    r = fixes_by_key[current_key]
                    for field, value in r.suggested_fixes.items():
                        output.append(f'  {field} = {{{value}}},')
                current_key = None

        output.append(line)

    return "\n".join(output)
