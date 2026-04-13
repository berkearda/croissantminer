#!/usr/bin/env python3
"""
16-field evaluation for CroissantMiner NeurIPS 2026 D&B paper.

Evaluates ONLY the 16 fields with validated ground truth (10 General + 6 RAI).
Uses existing extraction outputs — no re-extraction.

Methods evaluated:
  1. Claude Sonnet 4.5 (combined)
  2. GPT-4o-mini (combined)
  3. HF Auto-Croissant baseline
  4. Source ablation: paper-only, card-only, combined
  5. Bootstrap 95% CIs for all methods
"""

import json
import sys
import numpy as np
from pathlib import Path
from collections import defaultdict

# Add project root to path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from evaluation.config_16field import (
    ALL_16_FIELDS, CONSTRAINED_FIELDS_16, SHORT_TEXT_FIELDS_16,
    RAI_JUDGE_FIELDS_16, BENCHMARK_DATASETS,
)
from evaluation.field_metrics import (
    score_field, finalize_cache, get_field_category,
    score_constrained, score_token_f1, score_llm_judge,
)

# ═══════════════════════════════════════════════════════════════════════
# Paths
# ═══════════════════════════════════════════════════════════════════════

GT_PATH = ROOT / "data" / "groundtruth_30field" / "all_annotations.json"
CLAUDE_DIR = ROOT / "evaluation_outputs_v2"
GPT_DIR = ROOT / "results" / "gpt4o_mini"
HF_DIR = ROOT / "data" / "baselines" / "hf_croissant_mapped"
ABLATION_DIR = ROOT / "results" / "ablations" / "source_ablation"
OUTPUT_DIR = ROOT / "results" / "eval_16field"


def load_gt():
    """Load ground truth, using first annotator for each dataset."""
    with open(GT_PATH) as f:
        gt_all = json.load(f)
    gt = {}
    for ds in BENCHMARK_DATASETS:
        if ds in gt_all:
            entries = gt_all[ds]
            gt[ds] = entries[0] if isinstance(entries, list) else entries
    return gt


def load_extraction(ext_dir: Path, ds_name: str) -> dict:
    """Load extraction output for a dataset, trying common name patterns."""
    for name in [f"{ds_name}_extraction.json", f"{ds_name}.json",
                 f"{ds_name.lower()}_extraction.json", f"{ds_name.lower()}.json"]:
        path = ext_dir / name
        if path.exists():
            with open(path) as f:
                return json.load(f)
    return None


def resolve_field(data: dict, field: str):
    """Get field value with prefix fallback (sc:name → name, rai:X → X)."""
    val = data.get(field)
    if val is not None:
        return val
    # Try without prefix
    short = field.split(":")[-1] if ":" in field else field
    val = data.get(short)
    if val is not None:
        return val
    # Try with rai: prefix if not already
    if not field.startswith("rai:"):
        val = data.get(f"rai:{short}")
    return val


def get_category_16(field: str) -> str:
    """Return category for 16-field evaluation."""
    if field in CONSTRAINED_FIELDS_16:
        return "constrained"
    if field in SHORT_TEXT_FIELDS_16:
        return "short_text"
    if field in RAI_JUDGE_FIELDS_16:
        return "rai"
    return "unknown"


def evaluate_16fields(predicted: dict, gt_entry: dict, ds_name: str) -> list:
    """Evaluate 16 fields for a single dataset. Returns list of result dicts."""
    results = []
    for field in ALL_16_FIELDS:
        pred = resolve_field(predicted, field)
        gt_val = resolve_field(gt_entry, field)

        # Use existing score_field which handles null/unknown logic
        result = score_field(
            str(pred) if pred is not None else None,
            str(gt_val) if gt_val is not None else None,
            field,
        )
        result["dataset"] = ds_name
        results.append(result)
    return results


def evaluate_method(method_name: str, ext_dir: Path, gt: dict) -> list:
    """Evaluate a method across all datasets. Returns flat list of results."""
    all_results = []
    for ds in BENCHMARK_DATASETS:
        if ds not in gt:
            continue
        predicted = load_extraction(ext_dir, ds)
        if predicted is None:
            print(f"  ⚠ {method_name}: no extraction for {ds}")
            continue
        results = evaluate_16fields(predicted, gt[ds], ds)
        all_results.extend(results)
    return all_results


