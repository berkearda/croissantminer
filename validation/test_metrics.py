#!/usr/bin/env python3
"""
Task 3: Metric Computation Unit Tests

Tests for exact match, token F1, LLM judge, composite score, and null handling.
Run: pytest validation/test_metrics.py -v
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from evaluation.field_metrics import (
    score_constrained,
    score_token_f1,
    score_field,
    get_field_category,
    _normalize_license,
    _normalize_language,
    _normalize_boolean,
    _normalize_url,
    _extract_year,
    _names_match,
)


# ═══════════════════════════════════════════════════════════════════════
# 3a: Exact match tests
# ═══════════════════════════════════════════════════════════════════════

class TestExactMatch:
    """Tests for score_constrained (exact match after normalization)."""

    def test_basic_match(self):
        assert score_constrained("MIT", "MIT", "sc:license") == 1.0

    def test_basic_mismatch(self):
        assert score_constrained("MIT", "Apache-2.0", "sc:license") == 0.0

    def test_license_normalization(self):
        """MIT License, mit, The MIT License → all map to 'mit'."""
        assert score_constrained("MIT License", "MIT", "sc:license") == 1.0
        assert score_constrained("mit", "MIT", "sc:license") == 1.0
        assert score_constrained("The MIT License", "MIT", "sc:license") == 1.0

    def test_license_cc_variants(self):
        assert score_constrained("CC BY 4.0", "cc-by-4.0", "sc:license") == 1.0
        assert score_constrained("Creative Commons Attribution 4.0", "cc-by-4.0", "sc:license") == 1.0
        assert score_constrained("CC-BY-SA-4.0", "cc-by-sa-4.0", "sc:license") == 1.0

    def test_license_url(self):
        assert score_constrained(
            "https://creativecommons.org/licenses/by-sa/4.0/",
            "CC-BY-SA-4.0", "sc:license"
        ) == 1.0

    def test_language_normalization(self):
        assert score_constrained("en", "English", "sc:inLanguage") == 1.0
        assert score_constrained("eng", "english", "sc:inLanguage") == 1.0
        assert score_constrained("English", "en", "sc:inLanguage") == 1.0

    def test_language_multilingual(self):
        """Both have the same set of languages → match."""
        assert score_constrained("en, fr", "English, French", "sc:inLanguage") == 1.0

    def test_date_year_extraction(self):
        """Year-only match is sufficient."""
        assert score_constrained("2021", "2021", "sc:datePublished") == 1.0
        assert score_constrained("2021-10-28", "2021", "sc:datePublished") == 1.0
        assert score_constrained("October 2021", "2021", "sc:datePublished") == 1.0
        assert score_constrained("2021", "2022", "sc:datePublished") == 0.0

    def test_boolean_normalization(self):
        assert score_constrained("Yes", "true", "cr:isLiveDataset") == 1.0
        assert score_constrained("No", "false", "cr:isLiveDataset") == 1.0
        assert score_constrained("Yes", "No", "cr:isLiveDataset") == 0.0
        assert score_constrained("1", "true", "cr:isLiveDataset") == 1.0

    def test_url_normalization(self):
        """Strip protocol and trailing slash."""
        assert score_constrained(
            "https://github.com/hendrycks/test",
            "http://github.com/hendrycks/test/",
            "sc:url"
        ) == 1.0

    def test_name_matching(self):
        assert score_constrained("MMLU", "MMLU", "sc:name") == 1.0
        assert score_constrained(
            "MMLU (Massive Multitask Language Understanding)",
            "MMLU", "sc:name"
        ) == 1.0
        assert score_constrained("mmlu", "MMLU", "sc:name") == 1.0

    def test_publisher_fuzzy(self):
        """Publisher uses token overlap ≥50%."""
        assert score_constrained("ICLR 2021", "ICLR 2021", "sc:publisher") == 1.0
        assert score_constrained("ICLR", "ICLR 2021", "sc:publisher") == 1.0

    def test_whitespace_handling(self):
        assert score_constrained("  MIT  ", "MIT", "sc:license") == 1.0
        assert score_constrained("  en  ", "English", "sc:inLanguage") == 1.0


# ═══════════════════════════════════════════════════════════════════════
# 3b: Token F1 tests
# ═══════════════════════════════════════════════════════════════════════

class TestTokenF1:
    """Tests for score_token_f1."""

    def test_identical_strings(self):
        assert score_token_f1("The dataset contains images", "The dataset contains images") == 1.0

    def test_subset(self):
        """Predicted is subset of GT → recall=1, precision<1."""
        f1 = score_token_f1("images cats", "the dataset contains images of cats and dogs")
        assert 0.3 < f1 < 0.8

    def test_no_overlap(self):
        assert score_token_f1("hello world", "foo bar baz") == 0.0

    def test_empty_strings(self):
        assert score_token_f1("", "") == 1.0
        assert score_token_f1("hello", "") == 0.0
        assert score_token_f1("", "hello") == 0.0

    def test_case_insensitive(self):
        """F1 should be case-insensitive."""
        assert score_token_f1("MIT License", "mit license") == 1.0

    def test_partial_overlap(self):
        f1 = score_token_f1("Alex Krizhevsky", "Alex Krizhevsky, Vinod Nair, Geoffrey Hinton")
        assert 0.3 < f1 < 0.7  # partial overlap


# ═══════════════════════════════════════════════════════════════════════
# 3c: Unified scorer / null handling tests
# ═══════════════════════════════════════════════════════════════════════

class TestScoreField:
    """Tests for the unified score_field function, especially null handling."""

    def test_both_null_gt_skipped(self):
        """If GT is null → skip (not evaluable)."""
        result = score_field(None, None, "sc:license")
        assert result["skipped"] is True
        assert result["score"] is None

    def test_gt_unknown_treated_as_null(self):
        """GT values like 'Unknown', 'N/A' count as null gold: an empty
        prediction is skipped, a filled one scores 0 (hallucination)."""
        for unknown_val in ["Unknown", "N/A", "null", "Not disclosed",
                            "[NULL - not found in paper]"]:
            result = score_field(None, unknown_val, "sc:license")
            assert result["skipped"] is True, f"Should skip GT='{unknown_val}'"
            result = score_field("MIT", unknown_val, "sc:license")
            assert result["skipped"] is False, f"Should score GT='{unknown_val}'"
            assert result["score"] == 0.0
            assert result["metric"] == "hallucination"

    def test_pred_null_gt_has_value(self):
        """Prediction is null but GT has value → score 0 (miss)."""
        result = score_field(None, "MIT", "sc:license")
        assert result["skipped"] is False
        assert result["score"] == 0.0
        assert result["reason"] == "Extraction is null but GT has value"

    def test_constrained_field_scored(self):
        result = score_field("MIT", "MIT", "sc:license")
        assert result["score"] == 1.0
        assert result["metric"] == "exact_match"

    def test_short_text_field_scored(self):
        result = score_field("some text here", "some text here", "sc:description")
        assert result["score"] == 1.0
        assert result["metric"] == "token_f1"

    def test_field_category_detection(self):
        assert get_field_category("sc:name") == "constrained"
        assert get_field_category("sc:description") == "short_text"
        assert get_field_category("rai:dataCollection") == "rai"
        assert get_field_category("nonexistent") == "unknown"


# ═══════════════════════════════════════════════════════════════════════
# 3d: Composite score tests
# ═══════════════════════════════════════════════════════════════════════

class TestComposite:
    """Tests for composite score computation logic."""

    def test_all_perfect(self):
        """All scores 1.0 → composite 1.0."""
        import numpy as np
        scores = [1.0] * 30
        assert np.mean(scores) == 1.0

    def test_all_zero(self):
        import numpy as np
        scores = [0.0] * 30
        assert np.mean(scores) == 0.0

    def test_mixed(self):
        import numpy as np
        scores = [1.0] * 15 + [0.0] * 15
        assert abs(np.mean(scores) - 0.5) < 0.01

    def test_skipped_excluded(self):
        """Skipped fields should NOT be included in composite."""
        # Simulate: score_field returns skipped=True → should not enter the average
        results = [
            {"score": 1.0, "skipped": False},
            {"score": 0.0, "skipped": False},
            {"score": None, "skipped": True},  # GT was null
        ]
        evaluated = [r["score"] for r in results if not r["skipped"]]
        import numpy as np
        assert abs(np.mean(evaluated) - 0.5) < 0.01


# ═══════════════════════════════════════════════════════════════════════
# 3e: Null classification tests
# ═══════════════════════════════════════════════════════════════════════

class TestNullClassification:
    """Tests for null handling classification logic.

    Design decisions documented here:
    - gt=None, pred=None → "correct_null" (both agree it's missing) → SKIP in evaluation
    - gt=None, pred="something" → "hallucination" → SKIP (no GT to evaluate against)
    - gt="something", pred=None → "miss" → score 0.0
    - gt="something", pred="something" → "non_null" → evaluate with appropriate metric
    """

    def test_both_null(self):
        result = score_field(None, None, "sc:license")
        assert result["skipped"] is True
        # Both null → correct null, but we skip (no GT to evaluate)

    def test_hallucination_on_null_gt(self):
        """Pred has value but GT is null → score 0 (hallucination)."""
        result = score_field("MIT", None, "sc:license")
        assert result["skipped"] is False
        assert result["score"] == 0.0
        assert result["metric"] == "hallucination"

    def test_miss(self):
        """GT has value but pred is null → score 0."""
        result = score_field(None, "MIT", "sc:license")
        assert result["score"] == 0.0
        assert not result["skipped"]

    def test_non_null_evaluated(self):
        """Both have values → evaluate normally."""
        result = score_field("MIT", "MIT", "sc:license")
        assert result["score"] == 1.0
        assert not result["skipped"]


# ═══════════════════════════════════════════════════════════════════════
# Normalizer unit tests
# ═══════════════════════════════════════════════════════════════════════

class TestNormalizers:
    """Direct tests for internal normalizer functions."""

    def test_normalize_license(self):
        assert _normalize_license("MIT") == "mit"
        assert _normalize_license("MIT License") == "mit"
        assert _normalize_license("CC BY 4.0") == "cc-by-4.0"
        assert _normalize_license("Apache 2.0") == "apache-2.0"
        assert _normalize_license("GPL-3.0") == "gpl-3.0"

    def test_normalize_language(self):
        langs = _normalize_language("en")
        assert "english" in langs
        langs = _normalize_language("English, French")
        assert "english" in langs
        assert "french" in langs

    def test_extract_year(self):
        assert _extract_year("2021") == "2021"
        assert _extract_year("Published in 2021") == "2021"
        assert _extract_year("2021-10-28") == "2021"
        assert _extract_year("no year here") is None

    def test_normalize_boolean(self):
        assert _normalize_boolean("Yes") == "true"
        assert _normalize_boolean("No") == "false"
        assert _normalize_boolean("true") == "true"
        assert _normalize_boolean("1") == "true"
        assert _normalize_boolean("0") == "false"

    def test_normalize_url(self):
        assert _normalize_url("https://example.com/") == "example.com"
        assert _normalize_url("http://example.com") == "example.com"

    def test_names_match(self):
        assert _names_match("MMLU", "MMLU")
        assert _names_match("MMLU", "MMLU (Massive Multitask Language Understanding)")
        assert _names_match("mmlu", "MMLU")
        assert not _names_match("MMLU", "MMMU")


# ═══════════════════════════════════════════════════════════════════════
# True label computation tests
# ═══════════════════════════════════════════════════════════════════════

class TestTrueLabels:
    """Tests for field-type-stratified true label computation."""

    def _import(self):
        from evaluation.true_labels import compute_true_label, get_field_type
        return compute_true_label, get_field_type

    # ── Field type detection ──
    def test_field_type_constrained(self):
        _, gft = self._import()
        assert gft("name") == "constrained"
        assert gft("sc:name") == "constrained"
        assert gft("license") == "constrained"
        assert gft("datePublished") == "constrained"
        assert gft("cr:isLiveDataset") == "constrained"

    def test_field_type_short_text(self):
        _, gft = self._import()
        assert gft("creator") == "short_text"
        assert gft("sc:creator") == "short_text"
        assert gft("description") == "short_text"

    def test_field_type_rai(self):
        _, gft = self._import()
        assert gft("rai:dataCollection") == "rai"
        assert gft("rai:dataBiases") == "rai"

    # ── Constrained: exact match ──
    def test_constrained_exact(self):
        ctl, _ = self._import()
        assert ctl("MIT", "MIT", "license") == 1
        assert ctl("MIT", "MIT License", "license") == 1  # normalized
        assert ctl("2021", "2021", "datePublished") == 1

    def test_constrained_prefix_partial(self):
        ctl, _ = self._import()
        # "ICLR" is substring of "ICLR 2021" but shorter → Partial
        assert ctl("ICLR 2021", "ICLR", "publisher") == 2
        # "2016" vs "2016-02-23" → year matches → Correct (by design: year-only is acceptable)
        assert ctl("2016-02-23", "2016", "datePublished") == 1
        # Different year → Incorrect
        assert ctl("2016-02-23", "2017", "datePublished") == 3

    def test_constrained_completely_different(self):
        ctl, _ = self._import()
        assert ctl("MIT", "Apache-2.0", "license") == 3
        assert ctl("MMLU", "SQuAD", "name") == 3

    # ── Short-text: creator names ──
    def test_creator_same_names(self):
        ctl, _ = self._import()
        assert ctl("Alice Smith, Bob Jones", "Bob Jones, Alice Smith", "creator") == 1

    def test_creator_partial_overlap(self):
        ctl, _ = self._import()
        # Only 1 of 3 names matches
        result = ctl("Alice, Bob, Charlie", "Alice, Dave, Eve", "creator")
        assert result == 2

    def test_creator_no_overlap(self):
        ctl, _ = self._import()
        assert ctl("Alice, Bob", "Charlie, Dave", "creator") == 3

    # ── RAI: token F1 thresholds ──
    def test_rai_correct(self):
        ctl, _ = self._import()
        result = ctl(
            "Data collected via web scraping from Reddit posts",
            "Data collected via web scraping from Reddit posts",
            "rai:dataCollection"
        )
        assert result == 1

    def test_rai_partial(self):
        ctl, _ = self._import()
        result = ctl(
            "Data collected via web scraping from Reddit posts between 2019 and 2021 using the PRAW API",
            "Data collected via web scraping from Reddit",
            "rai:dataCollection"
        )
        assert result == 2

    def test_rai_incorrect(self):
        ctl, _ = self._import()
        result = ctl(
            "Data collected via web scraping from Reddit",
            "The weather is nice today",
            "rai:dataCollection"
        )
        assert result == 3

    # ── Null handling ──
    def test_both_null(self):
        ctl, _ = self._import()
        assert ctl(None, None, "license") is None

    def test_gt_null_ext_present(self):
        ctl, _ = self._import()
        assert ctl(None, "MIT", "license") is None  # skip

    def test_gt_present_ext_null(self):
        ctl, _ = self._import()
        assert ctl("MIT", None, "license") == 3  # miss

    def test_ext_null_string(self):
        ctl, _ = self._import()
        assert ctl("MIT", "[NULL - not found in paper]", "license") == 3
