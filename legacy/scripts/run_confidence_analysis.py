#!/usr/bin/env python3
"""
Self-consistency confidence scoring experiment.

Runs extraction 3x with temp=0.3, measures inter-run agreement,
and correlates with actual accuracy from error taxonomy.
"""

import sys
import json
import time
import re
from pathlib import Path
from collections import defaultdict, Counter

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE, MAX_PDF_CHARS
from metadata.extractor import setup_llm_pipeline, clean_llm_output
from pdf.reader import extract_text_from_pdf
from pdf.processor import clean_text
from croissantminer.confidence import compute_all_confidences
from evaluation.field_metrics import ALL_30_FIELDS, score_field, get_field_category

BENCHMARK_MAP = {
    "2012.03411v2": "MLS", "2009.03300v3": "MMLU", "2106.03193v1": "FLORES",
    "2404.00498v2": "CIFAR", "1405.0312v3": "MSCOCO", "2311.16502v4": "MMMU",
    "1602.07332v1": "Visual Genome", "2310.02255v3": "MathVista",
}

RAW_DIR = Path("data/raw")
OUT_DIR = Path("results/confidence_analysis")
GT_PATH = Path("data/groundtruth_30field/all_annotations.json")
N_RUNS = 3


def run_extractions():
    """Run extraction 3x with temp=0.3 for each dataset."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    model = setup_llm_pipeline("claude-sonnet-4-5", temperature=0.3)

    for pdf_id, ds_name in BENCHMARK_MAP.items():
        pdf_path = RAW_DIR / f"{pdf_id}.pdf"
        raw_text = extract_text_from_pdf(pdf_path)
        cleaned = clean_text(raw_text)[:MAX_PDF_CHARS]
        user_prompt = USER_PROMPT_TEMPLATE % cleaned

        for run in range(1, N_RUNS + 1):
            out_file = OUT_DIR / f"{ds_name}_run{run}.json"
            if out_file.exists():
                print(f"  {ds_name} run{run}: cached")
                continue

            print(f"  {ds_name} run{run}...", end=" ", flush=True)
            start = time.time()

            output = model.generate(user_prompt, system_prompt=SYSTEM_PROMPT)
            json_str = clean_llm_output(output, user_prompt)

            try:
                metadata = json.loads(json_str)
            except json.JSONDecodeError:
                metadata = {}
                for m in re.finditer(r'"([^"]+)"\s*:\s*null', json_str):
                    metadata[m.group(1)] = None
                for m in re.finditer(r'"([^"]+)"\s*:\s*"((?:[^"\\]|\\.)*)"', json_str):
                    metadata[m.group(1)] = m.group(2).replace('\\n', ' ').strip()

            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            print(f"{time.time()-start:.0f}s")


def analyze():
    """Analyze confidence vs actual accuracy."""
    import numpy as np

    with open(GT_PATH) as f:
        gt_all = json.load(f)

    # Load error taxonomy for hallucination correlation
    tax_file = Path("results/error_taxonomy/error_taxonomy.json")
    hallucination_fields = set()
    if tax_file.exists():
        with open(tax_file) as f:
            taxonomy = json.load(f)
        for err in taxonomy.get("errors", []):
            if err["error_type"] == "HALLUCINATION":
                hallucination_fields.add((err["dataset"], err["field"]))

    all_confidences = []
    confidence_vs_accuracy = {"high": [], "medium": [], "low": []}

    for ds_name in BENCHMARK_MAP.values():
        # Load 3 runs
        runs = []
        for run in range(1, N_RUNS + 1):
            f = OUT_DIR / f"{ds_name}_run{run}.json"
            if not f.exists():
                break
            with open(f) as fh:
                runs.append(json.load(fh))

        if len(runs) < N_RUNS:
            print(f"  {ds_name}: only {len(runs)} runs, skipping")
            continue

        # Compute confidence
        conf_results = compute_all_confidences(runs, ALL_30_FIELDS)

        # Get GT
        gt_ref = gt_all.get(ds_name, [{}])
        gt_ref = gt_ref[0] if isinstance(gt_ref, list) else gt_ref

        for field, conf in conf_results.items():
            gt_val = gt_ref.get(field) or gt_ref.get(field.split(":")[-1])

            # Score the majority-vote extraction against GT
            result = score_field(conf["value"], gt_val, field)

            is_hallucination = (ds_name, field) in hallucination_fields

            entry = {
                "dataset": ds_name,
                "field": field,
                "category": get_field_category(field),
                "confidence": conf["confidence"],
                "agreement": conf["agreement"],
                "flag": conf["flag"],
                "score": result["score"],
                "skipped": result["skipped"],
                "is_hallucination": is_hallucination,
                "raw_values": conf["raw_values"],
            }
            all_confidences.append(entry)

            if not result["skipped"] and result["score"] is not None:
                confidence_vs_accuracy[conf["agreement"]].append(result["score"])

    # ── RESULTS ──
    print(f"\n{'='*80}")
    print("CONFIDENCE DISTRIBUTION")
    print(f"{'='*80}")

    evaluated = [e for e in all_confidences if not e["skipped"]]
    agreement_counts = Counter(e["agreement"] for e in evaluated)

    print(f"\n  {'Agreement':<15} {'Count':>6} {'%':>6}")
    print(f"  {'-'*30}")
    for level in ["high", "medium", "low"]:
        count = agreement_counts.get(level, 0)
        pct = count / len(evaluated) * 100 if evaluated else 0
        print(f"  {level:<15} {count:>6} {pct:>5.0f}%")

    # Confidence vs accuracy
    print(f"\n{'='*80}")
    print("CONFIDENCE vs ACTUAL ACCURACY")
    print(f"{'='*80}")

    print(f"\n  {'Agreement':<15} {'n':>5} {'Mean score':>11} {'% correct':>10}")
    print(f"  {'-'*45}")
    for level in ["high", "medium", "low"]:
        scores = confidence_vs_accuracy[level]
        if scores:
            mean = np.mean(scores)
            correct = sum(1 for s in scores if s >= 0.8) / len(scores) * 100
            print(f"  {level:<15} {len(scores):>5} {mean:>10.3f} {correct:>9.0f}%")
        else:
            print(f"  {level:<15}     0      n/a       n/a")

    # Hallucination detection
    print(f"\n{'='*80}")
    print("HALLUCINATION DETECTION")
    print(f"{'='*80}")

    hall_entries = [e for e in evaluated if e["is_hallucination"]]
    non_hall = [e for e in evaluated if not e["is_hallucination"]]

    flagged_hall = [e for e in hall_entries if e["flag"] in ("likely_hallucination", "uncertain") or e["agreement"] == "low"]
    missed_hall = [e for e in hall_entries if e["agreement"] == "high" and e["flag"] == "none"]

    flagged_non_hall = [e for e in non_hall if e["flag"] in ("likely_hallucination", "uncertain") or e["agreement"] == "low"]

    print(f"\n  Total hallucination errors (from taxonomy): {len(hall_entries)}")
    print(f"  Flagged as low-confidence: {len(flagged_hall)} (true positives)")
    print(f"  Missed (high confidence): {len(missed_hall)} (false negatives)")
    print(f"  Non-hallucinations flagged low: {len(flagged_non_hall)} (false positives)")

    if hall_entries:
        precision = len(flagged_hall) / (len(flagged_hall) + len(flagged_non_hall)) * 100 if (len(flagged_hall) + len(flagged_non_hall)) > 0 else 0
        recall = len(flagged_hall) / len(hall_entries) * 100 if hall_entries else 0
        print(f"\n  Precision: {precision:.0f}%")
        print(f"  Recall: {recall:.0f}%")

    # Per-field confidence breakdown
    print(f"\n{'='*80}")
    print("FIELDS WITH LOWEST CONFIDENCE")
    print(f"{'='*80}")

    field_conf = defaultdict(list)
    for e in evaluated:
        field_conf[e["field"]].append(e["confidence"])

    print(f"\n  {'Field':<40} {'Avg conf':>9} {'Low%':>6}")
    print(f"  {'-'*58}")
    for field in sorted(field_conf, key=lambda f: np.mean(field_conf[f])):
        confs = field_conf[field]
        if len(confs) < 3:
            continue
        avg = np.mean(confs)
        low_pct = sum(1 for c in confs if c < 0.5) / len(confs) * 100
        if avg < 0.8:
            print(f"  {field:<40} {avg:>8.3f} {low_pct:>5.0f}%")

    # Save
    results = {
        "n_runs": N_RUNS,
        "n_datasets": len(BENCHMARK_MAP),
        "total_evaluated": len(evaluated),
        "agreement_distribution": dict(agreement_counts),
        "confidence_vs_accuracy": {
            level: {"n": len(scores), "mean": round(float(np.mean(scores)), 3) if scores else 0}
            for level, scores in confidence_vs_accuracy.items()
        },
        "hallucination_detection": {
            "total_hallucinations": len(hall_entries),
            "true_positives": len(flagged_hall),
            "false_negatives": len(missed_hall),
            "false_positives": len(flagged_non_hall),
        },
        "all_confidences": all_confidences,
    }
    with open(OUT_DIR / "confidence_analysis.json", "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)

    print(f"\nSaved to {OUT_DIR}/")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--analyze-only", action="store_true")
    args = parser.parse_args()

    print("=" * 60)
    print("SELF-CONSISTENCY CONFIDENCE ANALYSIS")
    print(f"({N_RUNS} runs per dataset, temperature=0.3)")
    print("=" * 60)

    if not args.analyze_only:
        print("\nStep 1: Running extractions...")
        run_extractions()

    print("\nStep 2: Analyzing confidence vs accuracy...")
    analyze()


if __name__ == "__main__":
    main()
