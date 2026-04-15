"""Lightweight feedback collector for bibguard.

Saves structured feedback as timestamped JSON files under a local
``feedback/`` directory (next to the .bib file, or in a central location).
Designed for AI agents (Claude Code, Codex) to log issues non-interactively
and for humans to review later.

CLI usage::

    bibguard feedback --issue "phantom DOI not caught" --severity major
    bibguard feedback --show
    bibguard feedback --show --last 5
    bibguard feedback --stats
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

SEVERITY_LEVELS = ("critical", "major", "minor", "suggestion")

# Default storage: ~/.local/share/bibguard/feedback/
_DEFAULT_DIR = Path(os.environ.get(
    "BIBGUARD_FEEDBACK_DIR",
    Path.home() / ".local" / "share" / "bibguard" / "feedback",
))


def _feedback_dir() -> Path:
    d = _DEFAULT_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def log_feedback(
    issue: str,
    severity: str = "minor",
    context: Optional[str] = None,
    tag: Optional[str] = None,
    bib_file: Optional[str] = None,
    expected: Optional[str] = None,
    actual: Optional[str] = None,
) -> Path:
    """Save a feedback entry and return the file path."""
    if severity not in SEVERITY_LEVELS:
        raise ValueError(f"severity must be one of {SEVERITY_LEVELS}, got {severity!r}")

    ts = datetime.now(timezone.utc)
    entry = {
        "timestamp": ts.isoformat(),
        "issue": issue,
        "severity": severity,
        "context": context,
        "tag": tag,
        "bib_file": bib_file,
        "expected": expected,
        "actual": actual,
    }
    # Drop None values
    entry = {k: v for k, v in entry.items() if v is not None}

    filename = f"{ts.strftime('%Y%m%d_%H%M%S')}_{severity}.json"
    path = _feedback_dir() / filename
    path.write_text(json.dumps(entry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def show_feedback(last: Optional[int] = None) -> list[dict]:
    """Read feedback entries, newest first."""
    fb_dir = _feedback_dir()
    files = sorted(fb_dir.glob("*.json"), reverse=True)
    if last:
        files = files[:last]
    entries = []
    for f in files:
        try:
            entries.append(json.loads(f.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return entries


def feedback_stats() -> dict[str, int]:
    """Count feedback entries by severity."""
    fb_dir = _feedback_dir()
    counts: dict[str, int] = {s: 0 for s in SEVERITY_LEVELS}
    counts["total"] = 0
    for f in fb_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            sev = data.get("severity", "minor")
            counts[sev] = counts.get(sev, 0) + 1
            counts["total"] += 1
        except (json.JSONDecodeError, OSError):
            continue
    return counts
