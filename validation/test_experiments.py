"""
Tests for experiment outputs and the shared extraction validator.

Run: pytest validation/test_experiments.py -v

Add new tests here as experiments are created. Each experiment should have
at minimum:
  - Output format validation test
  - Score range validation test
  - Experiment-specific logic tests (truncation, voting, etc.)
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from validation.validate_extraction import (
    validate_extraction,
    CANONICAL_FIELDS,
)


# ═══════════════════════════════════════════════════════════════════════
# Shared extraction validator tests
# ═══════════════════════════════════════════════════════════════════════

class TestValidateExtraction:
    """Tests for the shared validate_extraction utility."""

    def _make_valid(self):
        """Create a valid 30-field extraction dict."""
        return {f: None for f in CANONICAL_FIELDS}

    def test_valid_extraction(self):
        data = self._make_valid()
        valid, errors = validate_extraction(data, "test")
        assert valid, f"Should be valid: {errors}"
        assert errors == []

    def test_missing_field(self):
        data = self._make_valid()
        del data["name"]
        valid, errors = validate_extraction(data, "test")
        assert not valid
        assert any("missing" in e for e in errors)

    def test_extra_field(self):
        data = self._make_valid()
        data["rai:extraField"] = "value"
        valid, errors = validate_extraction(data, "test")
        assert not valid
        assert any("extra" in e for e in errors)

    def test_typo_detected(self):
        """The datLimitations typo that was caught in production."""
        data = self._make_valid()
        del data["rai:dataLimitations"]
        data["rai:datLimitations"] = "some value"
        valid, errors = validate_extraction(data, "test")
        assert not valid
        assert any("missing" in e for e in errors)
        assert any("extra" in e for e in errors)

    def test_whitespace_in_field_name(self):
        data = self._make_valid()
        data[" name"] = data.pop("name")
        valid, errors = validate_extraction(data, "test")
        assert not valid
        assert any("whitespace" in e for e in errors)

    def test_unexpected_type(self):
        data = self._make_valid()
        data["name"] = 12345  # int is actually valid
        valid, errors = validate_extraction(data, "test")
        assert valid  # int is in VALID_VALUE_TYPES

        data["name"] = set()  # set is NOT valid
        valid, errors = validate_extraction(data, "test")
        assert not valid

    def test_not_a_dict(self):
        valid, errors = validate_extraction("not a dict", "test")
        assert not valid
        assert any("not a dict" in e for e in errors)

    def test_all_null_valid(self):
        """All fields null is a valid extraction (paper had no info)."""
        data = {f: None for f in CANONICAL_FIELDS}
        valid, errors = validate_extraction(data, "test")
        assert valid

    def test_all_strings_valid(self):
        data = {f: "some value" for f in CANONICAL_FIELDS}
        valid, errors = validate_extraction(data, "test")
        assert valid

    def test_canonical_fields_count(self):
        """Sanity: exactly 30 canonical fields."""
        assert len(CANONICAL_FIELDS) == 30


# ═══════════════════════════════════════════════════════════════════════
# Existing extraction output format tests
# ═══════════════════════════════════════════════════════════════════════

class TestExistingExtractions:
    """Verify all 103 corpus extraction files pass validation.

    Only checks the 103 datasets in paper_links.json (the corpus).
    Legacy Phase 1 extractions (CIFAR, FLORES, etc. without _30field suffix)
    use an older schema with unprefixed RAI fields and are excluded.
    """

    ROOT = Path(__file__).parent.parent
    PROCESSED = ROOT / "data" / "processed"
    PAPER_LINKS = ROOT / "data" / "paper_links.json"

    def _get_corpus_ids(self):
        if not self.PAPER_LINKS.exists():
            pytest.skip("paper_links.json not found")
        with open(self.PAPER_LINKS) as f:
            return sorted(json.load(f).keys())

    def test_all_corpus_extractions_valid(self):
        """All 103 corpus extractions must have exactly 30 canonical fields."""
        corpus_ids = self._get_corpus_ids()
        failures = []
        for ds_id in corpus_ids:
            ext = self.PROCESSED / ds_id / "full_pdf_metadata_result.json"
            if not ext.exists():
                failures.append(f"{ds_id}: extraction file not found")
                continue
            with open(ext) as f:
                data = json.load(f)
            valid, errors = validate_extraction(data, ds_id)
            if not valid:
                failures.extend(errors)

        assert not failures, f"Extraction validation failures:\n" + "\n".join(failures)

    def test_corpus_extraction_count(self):
        """All 103 corpus datasets should have extractions."""
        corpus_ids = self._get_corpus_ids()
        ext_count = sum(1 for ds_id in corpus_ids
                        if (self.PROCESSED / ds_id / "full_pdf_metadata_result.json").exists())
        assert ext_count == 103, f"Expected 103 corpus extractions, found {ext_count}"


# ═══════════════════════════════════════════════════════════════════════
# Context ablation experiment tests
# ═══════════════════════════════════════════════════════════════════════

class TestContextAblation:
    """Tests for the context ablation experiment."""

    def test_truncation_lengths(self):
        """50pct is ~50% of full, 25pct is ~25%, abstract is < 5000."""
        sys.path.insert(0, str(Path(__file__).parent.parent / "experiments"))
        from context_ablation import truncate_text, extract_abstract

        full = "word " * 10000  # 50000 chars
        assert len(truncate_text(full, "full")) == len(full)
        assert abs(len(truncate_text(full, "50pct")) - len(full) * 0.5) < 10
        assert abs(len(truncate_text(full, "25pct")) - len(full) * 0.25) < 10

    def test_truncation_ordering(self):
        """full > 50pct > 25pct > abstract."""
        sys.path.insert(0, str(Path(__file__).parent.parent / "experiments"))
        from context_ablation import truncate_text

        full = "word " * 10000
        assert len(truncate_text(full, "full")) > len(truncate_text(full, "50pct"))
        assert len(truncate_text(full, "50pct")) > len(truncate_text(full, "25pct"))

    def test_abstract_extraction(self):
        """Abstract extractor finds the abstract section."""
        sys.path.insert(0, str(Path(__file__).parent.parent / "experiments"))
        from context_ablation import extract_abstract

        paper = """Title: Some Paper
