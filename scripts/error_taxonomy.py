#!/usr/bin/env python3
"""
Systematic error taxonomy for CroissantMiner extraction failures.

Classifies every imperfect extraction into:
  ABSENT_IN_SOURCE, HALLUCINATION, INCOMPLETE,
  GRANULARITY_MISMATCH, WRONG_SECTION, FORMAT_ERROR
"""

import sys
import json
import os
import re
import hashlib
from pathlib import Path
from collections import defaultdict, Counter

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from evaluation.field_metrics import (
    ALL_30_FIELDS, get_field_category, score_field,
    CONSTRAINED_FIELDS, SHORT_TEXT_FIELDS, LONG_TEXT_RAI_FIELDS,
)

GT_PATH = Path("data/groundtruth_30field/all_annotations.json")
EXTRACTION_DIR = Path("results/ablations/source_ablation/combined")
PAPER_ONLY_DIR = Path("evaluation_outputs_v2")
OUT_DIR = Path("results/error_taxonomy")

TAXONOMY = [
    "ABSENT_IN_SOURCE",
    "HALLUCINATION",
    "INCOMPLETE",
    "GRANULARITY_MISMATCH",
    "WRONG_SECTION",
    "FORMAT_ERROR",
]

CLASSIFY_PROMPT = """You are classifying a metadata extraction error. Given the ground truth value, the model's extraction, and the field name, classify the error into exactly ONE category.

Field: {field_name}
Ground truth: {gt_value}
Model extraction: {extraction_value}

Error categories:
1. HALLUCINATION — Model generated plausible but factually incorrect information not supported by any source
2. INCOMPLETE — Model found the right topic but extracted only partial information, missing important details
3. GRANULARITY_MISMATCH — Model extracted correct information but at wrong detail level (too general or too specific)
4. WRONG_SECTION — Model extracted information from the wrong part of the paper (e.g., general ML info instead of dataset-specific)
5. FORMAT_ERROR — Correct information but wrong format for the schema (e.g., date format, license identifier format)

Output ONLY the category name (one of: HALLUCINATION, INCOMPLETE, GRANULARITY_MISMATCH, WRONG_SECTION, FORMAT_ERROR)."""

# Cache for LLM classifications
_classify_cache = {}
_CACHE_FILE = OUT_DIR / "classify_cache.json"


def _load_cache():
    global _classify_cache
    if _CACHE_FILE.exists() and not _classify_cache:
        with open(_CACHE_FILE) as f:
            _classify_cache = json.load(f)


def _save_cache():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(_CACHE_FILE, "w") as f:
        json.dump(_classify_cache, f, indent=2, ensure_ascii=False)