def compute_summary(results: list) -> dict:
    """Compute per-category and composite summary from results list."""
    cat_scores = defaultdict(list)
    field_scores = defaultdict(list)
    ds_scores = defaultdict(list)

    for r in results:
        if r["skipped"]:
            continue
        cat = get_category_16(r["field"])
        cat_scores[cat].append(r["score"])
        field_scores[r["field"]].append(r["score"])
        ds_scores[r["dataset"]].append(r["score"])

    # RAI raw scores (1-5) for display
    rai_raw = [r["raw_score"] for r in results
               if get_category_16(r["field"]) == "rai" and not r["skipped"]]

    constrained = cat_scores.get("constrained", [])
    short_text = cat_scores.get("short_text", [])
    rai = cat_scores.get("rai", [])
    all_scores = constrained + short_text + rai

    return {
        "constrained": {
            "n": len(constrained),
            "mean": float(np.mean(constrained)) if constrained else 0,
        },
        "short_text": {
            "n": len(short_text),
            "mean": float(np.mean(short_text)) if short_text else 0,
        },
        "rai": {
            "n": len(rai),
            "mean": float(np.mean(rai)) if rai else 0,
            "mean_1_5": float(np.mean(rai_raw)) if rai_raw else 0,
        },
        "composite": {
            "n": len(all_scores),
            "mean": float(np.mean(all_scores)) if all_scores else 0,
        },
        "per_dataset": {ds: float(np.mean(s)) for ds, s in ds_scores.items()},
        "per_field": {f: float(np.mean(s)) for f, s in field_scores.items()},
    }


def bootstrap_ci(results: list, n_boot=2000, ci=0.95) -> tuple:
    """Bootstrap 95% CI for composite score."""
    scores = [r["score"] for r in results if not r["skipped"]]
    if not scores:
        return (0, 0, 0)
    scores = np.array(scores)
    rng = np.random.default_rng(42)
    boot_means = []
    for _ in range(n_boot):
        sample = rng.choice(scores, size=len(scores), replace=True)
        boot_means.append(np.mean(sample))
    boot_means = np.sort(boot_means)
    alpha = (1 - ci) / 2
    lo = float(boot_means[int(alpha * n_boot)])
    hi = float(boot_means[int((1 - alpha) * n_boot)])
    return float(np.mean(scores)), lo, hi


# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    gt = load_gt()
    print(f"Loaded GT for {len(gt)} datasets")
    print(f"Evaluating {len(ALL_16_FIELDS)} fields\n")

    # ── Evaluate all methods ──
    methods = {}

    # 1. Claude Sonnet 4.5
    print("Evaluating Claude Sonnet 4.5...")
    methods["Claude Sonnet 4.5"] = evaluate_method("Claude Sonnet 4.5", CLAUDE_DIR, gt)

    # 2. GPT-4o-mini
    print("Evaluating GPT-4o-mini...")
    methods["GPT-4o-mini"] = evaluate_method("GPT-4o-mini", GPT_DIR, gt)

    # 3. HF Auto-Croissant
    print("Evaluating HF Auto-Croissant...")
    methods["HF Auto-Croissant"] = evaluate_method("HF Auto-Croissant", HF_DIR, gt)

    # 4. Source ablation
    print("Evaluating source ablation...")
    for source in ["paper_only", "card_only", "combined"]:
        label = source.replace("_", " ").title()
        abl_dir = ABLATION_DIR / source
        if abl_dir.exists():
            methods[f"Ablation: {label}"] = evaluate_method(f"Ablation: {label}", abl_dir, gt)

    finalize_cache()

    # ── Compute summaries and CIs ──
    summaries = {}
    cis = {}
    for name, results in methods.items():
        summaries[name] = compute_summary(results)
        mean, lo, hi = bootstrap_ci(results)
        cis[name] = {"mean": mean, "ci_lo": lo, "ci_hi": hi}

    # ── Print main results table ──
    print(f"\n{'='*100}")
    print("16-FIELD EVALUATION RESULTS (10 General + 6 RAI)")
    print(f"{'='*100}\n")

    header = f"{'Method':<24} {'Constrained(7)':>15} {'Short-text(3)':>14} {'RAI Judge(6)':>14} {'Composite':>12} {'95% CI':>16} {'N':>5}"
    print(header)
    print("-" * 100)

    main_methods = ["Claude Sonnet 4.5", "GPT-4o-mini", "HF Auto-Croissant"]
    for name in main_methods:
        if name not in summaries:
            continue
        s = summaries[name]
        ci = cis[name]
        c_pct = s["constrained"]["mean"] * 100
        st_f1 = s["short_text"]["mean"]
        rai_15 = s["rai"]["mean_1_5"]
        comp = s["composite"]["mean"] * 100
        n_eval = s["composite"]["n"]
        ci_str = f"[{ci['ci_lo']*100:.1f}, {ci['ci_hi']*100:.1f}]"
        print(f"{name:<24} {c_pct:>10.1f}% ({s['constrained']['n']:>2}) "
              f"{st_f1:>9.3f} ({s['short_text']['n']:>2}) "
              f"{rai_15:>8.2f}/5 ({s['rai']['n']:>2}) "
              f"{comp:>8.1f}% {ci_str:>16} {n_eval:>5}")

    # ── Source ablation table ──
    print(f"\n{'='*100}")
    print("SOURCE ABLATION")
    print(f"{'='*100}\n")

    abl_keys = [k for k in summaries if k.startswith("Ablation:")]
    if abl_keys:
        print(f"{'Source':<24} {'Composite':>12} {'95% CI':>16}")
        print("-" * 55)
        for name in abl_keys:
            s = summaries[name]
            ci = cis[name]
            comp = s["composite"]["mean"] * 100
            ci_str = f"[{ci['ci_lo']*100:.1f}, {ci['ci_hi']*100:.1f}]"
            short = name.replace("Ablation: ", "")
            print(f"{short:<24} {comp:>8.1f}% {ci_str:>16}")

    # ── AAAI comparison ──
    if "Claude Sonnet 4.5" in summaries:
        claude_comp = summaries["Claude Sonnet 4.5"]["composite"]["mean"] * 100
        aaai_overall = 59.4  # Mistral 7B from AAAI paper
        delta = claude_comp - aaai_overall
        print(f"\n{'='*100}")
        print("COMPARISON WITH AAAI PAPER (Mistral 7B)")
        print(f"{'='*100}\n")
        print(f"  AAAI (Mistral 7B):     {aaai_overall:.1f}%")
        print(f"  NeurIPS (Claude 4.5):  {claude_comp:.1f}%")
        print(f"  Delta:                 +{delta:.1f}pp")

    # ── Per-field breakdown for Claude ──
    if "Claude Sonnet 4.5" in summaries:
        print(f"\n{'='*100}")
        print("PER-FIELD BREAKDOWN (Claude Sonnet 4.5)")
        print(f"{'='*100}\n")
        print(f"{'Field':<40} {'Category':<12} {'Metric':<8} {'Score':>8} {'n':>4}")
        print("-" * 75)

        s = summaries["Claude Sonnet 4.5"]
        for field in ALL_16_FIELDS:
            cat = get_category_16(field)
            if field in s["per_field"]:
                score = s["per_field"][field]
                n = sum(1 for r in methods["Claude Sonnet 4.5"]
                        if r["field"] == field and not r["skipped"])
                metric = {"constrained": "EM", "short_text": "F1", "rai": "Judge"}[cat]
                print(f"{field:<40} {cat:<12} {metric:<8} {score:>8.3f} {n:>4}")
            else:
                print(f"{field:<40} {cat:<12} {'—':<8} {'skip':>8}")

    # ── Save results ──
    output = {
        "config": {
            "fields": ALL_16_FIELDS,
            "n_fields": len(ALL_16_FIELDS),
            "n_datasets": len(gt),
            "datasets": list(gt.keys()),
        },
        "summaries": summaries,
        "bootstrap_cis": cis,
    }

    with open(OUTPUT_DIR / "eval_16field_results.json", "w") as f:
        json.dump(output, f, indent=2, default=str)

    # ── Generate LaTeX table ──
    latex = []
    latex.append(r"\begin{table}[t]")
    latex.append(r"\centering")
    latex.append(r"\caption{16-field evaluation results on 8 benchmark datasets. Constrained fields use exact match after normalization, short-text fields use token F1, and RAI fields use LLM-as-judge (1--5 scale). Composite is the mean of all normalized scores.}")
    latex.append(r"\label{tab:main-results}")
    latex.append(r"\begin{tabular}{lcccc}")
    latex.append(r"\toprule")
    latex.append(r"Method & Constrained (EM) & Short-text (F1) & RAI (Judge) & Composite \\")
    latex.append(r"\midrule")

    best_comp = max(summaries[m]["composite"]["mean"] for m in main_methods if m in summaries)
    for name in main_methods:
        if name not in summaries:
            continue
        s = summaries[name]
        ci = cis[name]
        c_pct = s["constrained"]["mean"] * 100
        st_f1 = s["short_text"]["mean"]
        rai_15 = s["rai"]["mean_1_5"]
        comp = s["composite"]["mean"] * 100
        ci_lo = ci["ci_lo"] * 100
        ci_hi = ci["ci_hi"] * 100

        comp_str = f"{comp:.1f}\\%"
        if s["composite"]["mean"] == best_comp:
            comp_str = f"\\textbf{{{comp:.1f}\\%}}"

        latex.append(f"{name} & {c_pct:.1f}\\% & {st_f1:.3f} & {rai_15:.2f}/5 & {comp_str} [{ci_lo:.1f}, {ci_hi:.1f}] \\\\")

    latex.append(r"\bottomrule")
    latex.append(r"\end{tabular}")
    latex.append(r"\end{table}")

    # Source ablation table
    if abl_keys:
        latex.append("")
        latex.append(r"\begin{table}[t]")
        latex.append(r"\centering")
        latex.append(r"\caption{Source ablation: effect of input source on composite score (16 fields).}")
        latex.append(r"\label{tab:source-ablation}")
        latex.append(r"\begin{tabular}{lcc}")
        latex.append(r"\toprule")
        latex.append(r"Source & Composite & 95\% CI \\")
        latex.append(r"\midrule")
        for name in abl_keys:
            s = summaries[name]
            ci = cis[name]
            comp = s["composite"]["mean"] * 100
            short = name.replace("Ablation: ", "")
            latex.append(f"{short} & {comp:.1f}\\% & [{ci['ci_lo']*100:.1f}, {ci['ci_hi']*100:.1f}] \\\\")
        latex.append(r"\bottomrule")
        latex.append(r"\end{tabular}")
        latex.append(r"\end{table}")

    with open(OUTPUT_DIR / "paper_tables_16field.tex", "w") as f:
        f.write("\n".join(latex))

    # ── Markdown report ──
    md = []
    md.append("# 16-Field Evaluation Results\n")
    md.append(f"**Fields:** {len(ALL_16_FIELDS)} (7 Constrained + 3 Short-text + 6 RAI)")
    md.append(f"**Datasets:** {len(gt)} ({', '.join(gt.keys())})\n")

    md.append("## Main Results\n")
    md.append("| Method | Constrained (EM) | Short-text (F1) | RAI (Judge 1-5) | Composite [95% CI] | N |")
    md.append("|--------|-----------------|----------------|----------------|-------------------|---|")
    for name in main_methods:
        if name not in summaries:
            continue
        s = summaries[name]
        ci = cis[name]
        c_pct = s["constrained"]["mean"] * 100
        st_f1 = s["short_text"]["mean"]
        rai_15 = s["rai"]["mean_1_5"]
        comp = s["composite"]["mean"] * 100
        n = s["composite"]["n"]
        md.append(f"| {name} | {c_pct:.1f}% (n={s['constrained']['n']}) | {st_f1:.3f} (n={s['short_text']['n']}) | {rai_15:.2f}/5 (n={s['rai']['n']}) | {comp:.1f}% [{ci['ci_lo']*100:.1f}, {ci['ci_hi']*100:.1f}] | {n} |")

    if abl_keys:
        md.append("\n## Source Ablation\n")
        md.append("| Source | Composite [95% CI] |")
        md.append("|--------|-------------------|")
        for name in abl_keys:
            s = summaries[name]
            ci = cis[name]
            comp = s["composite"]["mean"] * 100
            short = name.replace("Ablation: ", "")
            md.append(f"| {short} | {comp:.1f}% [{ci['ci_lo']*100:.1f}, {ci['ci_hi']*100:.1f}] |")

    if "Claude Sonnet 4.5" in summaries:
        claude_comp = summaries["Claude Sonnet 4.5"]["composite"]["mean"] * 100
        md.append(f"\n## AAAI Comparison\n")
        md.append(f"- AAAI (Mistral 7B): 59.4%")
        md.append(f"- NeurIPS (Claude Sonnet 4.5): {claude_comp:.1f}%")
        md.append(f"- Delta: +{claude_comp - 59.4:.1f}pp")

    with open(OUTPUT_DIR / "eval_16field_report.md", "w") as f:
        f.write("\n".join(md))

    print(f"\n\nResults saved to {OUTPUT_DIR}/")
    print(f"  eval_16field_results.json")
    print(f"  paper_tables_16field.tex")
    print(f"  eval_16field_report.md")


if __name__ == "__main__":
    main()
