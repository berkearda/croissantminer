"""
Field-type-stratified true label computation.

Determines whether an extraction is Correct (1), Partially Correct (2),
or Incorrect (3) relative to ground truth, using appropriate metrics
per field type.

Constrained fields: normalized exact match + substring/prefix fallback
Short-text fields:  set-based name matching (creator) or token F1 (description)
RAI fields:         token F1 thresholds

This is the single source of truth for true label computation across
all judge experiments.
"""

import re
from typing import Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from evaluation.field_metrics import (
    score_constrained, score_token_f1,
    CONSTRAINED_FIELDS, SHORT_TEXT_FIELDS, LONG_TEXT_RAI_FIELDS,
    _normalize_license, _normalize_language, _normalize_boolean,
    _normalize_url, _extract_year, _names_match,
)

# Thresholds
TOKEN_F1_CORRECT = 0.85
TOKEN_F1_PARTIAL = 0.35

# Field type lookup (handle both prefixed and unprefixed names)
_CONSTRAINED_SHORT = {f.split(":")[-1] for f in CONSTRAINED_FIELDS}
_SHORT_TEXT_SHORT = {f.split(":")[-1] for f in SHORT_TEXT_FIELDS}


def get_field_type(field_name: str) -> str:
    """Return 'constrained', 'short_text', or 'rai' for a field name.

    Handles both prefixed (sc:name, cr:citeAs) and unprefixed (name, citeAs).
    """
    if field_name in CONSTRAINED_FIELDS or field_name in _CONSTRAINED_SHORT:
        return "constrained"
    if field_name in SHORT_TEXT_FIELDS or field_name in _SHORT_TEXT_SHORT:
        return "short_text"
    if field_name in LONG_TEXT_RAI_FIELDS or field_name.startswith("rai:"):
        return "rai"
    # Unprefixed general fields
    if field_name in _CONSTRAINED_SHORT:
        return "constrained"
    if field_name in _SHORT_TEXT_SHORT:
        return "short_text"
    return "rai"  # default for unknown


def _normalize_str(s: str) -> str:
    """Basic normalization: lowercase, strip, collapse whitespace."""
    return re.sub(r'\s+', ' ', s.strip().lower())


def _is_substring_match(a: str, b: str) -> bool:
    """Check if one string is a meaningful substring of the other."""
    a_n = _normalize_str(a)
    b_n = _normalize_str(b)
    if not a_n or not b_n:
        return False
    # One contains the other
    if a_n in b_n or b_n in a_n:
        return True
    # Prefix match (e.g., "2016" is prefix of "2016-02-23")
    if a_n.startswith(b_n) or b_n.startswith(a_n):
        return True
    return False


def _label_constrained(gt: str, ext: str, field: str) -> int:
    """Label a constrained field extraction.

    Returns: 1 (Correct), 2 (Partial), 3 (Incorrect)
    """
    # Try field-specific normalized exact match
    prefixed = field
    if not any(field.startswith(p) for p in ("sc:", "cr:")):
        # Map to prefixed name for score_constrained
        if field in _CONSTRAINED_SHORT:
            for pf in CONSTRAINED_FIELDS:
                if pf.endswith(f":{field}"):
                    prefixed = pf
                    break

    try:
        em = score_constrained(ext, gt, prefixed)
        if em == 1.0:
            # score_constrained uses field-specific normalization (license→SPDX,
            # language→canonical, date→year, etc.) and fuzzy matching for publisher
            # (50% token overlap). For true labels we want to distinguish:
            # - license "MIT" vs "MIT License" → both normalize to "mit" → Correct
            # - publisher "ICLR" vs "ICLR 2021" → 50% token overlap → NOT correct
            #
            # Check: is this a publisher fuzzy match? Publisher is the only field
            # where score_constrained uses token overlap instead of exact normalization.
            if prefixed in ("sc:publisher", "publisher"):
                # Publisher uses 50% token overlap in score_constrained,
                # which is too lenient. "ICLR" matches "ICLR 2021" but year is missing.
                gt_n = _normalize_str(gt)
                ext_n = _normalize_str(ext)
                if gt_n != ext_n:
                    # Extraction is shorter (missing info) → Partial
                    # Extraction is longer (added info) → still Correct if GT is contained
                    if len(ext_n) < len(gt_n):
                        return 2  # Missing information → Partial
            return 1  # Correct (field-specific normalization confirms match)
    except Exception:
        if _normalize_str(ext) == _normalize_str(gt):
            return 1

    # Not exact match — check for partial (substring/prefix)
    if _is_substring_match(gt, ext):
        return 2  # Partially Correct

    # Check if core value is present (e.g., year in date, key word in name)
    gt_words = set(re.findall(r'\w+', gt.lower()))
    ext_words = set(re.findall(r'\w+', ext.lower()))
    if gt_words and ext_words:
        overlap = len(gt_words & ext_words) / max(len(gt_words), 1)
        if overlap > 0.5:
            return 2  # Partially Correct

    return 3  # Incorrect