Abstract
This paper presents a new dataset for testing language models.
We collected 10,000 examples from online sources.

1. Introduction
Language models have become increasingly powerful..."""

        abstract = extract_abstract(paper)
        assert "dataset" in abstract.lower()
        assert "introduction" not in abstract.lower() or len(abstract) < 500

    def test_abstract_fallback(self):
        """If no abstract heading, fallback to first 3000 chars."""
        sys.path.insert(0, str(Path(__file__).parent.parent / "experiments"))
        from context_ablation import extract_abstract

        paper = "No abstract heading here. " * 200
        abstract = extract_abstract(paper)
        assert len(abstract) <= 3000


# ═══════════════════════════════════════════════════════════════════════
# Few-shot ablation experiment tests
# ═══════════════════════════════════════════════════════════════════════

class TestFewShotAblation:
    """Tests for the few-shot ablation experiment."""

    def _import(self):
        sys.path.insert(0, str(Path(__file__).parent.parent / "experiments"))
        import fewshot_ablation
        return fewshot_ablation

    def test_load_examples(self):
        """Can load 1 and 3 examples."""
        mod = self._import()
        ex1 = mod.load_examples(1)
        assert len(ex1) == 1
        assert "paper_summary" in ex1[0]
        assert "extraction" in ex1[0]

        ex3 = mod.load_examples(3)
        assert len(ex3) == 3

    def test_load_zero_examples(self):
        mod = self._import()
        ex0 = mod.load_examples(0)
        assert len(ex0) == 0

    def test_prompt_with_examples(self):
        """Few-shot prompt contains examples and schema."""
        mod = self._import()
        examples = mod.load_examples(1)
        prompt = mod.build_fewshot_prompt("Test paper text", examples)
        assert "Example 1" in prompt
        assert "Test paper text" in prompt
        assert "SCHEMA" in prompt
        assert '"name"' in prompt

    def test_prompt_without_examples(self):
        """0-shot prompt has no examples section."""
        mod = self._import()
        prompt = mod.build_fewshot_prompt("Test paper text", [])
        assert "Example" not in prompt
        assert "Test paper text" in prompt

    def test_prompt_length_ordering(self):
        """3-shot prompt > 1-shot prompt > 0-shot prompt."""
        mod = self._import()
        p0 = mod.build_fewshot_prompt("text", [])
        p1 = mod.build_fewshot_prompt("text", mod.load_examples(1))
        p3 = mod.build_fewshot_prompt("text", mod.load_examples(3))
        assert len(p3) > len(p1) > len(p0)

    def test_example_diversity(self):
        """Examples come from different domains (different dataset IDs)."""
        mod = self._import()
        assert len(set(mod.EXAMPLE_IDS)) == len(mod.EXAMPLE_IDS)  # no duplicates

    def test_example_datasets_excluded_from_targets(self):
        """Example dataset IDs should not be evaluated as targets."""
        mod = self._import()
        # The script skips example datasets — verify IDs are in the corpus
        with open(mod.PAPER_LINKS) as f:
            corpus = set(json.load(f).keys())
        for eid in mod.EXAMPLE_IDS:
            assert eid in corpus, f"Example {eid} not in corpus"


# ═══════════════════════════════════════════════════════════════════════
# Gemini extraction experiment tests
# ═══════════════════════════════════════════════════════════════════════

class TestGeminiExtraction:
    """Tests for the Gemini extraction experiment."""

    def _import(self):
        sys.path.insert(0, str(Path(__file__).parent.parent / "experiments"))
        import gemini_extraction
        return gemini_extraction

    def test_model_configs_present(self):
        mod = self._import()
        assert "gemini-2.5-pro" in mod.MODELS
        assert "gemini-2.0-flash" in mod.MODELS

    def test_model_config_fields(self):
        mod = self._import()
        for name, cfg in mod.MODELS.items():
            assert "model_id" in cfg, f"{name} missing model_id"
            assert "rpm_limit" in cfg, f"{name} missing rpm_limit"
            assert "delay" in cfg, f"{name} missing delay"
            assert "max_chars" in cfg, f"{name} missing max_chars"
            assert cfg["delay"] >= 60 / cfg["rpm_limit"] - 1, \
                f"{name} delay too low for RPM limit"

    def test_output_dir_naming(self):
        """Output dir should use underscores not dots."""
        mod = self._import()
        for name in mod.MODELS:
            safe = name.replace(".", "_")
            assert "." not in safe

    def test_find_pdf_works(self):
        mod = self._import()
        # Should find at least one corpus PDF
        pdf = mod.find_pdf("openai_gsm8k")
        assert pdf is not None and pdf.exists()

    def test_find_pdf_benchmark(self):
        mod = self._import()
        pdf = mod.find_pdf("MMLU_30field")
        assert pdf is not None and pdf.exists()


# ═══════════════════════════════════════════════════════════════════════
# Self-consistency experiment tests
# ═══════════════════════════════════════════════════════════════════════

class TestSelfConsistency:
    """Tests for the self-consistency voting logic."""

    def _import(self):
        sys.path.insert(0, str(Path(__file__).parent.parent / "experiments"))
        import self_consistency
        return self_consistency

    def test_unanimous_vote(self):
        mod = self._import()
        winner, agr, method = mod.vote_field("name", ["MMLU", "MMLU", "MMLU"])
        assert winner == "MMLU"
        assert agr == 100.0
        assert method == "majority"

    def test_majority_vote(self):
        mod = self._import()
        winner, agr, method = mod.vote_field("name", ["MMLU", "MMLU", "mmlu benchmark"])
        assert winner == "MMLU"
        assert method == "majority"

    def test_all_null(self):
        mod = self._import()
        winner, agr, method = mod.vote_field("license", [None, None, None])
        assert winner is None
        assert agr == 100.0
        assert method == "unanimous_null"

    def test_no_majority_constrained_uses_first(self):
        mod = self._import()
        winner, agr, method = mod.vote_field("name", ["A", "B", "C"])
        assert winner == "A"
        assert method == "first_fallback"

    def test_no_majority_rai_uses_longest(self):
        mod = self._import()
        winner, agr, method = mod.vote_field("rai:dataCollection",
                                              ["short", "medium length text", "the longest text of all three"])
        assert winner == "the longest text of all three"
        assert method == "longest"

    def test_no_majority_short_text_uses_longest(self):
        mod = self._import()
        winner, agr, method = mod.vote_field("description",
                                              ["short", "a bit longer", "the longest description here"])
        assert winner == "the longest description here"
        assert method == "longest"

    def test_merge_extractions(self):
        mod = self._import()
        runs = [
            {"name": "MMLU", "description": "A benchmark", "url": "http://a.com",
             **{f: None for f in mod.CANONICAL_FIELDS if f not in ("name", "description", "url")}},
            {"name": "MMLU", "description": "A test benchmark", "url": "http://a.com",
             **{f: None for f in mod.CANONICAL_FIELDS if f not in ("name", "description", "url")}},
            {"name": "MMLU", "description": "A benchmark dataset", "url": "http://b.com",
             **{f: None for f in mod.CANONICAL_FIELDS if f not in ("name", "description", "url")}},
        ]
        merged, report = mod.merge_extractions(runs)
        assert merged["name"] == "MMLU"  # unanimous
        assert report["name"]["agreement_pct"] == 100.0
        assert merged["url"] == "http://a.com"  # majority (2 vs 1)

    def test_normalize_for_vote(self):
        mod = self._import()
        assert mod.normalize_for_vote("MIT") == "mit"
        assert mod.normalize_for_vote("  MIT  ") == "mit"
        assert mod.normalize_for_vote(None) is None
        assert mod.normalize_for_vote("null") is None
        assert mod.normalize_for_vote("") is None


# ═══════════════════════════════════════════════════════════════════════
# Tool-augmented pipeline tests
# ═══════════════════════════════════════════════════════════════════════

class TestLicenseValidator:
    """Tests for license SPDX validation."""

    def _import(self):
        sys.path.insert(0, str(Path(__file__).parent.parent / "experiments"))
        from validators.license_validator import validate_license
        return validate_license

    def test_valid_mit(self):
        v = self._import()
        r = v("MIT")
        assert r["valid"]
        assert r["spdx_id"] == "MIT"

    def test_valid_cc_by(self):
        v = self._import()
        r = v("CC BY 4.0")
        assert r["valid"]
        assert r["spdx_id"] == "CC-BY-4.0"

    def test_valid_apache(self):
        v = self._import()
        r = v("Apache 2.0")
        assert r["valid"]
        assert r["spdx_id"] == "Apache-2.0"

    def test_invalid_garbage(self):
        v = self._import()
        r = v("Some random text that is not a license")
        assert not r["valid"]
        assert r["suggestion"] is not None

    def test_empty(self):
        v = self._import()
        assert not v("")["valid"]
        assert not v(None)["valid"]

    def test_cc_url(self):
        v = self._import()
        r = v("https://creativecommons.org/licenses/by-sa/4.0/")
        assert r["valid"]
        assert "CC" in r["spdx_id"]


class TestArxivValidator:
    """Tests for arXiv ID extraction (no network calls needed)."""

    def test_extract_id_from_url(self):
        sys.path.insert(0, str(Path(__file__).parent.parent / "experiments"))
        from validators.arxiv_validator import _extract_arxiv_id
        assert _extract_arxiv_id("https://arxiv.org/abs/2009.03300") == "2009.03300"
        assert _extract_arxiv_id("https://arxiv.org/abs/2009.03300v3") == "2009.03300v3"
        assert _extract_arxiv_id("https://arxiv.org/pdf/2009.03300") == "2009.03300"

    def test_extract_bare_id(self):
        sys.path.insert(0, str(Path(__file__).parent.parent / "experiments"))
        from validators.arxiv_validator import _extract_arxiv_id
        assert _extract_arxiv_id("2009.03300") == "2009.03300"
        assert _extract_arxiv_id("2009.03300v3") == "2009.03300v3"


class TestDOIValidator:
    """Tests for DOI extraction (no network calls needed)."""

    def test_extract_doi_from_url(self):
        sys.path.insert(0, str(Path(__file__).parent.parent / "experiments"))
        from validators.doi_validator import _extract_doi
        assert _extract_doi("https://doi.org/10.1234/test") == "10.1234/test"

    def test_extract_bare_doi(self):
        sys.path.insert(0, str(Path(__file__).parent.parent / "experiments"))
        from validators.doi_validator import _extract_doi
        assert _extract_doi("10.1234/test.123") == "10.1234/test.123"

    def test_no_doi(self):
        sys.path.insert(0, str(Path(__file__).parent.parent / "experiments"))
        from validators.doi_validator import _extract_doi
        assert _extract_doi("no doi here") is None


class TestToolAugmentedOrchestrator:
    """Tests for the orchestrator logic (no network calls)."""

    def test_correction_prompt_format(self):
        sys.path.insert(0, str(Path(__file__).parent.parent / "experiments"))
        from tool_augmented import build_correction_prompt

        extraction = {"url": "http://broken.com", "license": "MIT"}
        failures = {
            "url": {"message": "HTTP 404", "result": {"suggestion": None}},
        }
        prompt = build_correction_prompt(extraction, failures, "paper text here")
        assert "url" in prompt
        assert "HTTP 404" in prompt
        assert "paper text here" in prompt

    def test_run_validators_empty(self):
        sys.path.insert(0, str(Path(__file__).parent.parent / "experiments"))
        from tool_augmented import run_validators

        # All null extraction — no validators should fire
        extraction = {f: None for f in CANONICAL_FIELDS}
        results = run_validators(extraction, "")
        assert len(results) == 0


# ═══════════════════════════════════════════════════════════════════════
# Fine-tuning infrastructure tests
# ═══════════════════════════════════════════════════════════════════════

class TestFinetuningDataPrep:
    """Tests for training data preparation (GT construction, formatting)."""

    def _import(self):
        sys.path.insert(0, str(Path(__file__).parent.parent / "finetuning"))
        import prepare_data
        return prepare_data

    def test_gt_correct_uses_claude(self):
        """Rating=1 (Correct) → GT = Claude's value."""
        mod = self._import()
        claude = {f: None for f in CANONICAL_FIELDS}
        claude["name"] = "MMLU"
        annotations = {("ds1", "name"): {"rating": 1, "corrected": None, "annotator": "A"}}
        gt = mod.construct_gt(claude, annotations, "ds1")
        assert gt["name"] == "MMLU"

    def test_gt_incorrect_with_correction(self):
        """Rating=3 + correction → GT = correction."""
        mod = self._import()
        claude = {f: None for f in CANONICAL_FIELDS}
        claude["name"] = "Wrong Name"
        annotations = {("ds1", "name"): {"rating": 3, "corrected": "Correct Name", "annotator": "A"}}
        gt = mod.construct_gt(claude, annotations, "ds1")
        assert gt["name"] == "Correct Name"

    def test_gt_incorrect_without_correction(self):
        """Rating=3 + no correction → GT = None."""
        mod = self._import()
        claude = {f: None for f in CANONICAL_FIELDS}
        claude["name"] = "Wrong Name"
        annotations = {("ds1", "name"): {"rating": 3, "corrected": None, "annotator": "A"}}
        gt = mod.construct_gt(claude, annotations, "ds1")
        assert gt["name"] is None

    def test_gt_partial_uses_claude(self):
        """Rating=2 (Partial) → GT = Claude's value (mostly right)."""
        mod = self._import()
        claude = {f: None for f in CANONICAL_FIELDS}
        claude["name"] = "Partial Name"
        annotations = {("ds1", "name"): {"rating": 2, "corrected": None, "annotator": "A"}}
        gt = mod.construct_gt(claude, annotations, "ds1")
        assert gt["name"] == "Partial Name"

    def test_gt_unannotated_uses_claude(self):
        """No annotation → GT = Claude's value (unverified)."""
        mod = self._import()
        claude = {f: None for f in CANONICAL_FIELDS}
        claude["description"] = "A dataset"
        gt = mod.construct_gt(claude, {}, "ds1")
        assert gt["description"] == "A dataset"

    def test_format_example_structure(self):
        """Chat-style JSONL has correct structure."""
        mod = self._import()
        gt = {f: "test" for f in CANONICAL_FIELDS}
        ex = mod.format_example("paper text here", gt)
        assert "messages" in ex
        assert len(ex["messages"]) == 3
        assert ex["messages"][0]["role"] == "system"
        assert ex["messages"][1]["role"] == "user"
        assert ex["messages"][2]["role"] == "assistant"
        assert "paper text here" in ex["messages"][1]["content"]
        # Assistant content should be valid JSON
        parsed = json.loads(ex["messages"][2]["content"])
        assert len(parsed) == 30

    def test_inference_schema(self):
        """JSON schema for constrained decoding has all 30 fields."""
        sys.path.insert(0, str(Path(__file__).parent.parent / "finetuning"))
        from inference import OUTPUT_SCHEMA
        assert len(OUTPUT_SCHEMA["required"]) == 30
        assert set(OUTPUT_SCHEMA["required"]) == CANONICAL_FIELDS
        assert OUTPUT_SCHEMA["additionalProperties"] is False


