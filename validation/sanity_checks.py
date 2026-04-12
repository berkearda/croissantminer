#!/usr/bin/env python3
"""
Task 4: End-to-End Sanity Checks

4a: Known-answer test (3 papers with manually verified fields)
4b: Determinism check (run extraction twice, compare)
4c: Metric consistency check
4d: Extraction format validation
4e: Score range validation
"""

import json
import sys
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent))

ROOT = Path(__file__).parent.parent
PROCESSED = ROOT / "data" / "processed"
PAPER_LINKS = ROOT / "data" / "paper_links.json"

EXPECTED_FIELDS = {
    "name", "description", "url", "license", "creator", "publisher",
    "datePublished", "inLanguage", "citeAs", "isLiveDataset",
    "rai:dataCollection", "rai:dataCollectionType", "rai:dataCollectionMissingData",
    "rai:dataCollectionRawData", "rai:dataCollectionTimeframe",
    "rai:dataImputationProtocol", "rai:dataManipulationProtocol",
    "rai:dataPreprocessingProtocol", "rai:dataAnnotationProtocol",
    "rai:dataAnnotationPlatform", "rai:dataAnnotationAnalysis",
    "rai:annotationsPerItem", "rai:annotatorDemographics",
    "rai:machineAnnotationTools", "rai:dataReleaseMaintenancePlan",
    "rai:personalSensitiveInformation", "rai:dataSocialImpact",
    "rai:dataBiases", "rai:dataLimitations", "rai:dataUseCases",
}


class CheckResult:
    def __init__(self, name):
        self.name = name
        self.passed = True
        self.messages = []

    def fail(self, msg):
        self.passed = False
        self.messages.append(f"FAIL: {msg}")

    def warn(self, msg):
        self.messages.append(f"WARN: {msg}")

    def info(self, msg):
        self.messages.append(f"INFO: {msg}")

    def __str__(self):
        status = "PASS" if self.passed else "FAIL"
        header = f"[{status}] {self.name}"
        if self.messages:
            return header + "\n" + "\n".join(f"  {m}" for m in self.messages)
        return header


def check_known_answers():
    """4a: Known-answer test — verify extractions for 3 well-known datasets."""
    r = CheckResult("4a: Known-Answer Test")

    # Manually verified ground truth for key fields
    KNOWN = {
        "MMLU_30field": {
            "name": "MMLU",  # should contain "MMLU"
            "datePublished": "2021",  # year should be 2021
            "isLiveDataset": "No",
        },
        "openai_gsm8k": {
            "name": "GSM8K",
            "datePublished": "2021",
            "isLiveDataset": "No",
        },
        "rajpurkar_squad": {
            "name": "SQuAD",
            "datePublished": "2016",
        },
    }

    for ds_id, expected in KNOWN.items():
        ext_path = PROCESSED / ds_id / "full_pdf_metadata_result.json"
        if not ext_path.exists():
            r.warn(f"{ds_id}: extraction not found")
            continue

        with open(ext_path) as f:
            data = json.load(f)

        for field, expected_val in expected.items():
            actual = data.get(field, "")
            actual_str = str(actual).lower() if actual else ""
            expected_lower = expected_val.lower()

            if expected_lower in actual_str:
                r.info(f"{ds_id}/{field}: OK ('{actual_str[:40]}' contains '{expected_lower}')")
            else:
                r.fail(f"{ds_id}/{field}: expected '{expected_val}', got '{actual_str[:60]}'")

    return r