def _extract_names(text: str) -> set:
    """Extract person names from a creator string."""
    # Split on commas, semicolons, "and"
    parts = re.split(r'[,;]\s*|\s+and\s+', text)
    names = set()
    for p in parts:
        p = p.strip()
        # Filter out org-like strings and short fragments
        if p and len(p) > 2 and not re.match(r'^(the|university|institute|lab|inc|corp)', p.lower()):
            # Normalize: lowercase, strip titles
            names.add(re.sub(r'[^\w\s]', '', p.lower()).strip())
    return names


def _label_short_text(gt: str, ext: str, field: str) -> int:
    """Label a short-text field extraction."""
    if field in ("creator", "sc:creator"):
        # Set-based name comparison
        gt_names = _extract_names(gt)
        ext_names = _extract_names(ext)
        if not gt_names or not ext_names:
            # Fallback to token F1
            f1 = score_token_f1(ext, gt)
            if f1 > TOKEN_F1_CORRECT:
                return 1
            elif f1 > TOKEN_F1_PARTIAL:
                return 2
            return 3

        overlap = len(gt_names & ext_names)
        if overlap == len(gt_names) and overlap == len(ext_names):
            return 1  # Same set
        elif overlap > 0:
            return 2  # Some overlap
        else:
            return 3  # No overlap

    # description and other short-text: token F1
    f1 = score_token_f1(ext, gt)
    if f1 > TOKEN_F1_CORRECT:
        return 1
    elif f1 > TOKEN_F1_PARTIAL:
        return 2
    return 3


def _label_rai(gt: str, ext: str) -> int:
    """Label a RAI field extraction using token F1."""
    f1 = score_token_f1(ext, gt)
    if f1 > TOKEN_F1_CORRECT:
        return 1
    elif f1 > TOKEN_F1_PARTIAL:
        return 2
    return 3


def compute_true_label(gt_value: Optional[str], extraction_value: Optional[str],
                       field_name: str) -> Optional[int]:
    """Compute true label for a (GT, extraction) pair.

    Args:
        gt_value: Ground truth value (None if no GT)
        extraction_value: Model extraction (None if null)
        field_name: Field name (prefixed or unprefixed)

    Returns:
        1 (Correct), 2 (Partially Correct), 3 (Incorrect), or None (skip)
    """
    gt_empty = gt_value is None or not str(gt_value).strip()
    ext_empty = (extraction_value is None or not str(extraction_value).strip()
                 or str(extraction_value).strip().lower() in
                 ("none", "null", "[null]", "[null - not found in paper]"))

    # Both empty → skip (not evaluable)
    if gt_empty and ext_empty:
        return None

    # GT empty, extraction non-empty → hallucination
    if gt_empty and not ext_empty:
        return None  # skip — no GT to evaluate against

    # GT non-empty, extraction empty → miss
    if not gt_empty and ext_empty:
        return 3

    gt = str(gt_value).strip()
    ext = str(extraction_value).strip()

    field_type = get_field_type(field_name)

    if field_type == "constrained":
        return _label_constrained(gt, ext, field_name)
    elif field_type == "short_text":
        return _label_short_text(gt, ext, field_name)
    else:
        return _label_rai(gt, ext)
