"""
Composite field-type-aware evaluator for CroissantMiner.

Applies appropriate metrics to each field type:
  Constrained → exact match after normalization
  Short-text → token-level F1
  RAI long-text → LLM-as-judge (1-5 scale)
"""

import json
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict

from .field_metrics import (
    score_field, finalize_cache, get_field_category,
    ALL_30_FIELDS, CONSTRAINED_FIELDS, SHORT_TEXT_FIELDS, LONG_TEXT_RAI_FIELDS,
)


def evaluate_dataset(
    predicted: Dict[str, str],
    groundtruth: Dict[str, str],
    dataset_name: str,
) -> Dict:
    """Evaluate all 30 fields for a single dataset using field-type-aware metrics."""
    results = {}

    for field in ALL_30_FIELDS:
        # Look up values with prefix fallback
        pred = predicted.get(field)
        if pred is None:
            short = field.split(":")[-1] if ":" in field else field
            pred = predicted.get(short) or predicted.get(f"rai:{short}")

        gt = groundtruth.get(field)
        if gt is None:
            short = field.split(":")[-1] if ":" in field else field
            gt = groundtruth.get(short)

        result = score_field(pred, gt, field)
        results[field] = result

    return results


def evaluate_method(
    extraction_dir: str,
    gt_path: str,
    method_name: str,
) -> Dict:
    """Evaluate a full method across all datasets."""

    # Load GT
    with open(gt_path) as f:
        gt_all = json.load(f)

    # Benchmark dataset mapping
    BENCHMARK_PDF_MAP = {
        "2012.03411v2": "MLS", "2009.03300v3": "MMLU", "2106.03193v1": "FLORES",
        "2404.00498v2": "CIFAR", "1405.0312v3": "MSCOCO", "2311.16502v4": "MMMU",
        "1602.07332v1": "Visual Genome", "2310.02255v3": "MathVista",
    }

    ext_dir = Path(extraction_dir)
    all_results = {}

    for ds_name in gt_all:
        # Find extraction file
        ext_file = None
        for name in [f"{ds_name}_extraction.json", f"{ds_name.lower()}_extraction.json"]:
            candidate = ext_dir / name
            if candidate.exists():
                ext_file = candidate
                break

        if not ext_file:
            continue

        with open(ext_file) as f:
            predicted = json.load(f)

        gt_ref = gt_all[ds_name][0] if isinstance(gt_all[ds_name], list) else gt_all[ds_name]
        results = evaluate_dataset(predicted, gt_ref, ds_name)
        all_results[ds_name] = results

    finalize_cache()
    return all_results


def compute_summary(all_results: Dict) -> Dict:
    """Compute summary statistics from per-dataset results."""
    # Per-category aggregation
    cat_scores = defaultdict(list)  # category -> [scores]
    field_scores = defaultdict(list)  # field -> [scores]
    ds_scores = {}  # dataset -> composite score

    for ds_name, field_results in all_results.items():
        ds_evaluated = []

        for field, result in field_results.items():
            if result["skipped"]:
                continue

            cat = result["category"]
            score = result["score"]
            cat_scores[cat].append(score)
            field_scores[field].append(score)
            ds_evaluated.append(score)

        ds_scores[ds_name] = np.mean(ds_evaluated) if ds_evaluated else 0

    # Summary
    constrained = cat_scores.get("constrained", [])
    short_text = cat_scores.get("short_text", [])
    rai = cat_scores.get("rai", [])
    all_scores = constrained + short_text + rai

    # RAI raw scores (1-5 scale) for display
    rai_raw = []
    for ds_results in all_results.values():
        for field, result in ds_results.items():
            if result["category"] == "rai" and not result["skipped"]:
                rai_raw.append(result["raw_score"])

    return {
        "constrained": {
            "n": len(constrained),
            "mean": float(np.mean(constrained)) if constrained else 0,
            "scores": constrained,
        },
        "short_text": {
            "n": len(short_text),
            "mean": float(np.mean(short_text)) if short_text else 0,
            "scores": short_text,
        },
        "rai": {
            "n": len(rai),
            "mean": float(np.mean(rai)) if rai else 0,
            "mean_1_5": float(np.mean(rai_raw)) if rai_raw else 0,
            "scores": rai,
        },
        "composite": {
            "n": len(all_scores),
            "mean": float(np.mean(all_scores)) if all_scores else 0,
        },
        "per_dataset": {ds: float(s) for ds, s in ds_scores.items()},
        "per_field": {f: float(np.mean(s)) for f, s in field_scores.items() if s},
    }