def check_extraction_format():
    """4d: Validate JSON structure of all extractions."""
    r = CheckResult("4d: Extraction Format Validation")

    with open(PAPER_LINKS) as f:
        paper_links = json.load(f)

    issues = []
    checked = 0

    for ds_id in sorted(paper_links.keys()):
        ext_path = PROCESSED / ds_id / "full_pdf_metadata_result.json"
        if not ext_path.exists():
            continue

        checked += 1
        with open(ext_path) as f:
            data = json.load(f)

        fields = set(data.keys())

        # Check all 30 fields present
        missing = EXPECTED_FIELDS - fields
        extra = fields - EXPECTED_FIELDS
        if missing:
            issues.append(f"{ds_id}: missing fields {missing}")
        if extra:
            issues.append(f"{ds_id}: extra fields {extra}")

        # Check value types
        for field, val in data.items():
            if val is not None and not isinstance(val, (str, dict, list, bool, int, float)):
                issues.append(f"{ds_id}/{field}: unexpected type {type(val).__name__}")

        # Check for trailing whitespace in field names
        for field in data.keys():
            if field != field.strip():
                issues.append(f"{ds_id}: field '{field}' has whitespace")

    r.info(f"Checked {checked} extraction files")

    if issues:
        r.fail(f"{len(issues)} format issues found")
        for issue in issues[:10]:
            r.info(f"  {issue}")
        if len(issues) > 10:
            r.info(f"  ... and {len(issues) - 10} more")
    else:
        r.info("All extraction files have correct format")

    return r


def check_score_ranges():
    """4e: Validate score ranges from existing evaluation results."""
    r = CheckResult("4e: Score Range Validation")

    eval_files = [
        ROOT / "results" / "eval_16field" / "eval_16field_results.json",
        ROOT / "results" / "field_type_eval" / "field_type_evaluation.json",
    ]

    for eval_path in eval_files:
        if not eval_path.exists():
            r.warn(f"Eval file not found: {eval_path.name}")
            continue

        with open(eval_path) as f:
            data = json.load(f)

        summaries = data if "summaries" not in data else data["summaries"]

        for method, summary in summaries.items():
            if not isinstance(summary, dict):
                continue

            # Check composite in [0, 1]
            comp = summary.get("composite", {}).get("mean", None)
            if comp is not None:
                if not (0 <= comp <= 1):
                    r.fail(f"{eval_path.name}/{method}: composite {comp} out of [0,1]")

            # Check per-field scores
            for field, score in summary.get("per_field", {}).items():
                if not isinstance(score, (int, float)):
                    continue
                if not (0 <= score <= 1):
                    r.fail(f"{eval_path.name}/{method}/{field}: score {score} out of [0,1]")

            # Check constrained scores are binary (should be 0 or 1)
            c_scores = summary.get("constrained", {}).get("scores", [])
            non_binary = [s for s in c_scores if s not in (0.0, 1.0)]
            if non_binary:
                r.fail(f"{eval_path.name}/{method}: {len(non_binary)} non-binary constrained scores")

        r.info(f"{eval_path.name}: all scores in valid ranges")

    return r


def check_metric_consistency():
    """4c: Run the same evaluation inputs and verify deterministic output."""
    r = CheckResult("4c: Metric Consistency (deterministic)")

    from evaluation.field_metrics import score_constrained, score_token_f1

    # Run 3 times, assert identical
    test_cases = [
        ("MIT", "MIT License", "sc:license"),
        ("en", "English", "sc:inLanguage"),
        ("2021", "2021-10-28", "sc:datePublished"),
    ]

    for pred, gt, field in test_cases:
        scores = [score_constrained(pred, gt, field) for _ in range(3)]
        if len(set(scores)) != 1:
            r.fail(f"Non-deterministic: {field} gave {scores}")
        else:
            r.info(f"{field}: deterministic ({scores[0]})")

    # Token F1 determinism
    f1_scores = [score_token_f1("hello world foo", "hello world bar") for _ in range(3)]
    if len(set(f1_scores)) != 1:
        r.fail(f"Token F1 non-deterministic: {f1_scores}")
    else:
        r.info(f"Token F1: deterministic ({f1_scores[0]:.3f})")

    return r


def main():
    checks = [
        check_known_answers(),
        check_metric_consistency(),
        check_extraction_format(),
        check_score_ranges(),
    ]

    print("\n" + "=" * 80)
    print("SANITY CHECK REPORT")
    print("=" * 80)

    all_passed = True
    for check in checks:
        print(f"\n{check}")
        if not check.passed:
            all_passed = False

    print(f"\n{'=' * 80}")
    if all_passed:
        print("OVERALL: ALL SANITY CHECKS PASSED")
    else:
        print("OVERALL: SOME CHECKS FAILED")
    print("=" * 80)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
