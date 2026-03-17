"""
Self-consistency confidence scoring for CroissantMiner extractions.

Runs extraction multiple times with slight stochasticity and measures
inter-run agreement to estimate confidence per field.
"""

import re
from typing import Dict, List, Optional
from difflib import SequenceMatcher


def _normalize_for_comparison(value):
    """Normalize a value for agreement comparison."""
    if value is None:
        return None
    s = str(value).strip().lower()
    if s in ("null", "none", "", "not mentioned", "n/a", "not applicable"):
        return None
    # Strip whitespace, punctuation for fuzzy comparison
    s = re.sub(r'\s+', ' ', s)
    return s


def _values_agree(v1, v2, threshold=0.8):
    """Check if two values agree (exact or fuzzy match)."""
    n1 = _normalize_for_comparison(v1)
    n2 = _normalize_for_comparison(v2)

    # Both null = agree
    if n1 is None and n2 is None:
        return True
    # One null = disagree
    if n1 is None or n2 is None:
        return False
    # Exact match
    if n1 == n2:
        return True
    # Fuzzy match for longer text
    if len(n1) > 20 or len(n2) > 20:
        ratio = SequenceMatcher(None, n1, n2).ratio()
        return ratio >= threshold
    # Short text: stricter
    return n1 == n2


def _validate_url(value):
    """Check if value looks like a real URL."""
    if not value:
        return True  # null is valid (field absent)
    s = str(value).strip()
    if re.match(r'^https?://[a-zA-Z0-9]', s):
        # Check for obviously fake patterns
        if 'example.com' in s or 'placeholder' in s:
            return False
        return True
    return False


def _validate_license(value):
    """Check if value is a known license string."""
    if not value:
        return True
    s = str(value).strip().lower()
    known = [
        'cc', 'creative commons', 'mit', 'apache', 'gpl', 'bsd',
        'public domain', 'cc0', 'unknown', 'custom', 'proprietary',
        'open', 'free', 'research', 'academic',
    ]
    return any(k in s for k in known)


def _validate_date(value):
    """Check if value looks like a valid date."""
    if not value:
        return True
    s = str(value).strip()
    # Year only
    if re.match(r'^(19|20)\d{2}$', s):
        return True
    # Full date
    if re.match(r'^(19|20)\d{2}[-/](0[1-9]|1[0-2])[-/](0[1-9]|[12]\d|3[01])$', s):
        return True
    # Month Year
    if re.search(r'(19|20)\d{2}', s):
        return True
    return False


def compute_field_confidence(
    extractions: List[Dict],
    field_name: str,
) -> Dict:
    """Compute confidence for a single field across multiple extraction runs.

    Args:
        extractions: list of extraction dicts (one per run)
        field_name: which field to score

    Returns:
        dict with value, confidence, agreement level, and flag
    """
    # Get values for this field from each run
    short = field_name.split(":")[-1] if ":" in field_name else field_name
    values = []
    for ext in extractions:
        v = ext.get(field_name) or ext.get(short) or ext.get(f"rai:{short}")
        values.append(v)

    n = len(values)
    normalized = [_normalize_for_comparison(v) for v in values]

    # Count nulls
    null_count = sum(1 for v in normalized if v is None)

    # All null = confident null
    if null_count == n:
        return {
            "field": field_name,
            "value": None,
            "confidence": 0.95,
            "agreement": "high",
            "flag": "confident_null",
            "raw_values": [str(v)[:50] if v else "null" for v in values],
        }

    # Count pairwise agreements
    agreements = 0
    total_pairs = 0
    for i in range(n):
        for j in range(i + 1, n):
            total_pairs += 1
            if _values_agree(values[i], values[j]):
                agreements += 1

    agreement_ratio = agreements / total_pairs if total_pairs > 0 else 0

    # Pick best value (majority vote)
    # Group values by agreement clusters
    non_null_values = [(i, v) for i, v in enumerate(values) if normalized[i] is not None]
    if non_null_values:
        # Use first non-null as candidate, check if others agree
        best_value = non_null_values[0][1]
        # If 2+ agree, use their value
        for i, v in non_null_values:
            agree_count = sum(1 for j, v2 in non_null_values if _values_agree(v, v2))
            if agree_count > len(non_null_values) // 2:
                best_value = v
                break
    else:
        best_value = None

    # Compute confidence score
    if agreement_ratio >= 0.9:
        confidence = 0.9 + (agreement_ratio - 0.9)
        agreement_level = "high"
    elif agreement_ratio >= 0.5:
        confidence = 0.5 + (agreement_ratio - 0.5) * 0.8
        agreement_level = "medium"
    else:
        confidence = agreement_ratio * 0.5
        agreement_level = "low"

    # Validation checks for constrained fields
    flag = "none"
    if field_name in ("sc:url", "url"):
        if not _validate_url(best_value):
            flag = "likely_hallucination"
            confidence *= 0.5
    elif field_name in ("sc:license", "license"):
        if not _validate_license(best_value):
            flag = "likely_hallucination"
            confidence *= 0.5
    elif field_name in ("sc:datePublished", "datePublished"):
        if not _validate_date(best_value):
            flag = "likely_hallucination"
            confidence *= 0.5

    # Low agreement → uncertain
    if agreement_level == "low" and flag == "none":
        flag = "uncertain"

    return {
        "field": field_name,
        "value": best_value,
        "confidence": round(min(confidence, 1.0), 3),
        "agreement": agreement_level,
        "flag": flag,
        "raw_values": [str(v)[:80] if v else "null" for v in values],
    }


def compute_all_confidences(
    extractions: List[Dict],
    fields: List[str],
) -> Dict[str, Dict]:
    """Compute confidence for all fields."""
    results = {}
    for field in fields:
        results[field] = compute_field_confidence(extractions, field)
    return results