def classify_error_llm(field_name, gt_value, extraction_value):
    """Use GPT-4o-mini to classify the error type."""
    _load_cache()

    cache_key = hashlib.md5(f"{field_name}::{gt_value[:200]}::{extraction_value[:200]}".encode()).hexdigest()
    if cache_key in _classify_cache:
        return _classify_cache[cache_key]

    prompt = CLASSIFY_PROMPT.format(
        field_name=field_name,
        gt_value=str(gt_value)[:500],
        extraction_value=str(extraction_value)[:500],
    )

    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=20,
        )
        answer = response.choices[0].message.content.strip().upper()
        # Extract known category
        for cat in TAXONOMY[1:]:  # Skip ABSENT_IN_SOURCE (handled separately)
            if cat in answer:
                _classify_cache[cache_key] = cat
                if len(_classify_cache) % 10 == 0:
                    _save_cache()
                return cat
        # Default
        _classify_cache[cache_key] = "INCOMPLETE"
        return "INCOMPLETE"
    except Exception as e:
        print(f"    Classification error: {e}")
        return "INCOMPLETE"


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load GT
    with open(GT_PATH) as f:
        gt_all = json.load(f)

    # Collect all errors
    errors = []
    total_evaluated = 0
    total_perfect = 0

    datasets = list(gt_all.keys())

    print("=" * 80)
    print("ERROR TAXONOMY ANALYSIS")
    print("=" * 80)

    for ds_name in sorted(datasets):
        gt_ref = gt_all[ds_name][0] if isinstance(gt_all[ds_name], list) else gt_all[ds_name]

        # Load extraction (prefer combined, fall back to paper-only)
        ext_file = EXTRACTION_DIR / f"{ds_name}_extraction.json"
        if not ext_file.exists():
            ext_file = PAPER_ONLY_DIR / f"{ds_name}_extraction.json"
        if not ext_file.exists():
            continue

        with open(ext_file) as f:
            extraction = json.load(f)

        print(f"\n  {ds_name}:")

        for field in ALL_30_FIELDS:
            # Get values
            gt_val = gt_ref.get(field) or gt_ref.get(field.split(":")[-1])
            short = field.split(":")[-1] if ":" in field else field
            ext_val = extraction.get(field) or extraction.get(short) or extraction.get(f"rai:{short}")

            # Score the field
            result = score_field(ext_val, gt_val, field)

            if result["skipped"]:
                continue

            total_evaluated += 1
            cat = get_field_category(field)

            # Define "imperfect" thresholds per category
            is_perfect = False
            if cat == "constrained" and result["score"] == 1.0:
                is_perfect = True
            elif cat == "short_text" and result["score"] >= 0.8:
                is_perfect = True
            elif cat == "rai" and result["raw_score"] is not None and result["raw_score"] >= 4:
                is_perfect = True

            if is_perfect:
                total_perfect += 1
                continue

            # ── Classify the error ──
            ext_str = str(ext_val).strip() if ext_val else ""
            gt_str = str(gt_val).strip() if gt_val else ""
            ext_empty = not ext_str or ext_str.lower() in ("null", "none", "")

            if ext_empty:
                # Model didn't extract anything but GT has value
                error_type = "ABSENT_IN_SOURCE"  # Conservative default
                reason = "Model returned null for a field with ground truth value"
            else:
                # Both have values — classify with LLM
                error_type = classify_error_llm(field, gt_str, ext_str)
                reason = f"LLM classified"

            errors.append({
                "dataset": ds_name,
                "field": field,
                "field_category": cat,
                "error_type": error_type,
                "score": result["score"],
                "raw_score": result["raw_score"],
                "gt_preview": gt_str[:100],
                "ext_preview": ext_str[:100] if ext_str else "null",
                "reason": reason,
            })

        n_errors = sum(1 for e in errors if e["dataset"] == ds_name)
        print(f"    {n_errors} errors found")

    _save_cache()

    # ── ANALYSIS ──
    print(f"\n{'='*80}")
    print("ERROR DISTRIBUTION")
    print(f"{'='*80}")

    error_counts = Counter(e["error_type"] for e in errors)
    total_errors = len(errors)

    print(f"\nTotal evaluated: {total_evaluated}")
    print(f"Perfect: {total_perfect} ({total_perfect/total_evaluated*100:.0f}%)")
    print(f"Errors: {total_errors} ({total_errors/total_evaluated*100:.0f}%)")

    print(f"\n{'Error Type':<25} {'Count':>6} {'%':>6}  Example")
    print("-" * 90)
    for cat in TAXONOMY:
        count = error_counts.get(cat, 0)
        pct = count / total_errors * 100 if total_errors else 0
        example = next((e for e in errors if e["error_type"] == cat), None)
        ex_str = ""
        if example:
            ex_str = f"{example['field']}: \"{example['ext_preview'][:40]}\" vs \"{example['gt_preview'][:40]}\""
        print(f"{cat:<25} {count:>6} {pct:>5.0f}%  {ex_str}")

    # By field category
    print(f"\n{'='*80}")
    print("ERRORS BY FIELD CATEGORY")
    print(f"{'='*80}")

    for fcat in ["constrained", "short_text", "rai"]:
        cat_errors = [e for e in errors if e["field_category"] == fcat]
        if not cat_errors:
            continue
        print(f"\n  {fcat.upper()} ({len(cat_errors)} errors):")
        cat_dist = Counter(e["error_type"] for e in cat_errors)
        for etype, count in cat_dist.most_common():
            print(f"    {etype:<25} {count:>3} ({count/len(cat_errors)*100:.0f}%)")

    # Most error-prone fields
    print(f"\n{'='*80}")
    print("MOST ERROR-PRONE FIELDS (>= 3 errors)")
    print(f"{'='*80}")

    field_errors = defaultdict(list)
    for e in errors:
        field_errors[e["field"]].append(e["error_type"])

    print(f"\n{'Field':<40} {'Errors':>6} {'Dominant type':<25}")
    print("-" * 75)
    for field in sorted(field_errors, key=lambda f: len(field_errors[f]), reverse=True):
        errs = field_errors[field]
        if len(errs) < 3:
            continue
        dominant = Counter(errs).most_common(1)[0]
        print(f"{field:<40} {len(errs):>6} {dominant[0]} ({dominant[1]}x)")

    # Actionable insights
    print(f"\n{'='*80}")
    print("ACTIONABLE INSIGHTS")
    print(f"{'='*80}")

    insights = {
        "ABSENT_IN_SOURCE": "Better source coverage (web search, multiple card sources), or accept null as valid",
        "HALLUCINATION": "Constrained decoding, schema validation, confidence thresholds, null preference in prompts",
        "INCOMPLETE": "Multi-pass extraction, chain-of-thought prompting, longer context windows",
        "GRANULARITY_MISMATCH": "Schema-aware post-processing, standardization layer (SPDX for licenses, ISO for dates)",
        "WRONG_SECTION": "Section-aware extraction, improved field boundary definitions in prompts",
        "FORMAT_ERROR": "Output validators, format-specific post-processing (date parser, license normalizer)",
    }
    for etype in TAXONOMY:
        count = error_counts.get(etype, 0)
        if count > 0:
            print(f"\n  {etype} ({count} errors):")
            print(f"    Fix: {insights[etype]}")

    # Save results
    results = {
        "summary": {
            "total_evaluated": total_evaluated,
            "total_perfect": total_perfect,
            "total_errors": total_errors,
            "perfect_rate": round(total_perfect / total_evaluated * 100, 1),
        },
        "error_distribution": {cat: error_counts.get(cat, 0) for cat in TAXONOMY},
        "errors": errors,
    }
    with open(OUT_DIR / "error_taxonomy.json", "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Markdown report
    md = f"""# Error Taxonomy Analysis

## Summary
- Total field-dataset pairs evaluated: {total_evaluated}
- Perfect extractions: {total_perfect} ({total_perfect/total_evaluated*100:.0f}%)
- Errors: {total_errors} ({total_errors/total_evaluated*100:.0f}%)

## Error Distribution

| Error Type | Count | % | Fix |
|------------|-------|---|-----|
"""
    for cat in TAXONOMY:
        count = error_counts.get(cat, 0)
        pct = count / total_errors * 100 if total_errors else 0
        md += f"| {cat} | {count} | {pct:.0f}% | {insights[cat]} |\n"

    with open(OUT_DIR / "error_taxonomy_report.md", "w") as f:
        f.write(md)

    print(f"\nSaved to {OUT_DIR}/")


if __name__ == "__main__":
    main()
