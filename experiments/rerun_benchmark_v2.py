#!/usr/bin/env python3
"""
Re-run extraction on 8 benchmark datasets with updated prompts (v2).
Saves results to evaluation_outputs_v2/ to avoid overwriting originals.
Then runs LLM-as-judge evaluation and compares before vs after.

Usage:
    python scripts/rerun_benchmark_v2.py
    python scripts/rerun_benchmark_v2.py --eval-only   # skip extraction, just evaluate
    python scripts/rerun_benchmark_v2.py --compare-only # skip both, just compare
"""

import sys
import json
import time
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE, MAX_PDF_CHARS
from pdf.reader import extract_text_from_pdf
from pdf.processor import clean_text
from metadata.extractor import setup_llm_pipeline, clean_llm_output

# 8 benchmark datasets: arxiv PDF ID -> evaluation dataset name
BENCHMARK_MAP = {
    "2012.03411v2": "MLS",
    "2009.03300v3": "MMLU",
    "2106.03193v1": "FLORES",
    "2404.00498v2": "CIFAR",
    "1405.0312v3": "MSCOCO",
    "2311.16502v4": "MMMU",
    "1602.07332v1": "Visual Genome",
    "2310.02255v3": "MathVista",
}

RAW_DIR = Path("data/raw")
OUTPUT_DIR = Path("evaluation_outputs_v2")
OLD_DIR = Path("evaluation_outputs")


def run_extractions():
    """Re-extract metadata for all 8 benchmark datasets."""
    OUTPUT_DIR.mkdir(exist_ok=True)

    model = setup_llm_pipeline("claude-sonnet-4-5")

    results_summary = []
    for pdf_id, ds_name in BENCHMARK_MAP.items():
        pdf_path = RAW_DIR / f"{pdf_id}.pdf"
        if not pdf_path.exists():
            print(f"  SKIP {ds_name}: PDF not found at {pdf_path}")
            continue

        print(f"\n{'='*60}")
        print(f"Extracting: {ds_name} ({pdf_id}.pdf)")
        print(f"{'='*60}")

        start = time.time()

        # Extract text
        raw_text = extract_text_from_pdf(pdf_path)
        cleaned = clean_text(raw_text)
        if len(cleaned) > MAX_PDF_CHARS:
            cleaned = cleaned[:MAX_PDF_CHARS]

        # Build prompt with updated system prompt
        user_prompt = USER_PROMPT_TEMPLATE % cleaned

        # Call LLM
        output = model.generate(user_prompt, system_prompt=SYSTEM_PROMPT)
        json_str = clean_llm_output(output, user_prompt)

        # Parse and save
        try:
            metadata = json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"  JSON parse error: {e}")
            metadata = {}

        out_file = OUTPUT_DIR / f"{ds_name}_extraction.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        elapsed = time.time() - start
        print(f"  Saved to {out_file} ({elapsed:.1f}s)")
        results_summary.append({"dataset": ds_name, "time": round(elapsed, 1), "fields": len(metadata)})

    # Save summary
    with open(OUTPUT_DIR / "extraction_summary.json", "w") as f:
        json.dump(results_summary, f, indent=2)

    print(f"\n{'='*60}")
    print(f"All extractions complete. Results in {OUTPUT_DIR}/")
    print(f"{'='*60}")


def run_evaluation():
    """Run LLM-as-judge evaluation on v2 extractions."""
    from evaluation.evaluator import batch_evaluate
    from evaluation.groundtruth_parser_md import parse_markdown_groundtruth

    print(f"\n{'='*60}")
    print("Running LLM-as-judge evaluation on v2 extractions")
    print(f"{'='*60}")

    # Parse groundtruth
    md_path = "groundtruth/Croissant_Dataset_Annotations.md"
    gt_dir = "groundtruth/parsed_md_filtered"
    parse_markdown_groundtruth(md_path, output_dir=gt_dir)

    # Run evaluation
    output_file = str(OUTPUT_DIR / "evaluation_report_v2.json")
    results = batch_evaluate(
        extraction_outputs_dir=str(OUTPUT_DIR),
        groundtruth_dir=gt_dir,
        output_file=output_file,
        verbose=True,
        use_llm=True
    )

    print(f"\nEvaluation saved to {output_file}")
    return results


