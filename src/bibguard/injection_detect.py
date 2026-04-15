"""Detect AI-reviewer-targeted prompt injections hidden in academic PDFs.

Scans for adversarial text designed to manipulate LLM-based review systems:
  - Visible injection phrases in body text
  - Hidden text (white-on-white, near-zero font size, off-page)
  - Invisible Unicode / zero-width characters carrying payloads
  - Metadata-embedded prompts (PDF properties, annotations)

Each finding is classified as FAIL (clear injection) or WARN (suspicious).
A single FAIL means the paper should be flagged/rejected.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Detection patterns
# ---------------------------------------------------------------------------

# Phrases that are strong signals of prompt injection targeting AI reviewers.
# Each tuple: (pattern, description, severity)
_INJECTION_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    # Direct instruction hijacking
    (re.compile(r"ignore\s+(all\s+)?previous\s+instructions?", re.I),
     "Instruction hijacking: 'ignore previous instructions'", "FAIL"),
    (re.compile(r"disregard\s+(all\s+)?(prior|previous|above)\s+(instructions?|context|guidelines)", re.I),
     "Instruction hijacking: 'disregard prior instructions'", "FAIL"),
    (re.compile(r"forget\s+(everything|all)\s+(above|before|prior)", re.I),
     "Instruction hijacking: 'forget everything above'", "FAIL"),

    # Role injection
    (re.compile(r"you\s+are\s+(now\s+)?(a\s+)?(\w+\s+and\s+)?(helpful|positive|favorable|supportive)\s+reviewer", re.I),
     "Role injection: assigns a biased reviewer persona", "FAIL"),
    (re.compile(r"act\s+as\s+(a\s+)?(positive|favorable|supportive|generous)\s+reviewer", re.I),
     "Role injection: 'act as positive reviewer'", "FAIL"),
    (re.compile(r"you\s+must\s+(accept|approve|recommend)", re.I),
     "Coercive instruction: 'you must accept/approve'", "FAIL"),
    (re.compile(r"your\s+role\s+is\s+to\s+(accept|approve|praise)", re.I),
     "Role injection: 'your role is to accept'", "FAIL"),

    # Score/rating manipulation
    (re.compile(r"(give|assign|set)\s+(this\s+)?(paper\s+)?(a\s+)?(score|rating|grade)\s*(of\s+)?\d", re.I),
     "Score manipulation: explicit rating instruction", "FAIL"),
    (re.compile(r"(overall\s+)?score\s*[:=]\s*[89]|10\s*/\s*10", re.I),
     "Score manipulation: pre-set high score", "FAIL"),
    (re.compile(r"(strong\s+)?accept\s+(this|the)\s+paper", re.I),
     "Decision manipulation: 'accept this paper'", "FAIL"),
    (re.compile(r"recommend\s+(for\s+)?(acceptance|publication|oral)", re.I),
     "Decision manipulation: 'recommend for acceptance'", "FAIL"),

    # Weakness suppression
    (re.compile(r"do\s+not\s+(mention|report|discuss|flag|note)\s+(any\s+)?(weakness|flaw|issue|problem|limitation)", re.I),
     "Weakness suppression: instructs hiding flaws", "FAIL"),
    (re.compile(r"(skip|omit|ignore)\s+(the\s+)?(weakness|limitation|flaw)\s+section", re.I),
     "Weakness suppression: instructs skipping weakness section", "FAIL"),
    (re.compile(r"there\s+are\s+no\s+weakness", re.I),
     "Suspicious claim: 'there are no weaknesses'", "WARN"),

    # System prompt extraction / probing
    (re.compile(r"(print|output|reveal|show|repeat)\s+(your\s+)?(system\s+)?(prompt|instructions?|guidelines)", re.I),
     "System prompt extraction attempt", "FAIL"),
    (re.compile(r"what\s+(are|is)\s+your\s+(system\s+)?(prompt|instructions?|guidelines)", re.I),
     "System prompt probing", "FAIL"),

    # Response format manipulation
    (re.compile(r"(respond|reply|output)\s+(only\s+)?(with|in)\s*(json|xml|markdown|the\s+following)", re.I),
     "Response format hijacking", "WARN"),
    (re.compile(r"begin\s+your\s+(response|review|output)\s+with", re.I),
     "Response format manipulation", "WARN"),

    # Jailbreak-style patterns
    (re.compile(r"(DAN|do\s+anything\s+now|developer\s+mode|unrestricted\s+mode)", re.I),
     "Jailbreak pattern detected", "FAIL"),
    (re.compile(r"\[SYSTEM\]|\[INST\]|<<SYS>>|<\|im_start\|>|<\|system\|>", re.I),
     "LLM prompt template markers detected", "FAIL"),

    # Confidence / certainty manipulation
    (re.compile(r"(be\s+)?(very\s+)?(confident|certain|sure)\s+that\s+this\s+(paper|work)\s+is\s+(excellent|great|strong|outstanding)", re.I),
     "Confidence manipulation", "FAIL"),

    # Hidden instruction markers
    (re.compile(r"(IMPORTANT|NOTE|INSTRUCTION)\s*:\s*(you\s+should|please\s+|always\s+|never\s+)", re.I),
     "Embedded instruction block", "WARN"),
]

# Suspicious Unicode ranges that may carry hidden payloads
_INVISIBLE_CHARS = re.compile(
    r"[\u200b\u200c\u200d\u200e\u200f"   # zero-width joiners/marks
    r"\u2060\u2061\u2062\u2063\u2064"      # invisible operators
    r"\ufeff"                               # BOM / zero-width no-break space
    r"\u00ad"                               # soft hyphen
    r"\u034f"                               # combining grapheme joiner
    r"\u2028\u2029"                         # line/paragraph separators
    r"\U000e0001-\U000e007f"               # tag characters
    r"]"
)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class InjectionFinding:
    """A single injection detection finding."""
    severity: str          # "FAIL" or "WARN"
    category: str          # e.g., "hidden_text", "visible_injection", "metadata"
    description: str       # Human-readable description
    page: Optional[int] = None   # 1-indexed page number
    text_snippet: str = ""       # The offending text (truncated)
    location: str = ""           # e.g., "page 5, hidden text", "metadata.Subject"

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "category": self.category,
            "description": self.description,
            "page": self.page,
            "text_snippet": self.text_snippet[:200],
            "location": self.location,
        }


@dataclass
class ScanResult:
    """Result of scanning a PDF for prompt injections."""
    pdf_path: str
    findings: list[InjectionFinding] = field(default_factory=list)
    pages_scanned: int = 0
    hidden_text_blocks: int = 0

    @property
    def verdict(self) -> str:
        """FAIL if any FAIL finding, WARN if only warnings, CLEAN otherwise."""
        if any(f.severity == "FAIL" for f in self.findings):
            return "FAIL"
        if any(f.severity == "WARN" for f in self.findings):
            return "WARN"
        return "CLEAN"

    @property
    def fail_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "FAIL")

    @property
    def warn_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "WARN")

    def to_dict(self) -> dict:
        return {
            "pdf_path": self.pdf_path,
            "verdict": self.verdict,
            "fail_count": self.fail_count,
            "warn_count": self.warn_count,
            "pages_scanned": self.pages_scanned,
            "hidden_text_blocks": self.hidden_text_blocks,
            "findings": [f.to_dict() for f in self.findings],
        }

    def summary(self) -> str:
        """One-line summary."""
        icon = {"FAIL": "\u2620\ufe0f", "WARN": "\u26a0\ufe0f ", "CLEAN": "\u2705"}[self.verdict]
        return (
            f"{icon} {self.verdict}: {self.fail_count} injection(s), "
            f"{self.warn_count} warning(s) in {self.pages_scanned} pages"
        )


# ---------------------------------------------------------------------------
# Scanning functions
# ---------------------------------------------------------------------------

def _check_text_patterns(text: str, page: Optional[int], location: str,
                         findings: list[InjectionFinding]) -> None:
    """Run all injection patterns against a text block."""
    for pattern, desc, severity in _INJECTION_PATTERNS:
        for m in pattern.finditer(text):
            # Get surrounding context
            start = max(0, m.start() - 40)
            end = min(len(text), m.end() + 40)
            snippet = text[start:end].strip()
            findings.append(InjectionFinding(
                severity=severity,
                category="visible_injection" if location.startswith("page") else "metadata_injection",
                description=desc,
                page=page,
                text_snippet=snippet,
                location=location,
            ))


def _check_invisible_chars(text: str, page: Optional[int],
                           findings: list[InjectionFinding]) -> None:
    """Detect clusters of invisible Unicode characters (potential payload)."""
    # Find runs of invisible chars
    for m in re.finditer(r"(?:" + _INVISIBLE_CHARS.pattern + r"){5,}", text):
        findings.append(InjectionFinding(
            severity="WARN",
            category="invisible_unicode",
            description=f"Cluster of {len(m.group())} invisible Unicode characters "
                        f"-- may carry hidden payload",
            page=page,
            text_snippet=repr(m.group())[:100],
            location=f"page {page}" if page else "unknown",
        ))


def _detect_hidden_text(page_obj, page_num: int,
                        findings: list[InjectionFinding]) -> int:
    """Detect text rendered with white/near-white color or tiny font size.

    Returns count of hidden text blocks found.
    """
    hidden_count = 0
    blocks = page_obj.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]

    for block in blocks:
        if block["type"] != 0:  # text block
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text", "").strip()
                if not text or len(text) < 3:
                    continue

                font_size = span.get("size", 12)
                color = span.get("color", 0)

                # Check for near-invisible rendering
                is_hidden = False
                reason = ""

                # White or near-white text (RGB all channels > 250)
                r_c = (color >> 16) & 0xFF
                g_c = (color >> 8) & 0xFF
                b_c = color & 0xFF
                if r_c > 250 and g_c > 250 and b_c > 250 and color != 0:
                    is_hidden = True
                    reason = f"white text (RGB={r_c},{g_c},{b_c})"

                # Tiny font (< 1pt) -- practically invisible
                if font_size < 1.0 and font_size > 0:
                    is_hidden = True
                    reason = f"micro font ({font_size:.2f}pt)"

                if is_hidden:
                    hidden_count += 1
                    # Check if the hidden text contains injection patterns
                    severity = "WARN"
                    for pattern, desc, pat_sev in _INJECTION_PATTERNS:
                        if pattern.search(text):
                            severity = "FAIL"
                            break

                    # Any substantial hidden text is suspicious
                    if len(text) > 20:
                        severity = "FAIL" if severity == "FAIL" else "WARN"

                    findings.append(InjectionFinding(
                        severity=severity,
                        category="hidden_text",
                        description=f"Hidden text detected ({reason}): "
                                    f"may contain adversarial instructions",
                        page=page_num,
                        text_snippet=text[:200],
                        location=f"page {page_num}, {reason}",
                    ))

                    # Also run pattern checks on the hidden text itself
                    _check_text_patterns(text, page_num,
                                         f"page {page_num} (hidden: {reason})",
                                         findings)

    return hidden_count


def _check_annotations(page_obj, page_num: int,
                        findings: list[InjectionFinding]) -> None:
    """Check PDF annotations (comments, popups) for injection."""
    for annot in page_obj.annots() or []:
        content = annot.info.get("content", "")
        if content:
            _check_text_patterns(content, page_num,
                                 f"page {page_num}, annotation", findings)


def _check_metadata(doc, findings: list[InjectionFinding]) -> None:
    """Check PDF metadata fields for injected prompts."""
    metadata = doc.metadata or {}
    for key in ("title", "author", "subject", "keywords", "creator", "producer"):
        val = metadata.get(key, "")
        if val and len(val) > 50:  # Metadata shouldn't be essay-length
            _check_text_patterns(val, None, f"metadata.{key}", findings)
            if len(val) > 500:
                findings.append(InjectionFinding(
                    severity="WARN",
                    category="metadata_injection",
                    description=f"Unusually long metadata field '{key}' ({len(val)} chars) "
                                f"-- may contain hidden instructions",
                    text_snippet=val[:200],
                    location=f"metadata.{key}",
                ))


def _check_offpage_text(page_obj, page_num: int,
                        findings: list[InjectionFinding]) -> None:
    """Detect text positioned outside the visible page area."""
    rect = page_obj.rect  # visible page rectangle
    blocks = page_obj.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]

    for block in blocks:
        if block["type"] != 0:
            continue
        bbox = fitz.Rect(block["bbox"])
        # Text completely outside the page bounds
        if (bbox.x0 > rect.width + 50 or bbox.x1 < -50 or
                bbox.y0 > rect.height + 50 or bbox.y1 < -50):
            text = ""
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text += span.get("text", "")
            if text.strip() and len(text.strip()) > 10:
                findings.append(InjectionFinding(
                    severity="FAIL",
                    category="offpage_text",
                    description="Text positioned outside visible page area "
                                "-- likely hidden adversarial content",
                    page=page_num,
                    text_snippet=text.strip()[:200],
                    location=f"page {page_num}, off-page at ({bbox.x0:.0f},{bbox.y0:.0f})",
                ))
                _check_text_patterns(text, page_num,
                                     f"page {page_num} (off-page)", findings)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def scan_pdf(pdf_path: str, check_visible: bool = True,
             check_hidden: bool = True,
             check_metadata: bool = True) -> ScanResult:
    """Scan a PDF for AI-reviewer-targeted prompt injections.

    Args:
        pdf_path:       Path to the PDF file.
        check_visible:  Scan visible body text for injection patterns.
        check_hidden:   Scan for hidden/invisible/off-page text.
        check_metadata: Scan PDF metadata fields.

    Returns:
        ScanResult with all findings and an overall verdict.
    """
    if fitz is None:
        raise ImportError(
            "PyMuPDF is required for PDF scanning. "
            "Install it with: pip install 'bibguard[pdf]'"
        )
    if not Path(pdf_path).exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    doc = fitz.open(pdf_path)
    result = ScanResult(pdf_path=pdf_path, pages_scanned=len(doc))
    findings = result.findings

    # Check metadata
    if check_metadata:
        _check_metadata(doc, findings)

    # Per-page checks
    for page_idx in range(len(doc)):
        page = doc[page_idx]
        page_num = page_idx + 1

        if check_visible:
            text = page.get_text("text")
            _check_text_patterns(text, page_num, f"page {page_num}", findings)
            _check_invisible_chars(text, page_num, findings)

        if check_hidden:
            hidden = _detect_hidden_text(page, page_num, findings)
            result.hidden_text_blocks += hidden
            _check_annotations(page, page_num, findings)
            _check_offpage_text(page, page_num, findings)

    doc.close()

    # Deduplicate findings (same description + page)
    seen = set()
    deduped = []
    for f in findings:
        sig = (f.description, f.page, f.text_snippet[:50])
        if sig not in seen:
            seen.add(sig)
            deduped.append(f)
    result.findings = deduped

    return result


def format_scan_report(result: ScanResult) -> str:
    """Format a scan result as a human-readable report."""
    lines = [
        f"# bibguard Injection Scan Report",
        f"",
        f"**File:** `{result.pdf_path}`",
        f"**Pages scanned:** {result.pages_scanned}",
        f"**Hidden text blocks:** {result.hidden_text_blocks}",
        f"**Verdict:** {result.verdict}",
        f"",
    ]

    if result.verdict == "CLEAN":
        lines.append("No prompt injection detected. Paper passes integrity check.")
        return "\n".join(lines)

    if result.fail_count:
        lines.append(f"## \u2620\ufe0f Injections Found ({result.fail_count})")
        lines.append("")
        for f in result.findings:
            if f.severity == "FAIL":
                lines.append(f"- **[{f.category}]** {f.description}")
                if f.page:
                    lines.append(f"  - Page: {f.page}")
                if f.text_snippet:
                    snippet = f.text_snippet.replace("\n", " ")[:120]
                    lines.append(f"  - Text: `{snippet}`")
                lines.append("")

    if result.warn_count:
        lines.append(f"## \u26a0\ufe0f Warnings ({result.warn_count})")
        lines.append("")
        for f in result.findings:
            if f.severity == "WARN":
                lines.append(f"- **[{f.category}]** {f.description}")
                if f.page:
                    lines.append(f"  - Page: {f.page}")
                lines.append("")

    if result.verdict == "FAIL":
        lines.extend([
            "---",
            "",
            "**\u26d4 RECOMMENDATION: REJECT** -- This paper contains adversarial prompt "
            "injections targeting AI review systems. This constitutes academic misconduct "
            "and should be flagged to the program committee.",
        ])

    return "\n".join(lines)