# ═══════════════════════════════════════════════════════════════════════
# Unified evaluation tests
# ═══════════════════════════════════════════════════════════════════════

class TestUnifiedEvaluation:
    """Tests for evaluate_all.py."""

    def _import(self):
        sys.path.insert(0, str(Path(__file__).parent.parent / "evaluation"))
        import evaluate_all
        return evaluate_all

    def test_classify_null(self):
        mod = self._import()
        assert mod.classify_null(None, None) == "skip"
        assert mod.classify_null("Unknown", "MIT") == "skip"
        assert mod.classify_null("MIT", None) == "miss"
        assert mod.classify_null("MIT", "MIT") == "non_null"
        assert mod.classify_null(None, "MIT") == "skip"  # no GT

    def test_bootstrap_ci_all_same(self):
        mod = self._import()
        lo, hi = mod.bootstrap_ci([0.5] * 100)
        assert abs(lo - 0.5) < 0.01
        assert abs(hi - 0.5) < 0.01

    def test_bootstrap_ci_range(self):
        mod = self._import()
        lo, hi = mod.bootstrap_ci([0.0, 1.0] * 50)
        assert lo < 0.5 < hi

    def test_bootstrap_ci_empty(self):
        mod = self._import()
        lo, hi = mod.bootstrap_ci([])
        assert lo == 0 and hi == 0

    def test_resolve_field_prefixed(self):
        mod = self._import()
        data = {"sc:name": "MMLU", "name": "should not use"}
        assert mod.resolve_field(data, "sc:name") == "MMLU"

    def test_resolve_field_unprefixed(self):
        mod = self._import()
        data = {"name": "MMLU"}
        assert mod.resolve_field(data, "sc:name") == "MMLU"

    def test_resolve_field_rai(self):
        mod = self._import()
        data = {"rai:dataCollection": "Method A"}
        assert mod.resolve_field(data, "rai:dataCollection") == "Method A"

    def test_strategy_dirs_defined(self):
        mod = self._import()
        # Should have at least the core strategies
        assert "claude_sonnet" in mod.STRATEGY_DIRS
        assert "gpt4o_mini" in mod.STRATEGY_DIRS
        assert "hf_auto" in mod.STRATEGY_DIRS

    def test_all_30_fields_covered(self):
        mod = self._import()
        assert len(mod.ALL_30_FIELDS) == 30