def compare_results():
    """Compare v1 vs v2 results field by field."""
    old_path = OLD_DIR / "evaluation_report_full_pdf.json"
    new_path = OUTPUT_DIR / "evaluation_report_v2.json"

    if not old_path.exists():
        print(f"Old results not found: {old_path}")
        return
    if not new_path.exists():
        print(f"New results not found: {new_path}")
        return

    with open(old_path) as f:
        old = json.load(f)
    with open(new_path) as f:
        new = json.load(f)

    # Collect per-field scores across all datasets
    target_fields = [
        "rai:dataReleaseMaintenancePlan",
        "sc:datePublished",
        "rai:dataBiases",
        "rai:dataAnnotationProtocol",
        "sc:creator",
    ]

    # Build field -> [scores] for old and new
    old_field_scores = {}
    new_field_scores = {}
    old_ds_acc = {}
    new_ds_acc = {}

    for ds_name in old["results"]:
        old_ds_acc[ds_name] = old["results"][ds_name]["metrics"]["overall_stats"]["llm_accuracy"]
        for field, result in old["results"][ds_name]["metrics"]["field_results"].items():
            old_field_scores.setdefault(field, []).append(result["score"])

    for ds_name in new["results"]:
        new_ds_acc[ds_name] = new["results"][ds_name]["metrics"]["overall_stats"]["llm_accuracy"]
        for field, result in new["results"][ds_name]["metrics"]["field_results"].items():
            new_field_scores.setdefault(field, []).append(result["score"])

    # ── TARGET FIELDS COMPARISON ──
    print(f"\n{'='*80}")
    print("TARGET FIELDS: BEFORE vs AFTER PROMPT IMPROVEMENT")
    print(f"{'='*80}")
    print(f"\n{'Field':<35} {'Before':>8} {'After':>8} {'Delta':>8} {'Status'}")
    print("-" * 75)

    for field in target_fields:
        old_scores = old_field_scores.get(field, [])
        new_scores = new_field_scores.get(field, [])
        old_acc = sum(1 for s in old_scores if s >= 1.0) / len(old_scores) * 100 if old_scores else 0
        new_acc = sum(1 for s in new_scores if s >= 1.0) / len(new_scores) * 100 if new_scores else 0
        delta = new_acc - old_acc
        status = "IMPROVED" if delta > 0 else "SAME" if delta == 0 else "REGRESSED"
        marker = "+" if delta > 0 else "" if delta == 0 else ""
        print(f"{field:<35} {old_acc:>7.1f}% {new_acc:>7.1f}% {marker}{delta:>+7.1f}pp  {status}")

    # Overall
    old_all = [s for scores in old_field_scores.values() for s in scores]
    new_all = [s for scores in new_field_scores.values() for s in scores]
    old_overall = sum(s for s in old_all) / len(old_all) * 100 if old_all else 0
    new_overall = sum(s for s in new_all) / len(new_all) * 100 if new_all else 0
    delta_overall = new_overall - old_overall
    print("-" * 75)
    print(f"{'OVERALL (weighted)':<35} {old_overall:>7.1f}% {new_overall:>7.1f}% {delta_overall:>+7.1f}pp")

    # ── ALL FIELDS — REGRESSION CHECK ──
    print(f"\n{'='*80}")
    print("ALL 30 FIELDS: REGRESSION CHECK")
    print(f"{'='*80}")
    print(f"\n{'Field':<40} {'Before':>8} {'After':>8} {'Delta':>8}")
    print("-" * 70)

    all_fields = sorted(set(list(old_field_scores.keys()) + list(new_field_scores.keys())))
    regressions = []
    improvements = []

    for field in all_fields:
        old_scores = old_field_scores.get(field, [])
        new_scores = new_field_scores.get(field, [])
        old_acc = sum(s for s in old_scores) / len(old_scores) * 100 if old_scores else 0
        new_acc = sum(s for s in new_scores) / len(new_scores) * 100 if new_scores else 0
        delta = new_acc - old_acc
        marker = ""
        if delta < -5:
            marker = " ◄ REGRESSION"
            regressions.append((field, old_acc, new_acc, delta))
        elif delta > 5:
            marker = " ★ IMPROVED"
            improvements.append((field, old_acc, new_acc, delta))
        print(f"{field:<40} {old_acc:>7.1f}% {new_acc:>7.1f}% {delta:>+7.1f}pp{marker}")

    print(f"\nSummary: {len(improvements)} improved, {len(regressions)} regressed, {len(all_fields) - len(improvements) - len(regressions)} unchanged")

    # ── PER-DATASET COMPARISON ──
    print(f"\n{'='*80}")
    print("PER-DATASET ACCURACY")
    print(f"{'='*80}")
    print(f"\n{'Dataset':<20} {'Before':>8} {'After':>8} {'Delta':>8}")
    print("-" * 50)

    for ds in sorted(set(list(old_ds_acc.keys()) + list(new_ds_acc.keys()))):
        o = old_ds_acc.get(ds, 0) * 100
        n = new_ds_acc.get(ds, 0) * 100
        d = n - o
        print(f"{ds:<20} {o:>7.1f}% {n:>7.1f}% {d:>+7.1f}pp")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval-only", action="store_true", help="Skip extraction, only evaluate")
    parser.add_argument("--compare-only", action="store_true", help="Skip extraction and evaluation, only compare")
    args = parser.parse_args()

    if args.compare_only:
        compare_results()
        return

    if not args.eval_only:
        run_extractions()

    run_evaluation()
    compare_results()


if __name__ == "__main__":
    main()
