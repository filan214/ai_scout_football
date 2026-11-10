"""Report verification: every number in a report must come from its fact sheet."""

from __future__ import annotations

import re

NUMBER_RE = re.compile(r"(?<![\w.,])(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?")
PER_90_RE = re.compile(r"\bper[\s-]*90\b|\bp90\b", re.IGNORECASE)


def extract_numbers(text: str, fact_sheet: dict) -> list[tuple[float, bool]]:
    """Numbers in `text` as (value, is_integer). Digits inside string facts (season '2025-26', club names)
    and the unit 'per 90' are not claims and are removed first."""
    for value in fact_sheet.values():
        if isinstance(value, str) and any(c.isdigit() for c in value):
            text = text.replace(value, " ")
    text = PER_90_RE.sub(" ", text)
    out = []
    for whole, frac in NUMBER_RE.findall(text):
        out.append((float(whole.replace(",", "") + (frac or "")), not frac))
    return out


def number_matches(value: float, is_integer: bool, facts: list[float]) -> bool:
    """Integers must equal a fact exactly; decimals may differ by max(0.05, 2% of the fact)."""
    if is_integer:
        return any(value == f for f in facts)
    return any(abs(value - f) <= max(0.05, 0.02 * abs(f)) for f in facts)


def verify(report: dict, fact_sheet: dict) -> dict:
    """Check one report (summary, strengths, risks) against its fact sheet.

    Returns numbers, verified, verified_rate (1.0 when the text has no numbers), unverified numbers,
    missing_fact_keys (cited keys absent from the fact sheet) and fully_verified.
    """
    facts = [float(v) for v in fact_sheet.values() if isinstance(v, int | float) and not isinstance(v, bool)]
    claims = [*report.get("strengths", []), *report.get("risks", [])]
    texts = [report.get("summary", "")] + [c["text"] for c in claims]
    found = [n for text in texts for n in extract_numbers(text, fact_sheet)]
    unverified = [value for value, is_int in found if not number_matches(value, is_int, facts)]
    missing = sorted({k for c in claims for k in c.get("fact_keys", []) if k not in fact_sheet})
    rate = (len(found) - len(unverified)) / len(found) if found else 1.0
    return {
        "numbers": len(found),
        "verified": len(found) - len(unverified),
        "verified_rate": rate,
        "unverified": unverified,
        "missing_fact_keys": missing,
        "fully_verified": not unverified and not missing,
    }


def aggregate(checks: list[dict]) -> dict:
    """Faithfulness across reports: pooled verified-number rate and report-level counts."""
    numbers = sum(c["numbers"] for c in checks)
    verified = sum(c["verified"] for c in checks)
    return {
        "reports": len(checks),
        "numbers": numbers,
        "verified": verified,
        "verified_rate": verified / numbers if numbers else 1.0,
        "fully_verified_reports": sum(c["fully_verified"] for c in checks),
        "reports_with_missing_keys": sum(bool(c["missing_fact_keys"]) for c in checks),
    }