def generate_report(results_by_method: Dict[str, Dict], output_dir: str):
    """Generate markdown, LaTeX, and JSON reports."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    summaries = {}
    for method, all_results in results_by_method.items():
        summaries[method] = compute_summary(all_results)

    # ── Console + Markdown ──
    lines = []
    lines.append("# Field-Type-Aware Evaluation Results\n")

    # Main table
    header = f"{'Method':<22} {'Constrained(EM)':>16} {'Short-text(F1)':>15} {'RAI(Judge)':>12} {'Composite':>10}"
    sep = "-" * 80
    lines.append(f"## Main Comparison\n")
    lines.append(f"| Method | Constrained (EM) | Short-text (F1) | RAI (Judge 1-5) | Composite |")
    lines.append(f"|--------|-----------------|----------------|----------------|-----------|")

    print(f"\n{'='*80}")
    print("FIELD-TYPE-AWARE EVALUATION")
    print(f"{'='*80}\n")
    print(header)
    print(sep)

    for method in summaries:
        s = summaries[method]
        c = s["constrained"]["mean"] * 100
        st = s["short_text"]["mean"]
        r = s["rai"]["mean_1_5"]
        comp = s["composite"]["mean"] * 100
        n_c = s["constrained"]["n"]
        n_st = s["short_text"]["n"]
        n_r = s["rai"]["n"]

        print(f"{method:<22} {c:>10.1f}% ({n_c:>2}) {st:>10.3f} ({n_st:>2}) {r:>7.2f}/5 ({n_r:>2}) {comp:>9.1f}%")
        lines.append(f"| {method} | {c:.1f}% (n={n_c}) | {st:.3f} (n={n_st}) | {r:.2f}/5 (n={n_r}) | {comp:.1f}% |")

    # Per-dataset
    lines.append(f"\n## Per-Dataset Composite Scores\n")
    lines.append(f"| Dataset | " + " | ".join(summaries.keys()) + " |")
    lines.append(f"|---------|" + "|".join(["------" for _ in summaries]) + "|")

    print(f"\n{'='*80}")
    print("PER-DATASET COMPOSITE")
    print(f"{'='*80}\n")

    datasets = sorted(set(ds for s in summaries.values() for ds in s["per_dataset"]))
    for ds in datasets:
        row = f"| {ds} |"
        print_parts = [f"{ds:<20}"]
        for method in summaries:
            val = summaries[method]["per_dataset"].get(ds, 0) * 100
            row += f" {val:.1f}% |"
            print_parts.append(f"{val:>7.1f}%")
        lines.append(row)
        print("  ".join(print_parts))

    # Per-field for Claude (if present)
    claude_key = next((k for k in summaries if "Claude" in k or "claude" in k), None)
    if claude_key:
        lines.append(f"\n## Per-Field Breakdown ({claude_key})\n")
        lines.append(f"| Field | Category | Metric | Score | n |")
        lines.append(f"|-------|----------|--------|-------|---|")

        print(f"\n{'='*80}")
        print(f"PER-FIELD BREAKDOWN ({claude_key})")
        print(f"{'='*80}\n")
        print(f"{'Field':<40} {'Cat':<12} {'Metric':<10} {'Score':>7} {'n':>3}")
        print("-" * 75)

        for field in ALL_30_FIELDS:
            cat = get_field_category(field)
            scores = summaries[claude_key]["per_field"].get(field)
            if scores is not None:
                # Count how many datasets had this field evaluated
                n = sum(1 for ds_res in results_by_method[claude_key].values()
                        if field in ds_res and not ds_res[field]["skipped"])
                metric = {"constrained": "EM", "short_text": "F1", "rai": "Judge"}[cat]
                score_str = f"{scores:.3f}"
                print(f"{field:<40} {cat:<12} {metric:<10} {score_str:>7} {n:>3}")
                lines.append(f"| {field} | {cat} | {metric} | {score_str} | {n} |")
            else:
                print(f"{field:<40} {'—':<12} {'—':<10} {'skip':>7}")

    # ── LaTeX ──
    latex = []
    latex.append(r"\begin{table}[h]")
    latex.append(r"\centering")
    latex.append(r"\caption{Field-type-aware evaluation on 30-field benchmark (8 datasets).}")
    latex.append(r"\begin{tabular}{lcccc}")
    latex.append(r"\toprule")
    latex.append(r"Method & Constrained (EM) & Short-text (F1) & RAI (Judge) & Composite \\")
    latex.append(r"\midrule")

    for method in summaries:
        s = summaries[method]
        c = s["constrained"]["mean"] * 100
        st = s["short_text"]["mean"]
        r = s["rai"]["mean_1_5"]
        comp = s["composite"]["mean"] * 100

        best_comp = max(ss["composite"]["mean"] for ss in summaries.values())
        comp_str = f"\\textbf{{{comp:.1f}\\%}}" if s["composite"]["mean"] == best_comp else f"{comp:.1f}\\%"

        latex.append(f"{method} & {c:.1f}\\% & {st:.3f} & {r:.2f}/5 & {comp_str} \\\\")

    latex.append(r"\bottomrule")
    latex.append(r"\end{tabular}")
    latex.append(r"\end{table}")

    # Save all
    with open(out / "field_type_report.md", "w") as f:
        f.write("\n".join(lines))

    with open(out / "latex_tables.tex", "w") as f:
        f.write("\n".join(latex))

    with open(out / "field_type_evaluation.json", "w") as f:
        # Save summaries (not raw results — too large)
        json.dump(summaries, f, indent=2, default=str)

    print(f"\n\nSaved to {out}/")
    print(f"  field_type_evaluation.json")
    print(f"  field_type_report.md")
    print(f"  latex_tables.tex")
