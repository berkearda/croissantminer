#!/usr/bin/env python3
"""
Multi-run extraction comparison: old prompts vs new prompts.

Runs extraction 3 times each with old and new prompts to control for LLM variance.
Evaluates all runs with LLM-as-judge and reports averaged results with std dev.

Usage:
    python scripts/multi_run_comparison.py              # full pipeline
    python scripts/multi_run_comparison.py --eval-only   # skip extraction
    python scripts/multi_run_comparison.py --compare-only # just compare existing results
"""

import sys
import json
import time
import shutil
import subprocess
import argparse
import numpy as np
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

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
CONFIG_FILE = Path("config.py")

# Directories for each run
RUN_DIRS = {
    "old_run1": Path("evaluation_outputs"),        # Already exists
    "old_run2": Path("evaluation_outputs_old_r2"),
    "old_run3": Path("evaluation_outputs_old_r3"),
    "new_run1": Path("evaluation_outputs_v2"),      # Already exists
    "new_run2": Path("evaluation_outputs_v2_r2"),
    "new_run3": Path("evaluation_outputs_v2_r3"),
}


def build_old_system_prompt():
    """Build the OLD system prompt (without extraction guides) from current config."""
    from config import SYSTEM_PROMPT
    import re
    # Remove all [EXTRACTION GUIDE] blocks and GOOD/BAD/MOST LIKELY lines
    old = SYSTEM_PROMPT
    # Remove the general field-specific section (section 4) we added
    old = re.sub(
        r'4\. \*\*General Field-Specific Information:\*\*.*?5\. \*\*RAI Field-Specific Information:\*\*',
        '4. **RAI Field-Specific Information:**',
        old, flags=re.DOTALL
    )
    # Remove [EXTRACTION GUIDE] blocks (guide + GOOD/BAD/MOST LIKELY lines that follow)
    old = re.sub(
        r'\n     \[EXTRACTION GUIDE\].*?(?=\n   - \*\*|\n\n|\'\'\'$)',
        '', old, flags=re.DOTALL
    )
    return old


def run_extraction(output_dir, system_prompt_override=None):
    """Run extraction on all 8 benchmarks with optional prompt override."""
    output_dir.mkdir(exist_ok=True)

    from config import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE, MAX_PDF_CHARS
    from metadata.extractor import setup_llm_pipeline, clean_llm_output
    from pdf.reader import extract_text_from_pdf
    from pdf.processor import clean_text
    import re as re_mod

    sys_prompt = system_prompt_override if system_prompt_override else SYSTEM_PROMPT
    model = setup_llm_pipeline("claude-sonnet-4-5")

    for pdf_id, ds_name in BENCHMARK_MAP.items():
        pdf_path = RAW_DIR / f"{pdf_id}.pdf"
        if not pdf_path.exists():
            continue

        out_file = output_dir / f"{ds_name}_extraction.json"
        print(f"  {ds_name}...", end=" ", flush=True)
        start = time.time()

        raw_text = extract_text_from_pdf(pdf_path)
        cleaned = clean_text(raw_text)
        if len(cleaned) > MAX_PDF_CHARS:
            cleaned = cleaned[:MAX_PDF_CHARS]

        user_prompt = USER_PROMPT_TEMPLATE % cleaned
        output = model.generate(user_prompt, system_prompt=sys_prompt)
        json_str = clean_llm_output(output, user_prompt)

        try:
            metadata = json.loads(json_str)
        except json.JSONDecodeError:
            metadata = {}
            null_pat = r'"([^"]+)"\s*:\s*null'
            str_pat = r'"([^"]+)"\s*:\s*"((?:[^"\\]|\\.)*)"'
            for m in re_mod.finditer(null_pat, json_str):
                metadata[m.group(1)] = None
            for m in re_mod.finditer(str_pat, json_str):
                metadata[m.group(1)] = m.group(2).replace('\\n', ' ').strip()
            print(f"(regex fallback: {len(metadata)} fields)", end=" ")

        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        elapsed = time.time() - start
        print(f"{elapsed:.0f}s")


def run_evaluation(extraction_dir, report_name="evaluation_report.json"):
    """Run LLM-as-judge evaluation on extractions."""
    from evaluation.evaluator import batch_evaluate
    from evaluation.groundtruth_parser_md import parse_markdown_groundtruth

    gt_dir = "groundtruth/parsed_md_filtered"
    parse_markdown_groundtruth("groundtruth/Croissant_Dataset_Annotations.md", output_dir=gt_dir)

    output_file = str(extraction_dir / report_name)
    batch_evaluate(
        extraction_outputs_dir=str(extraction_dir),
        groundtruth_dir=gt_dir,
        output_file=output_file,
        verbose=False,
        use_llm=True
    )
    return output_file


def load_eval_results(report_path):
    """Load evaluation report and extract per-field scores."""
    with open(report_path) as f:
        data = json.load(f)

    field_scores = {}  # field -> {dataset -> score}
    ds_accuracies = {}

    for ds_name, ds_data in data.get("results", {}).items():
        stats = ds_data.get("metrics", {}).get("overall_stats", {})
        ds_accuracies[ds_name] = stats.get("llm_accuracy", 0)

        for field, result in ds_data.get("metrics", {}).get("field_results", {}).items():
            if field not in field_scores:
                field_scores[field] = {}
            field_scores[field][ds_name] = result["score"]

    return field_scores, ds_accuracies


def compare_all_runs():
    """Compare old vs new across all runs."""
    # Load all available evaluation reports
    old_runs = []
    new_runs = []

    old_report_files = [
        ("old_run1", RUN_DIRS["old_run1"] / "evaluation_report_full_pdf.json"),
        ("old_run2", RUN_DIRS["old_run2"] / "evaluation_report.json"),
        ("old_run3", RUN_DIRS["old_run3"] / "evaluation_report.json"),
    ]
    new_report_files = [
        ("new_run1", RUN_DIRS["new_run1"] / "evaluation_report_v2.json"),
        ("new_run2", RUN_DIRS["new_run2"] / "evaluation_report.json"),
        ("new_run3", RUN_DIRS["new_run3"] / "evaluation_report.json"),
    ]

    for label, path in old_report_files:
        if path.exists():
            fs, da = load_eval_results(path)
            old_runs.append((label, fs, da))
            print(f"  Loaded {label}: {path}")
        else:
            print(f"  MISSING {label}: {path}")

    for label, path in new_report_files:
        if path.exists():
            fs, da = load_eval_results(path)
            new_runs.append((label, fs, da))
            print(f"  Loaded {label}: {path}")
        else:
            print(f"  MISSING {label}: {path}")

    if not old_runs or not new_runs:
        print("Need at least 1 old and 1 new run to compare.")
        return

    # Collect all fields
    all_fields = set()
    for _, fs, _ in old_runs + new_runs:
        all_fields.update(fs.keys())
    all_fields = sorted(all_fields)

    # Compute per-field accuracy for each run (weighted: CORRECT=1.0, PARTIAL=0.5)
    def field_accuracy(field_scores_dict, field):
        scores = field_scores_dict.get(field, {})
        if not scores:
            return None
        return np.mean(list(scores.values())) * 100  # weighted accuracy %

    def overall_accuracy(ds_acc_dict):
        if not ds_acc_dict:
            return 0
        return np.mean(list(ds_acc_dict.values())) * 100

    # ── TARGET FIELDS TABLE ──
    target_fields = [
        ("rai:dataReleaseMaintenancePlan", "dataReleaseMaintenancePlan"),
        ("sc:datePublished", "datePublished"),
        ("rai:dataBiases", "dataBiases"),
        ("rai:dataAnnotationProtocol", "dataAnnotationProtocol"),
        ("sc:creator", "creator"),
    ]

    print(f"\n{'='*100}")
    print(f"TARGET FIELDS: AVERAGED COMPARISON ({len(old_runs)} old runs × {len(new_runs)} new runs)")
    print(f"{'='*100}")
    print(f"\n{'Field':<35} {'Before (mean±std)':>18} {'After (mean±std)':>18} {'Delta':>8} {'Status':<12}")
    print("-" * 95)

    for field_key, display_name in target_fields:
        old_accs = [field_accuracy(fs, field_key) for _, fs, _ in old_runs]
        new_accs = [field_accuracy(fs, field_key) for _, fs, _ in new_runs]

        # Filter None values
        old_accs = [a for a in old_accs if a is not None]
        new_accs = [a for a in new_accs if a is not None]

        if old_accs:
            old_mean, old_std = np.mean(old_accs), np.std(old_accs)
            old_str = f"{old_mean:5.1f}% ±{old_std:4.1f}"
        else:
            old_mean, old_std = 0, 0
            old_str = "  n/a in GT"

        if new_accs:
            new_mean, new_std = np.mean(new_accs), np.std(new_accs)
            new_str = f"{new_mean:5.1f}% ±{new_std:4.1f}"
        else:
            new_mean, new_std = 0, 0
            new_str = "  n/a in GT"

        delta = new_mean - old_mean
        if not old_accs or not new_accs:
            status = "NOT IN GT"
        elif delta > 5:
            status = "IMPROVED"
        elif delta < -5:
            status = "REGRESSED"
        else:
            status = "STABLE"

        print(f"{display_name:<35} {old_str:>18} {new_str:>18} {delta:>+7.1f}pp {status:<12}")

    # Overall
    old_overalls = [overall_accuracy(da) for _, _, da in old_runs]
    new_overalls = [overall_accuracy(da) for _, _, da in new_runs]
    old_mean_o, old_std_o = np.mean(old_overalls), np.std(old_overalls)
    new_mean_o, new_std_o = np.mean(new_overalls), np.std(new_overalls)
    print("-" * 95)
    print(f"{'OVERALL':<35} {old_mean_o:5.1f}% ±{old_std_o:4.1f}  {new_mean_o:5.1f}% ±{new_std_o:4.1f}  {new_mean_o - old_mean_o:>+7.1f}pp")

    # ── ALL FIELDS REGRESSION CHECK ──
    print(f"\n{'='*100}")
    print(f"ALL FIELDS: AVERAGED REGRESSION CHECK")
    print(f"{'='*100}")
    print(f"\n{'Field':<40} {'Before (mean±std)':>18} {'After (mean±std)':>18} {'Delta':>8}")
    print("-" * 90)

    improved = []
    regressed = []
    stable = []

    for field in all_fields:
        old_accs = [field_accuracy(fs, field) for _, fs, _ in old_runs]
        new_accs = [field_accuracy(fs, field) for _, fs, _ in new_runs]
        old_accs = [a for a in old_accs if a is not None]
        new_accs = [a for a in new_accs if a is not None]

        if not old_accs and not new_accs:
            continue

        old_mean = np.mean(old_accs) if old_accs else 0
        old_std = np.std(old_accs) if old_accs else 0
        new_mean = np.mean(new_accs) if new_accs else 0
        new_std = np.std(new_accs) if new_accs else 0
        delta = new_mean - old_mean

        marker = ""
        if delta > 5:
            marker = " ★"
            improved.append((field, old_mean, new_mean, delta))
        elif delta < -5:
            marker = " ◄"
            regressed.append((field, old_mean, new_mean, delta))
        else:
            stable.append(field)

        old_str = f"{old_mean:5.1f}% ±{old_std:4.1f}" if old_accs else "  n/a     "
        new_str = f"{new_mean:5.1f}% ±{new_std:4.1f}" if new_accs else "  n/a     "
        print(f"{field:<40} {old_str:>18} {new_str:>18} {delta:>+7.1f}pp{marker}")

    print(f"\nSummary: {len(improved)} improved (>5pp), {len(regressed)} regressed (<-5pp), {len(stable)} stable (±5pp)")

    # ── PER-DATASET ──
    print(f"\n{'='*100}")
    print("PER-DATASET AVERAGED ACCURACY")
    print(f"{'='*100}")

    all_datasets = sorted(set(
        ds for _, _, da in old_runs + new_runs for ds in da.keys()
    ))

    print(f"\n{'Dataset':<20} {'Before (mean±std)':>18} {'After (mean±std)':>18} {'Delta':>8}")
    print("-" * 70)

    for ds in all_datasets:
        old_ds = [da.get(ds, 0) * 100 for _, _, da in old_runs]
        new_ds = [da.get(ds, 0) * 100 for _, _, da in new_runs]
        old_m, old_s = np.mean(old_ds), np.std(old_ds)
        new_m, new_s = np.mean(new_ds), np.std(new_ds)
        delta = new_m - old_m
        print(f"{ds:<20} {old_m:5.1f}% ±{old_s:4.1f}  {new_m:5.1f}% ±{new_s:4.1f}  {delta:>+7.1f}pp")

    # ── VARIANCE ANALYSIS ──
    print(f"\n{'='*100}")
    print("LLM VARIANCE ANALYSIS")
    print(f"{'='*100}")
    print(f"\n  Old prompt runs ({len(old_runs)}): overall = {[f'{o:.1f}%' for o in old_overalls]}")
    print(f"  New prompt runs ({len(new_runs)}): overall = {[f'{n:.1f}%' for n in new_overalls]}")
    print(f"  Old std dev: {old_std_o:.2f}pp")
    print(f"  New std dev: {new_std_o:.2f}pp")
    print(f"  Mean difference: {new_mean_o - old_mean_o:+.1f}pp")

    if old_std_o > 0 or new_std_o > 0:
        pooled_std = np.sqrt((old_std_o**2 + new_std_o**2) / 2) if (old_std_o + new_std_o) > 0 else 1
        effect = (new_mean_o - old_mean_o) / pooled_std if pooled_std > 0 else 0
        print(f"  Effect size (Cohen's d): {effect:.2f}")
        if abs(new_mean_o - old_mean_o) > 2 * max(old_std_o, new_std_o):
            print("  → Difference likely REAL (exceeds 2× std dev)")
        else:
            print("  → Difference may be within LLM variance")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval-only", action="store_true")
    parser.add_argument("--compare-only", action="store_true")
    args = parser.parse_args()

    if args.compare_only:
        print("Loading existing results...")
        compare_all_runs()
        return

    if not args.eval_only:
        # Build old system prompt by stripping extraction guides from current
        print("Building old system prompt (without extraction guides)...")
        old_sys_prompt = build_old_system_prompt()
        print(f"  Old prompt: {len(old_sys_prompt)} chars")
        from config import SYSTEM_PROMPT
        print(f"  New prompt: {len(SYSTEM_PROMPT)} chars")

        # ── OLD PROMPT RUNS ──
        for run_name in ["old_run2", "old_run3"]:
            run_dir = RUN_DIRS[run_name]
            if (run_dir / "extraction_done").exists():
                print(f"\n{run_name}: already extracted, skipping")
                continue
            print(f"\n{'='*60}")
            print(f"EXTRACTION: {run_name} (OLD prompts)")
            print(f"{'='*60}")
            run_extraction(run_dir, system_prompt_override=old_sys_prompt)
            (run_dir / "extraction_done").touch()

        # ── NEW PROMPT RUNS ──
        for run_name in ["new_run2", "new_run3"]:
            run_dir = RUN_DIRS[run_name]
            if (run_dir / "extraction_done").exists():
                print(f"\n{run_name}: already extracted, skipping")
                continue
            print(f"\n{'='*60}")
            print(f"EXTRACTION: {run_name} (NEW prompts)")
            print(f"{'='*60}")
            run_extraction(run_dir)  # Uses current (new) config
            (run_dir / "extraction_done").touch()

    # ── EVALUATE ALL RUNS ──
    eval_runs = [
        ("old_run2", RUN_DIRS["old_run2"]),
        ("old_run3", RUN_DIRS["old_run3"]),
        ("new_run2", RUN_DIRS["new_run2"]),
        ("new_run3", RUN_DIRS["new_run3"]),
    ]

    for run_name, run_dir in eval_runs:
        report = run_dir / "evaluation_report.json"
        if report.exists():
            print(f"\n{run_name}: evaluation already exists, skipping")
            continue
        print(f"\n{'='*60}")
        print(f"EVALUATING: {run_name}")
        print(f"{'='*60}")
        run_evaluation(run_dir)

    # ── COMPARE ──
    print(f"\n{'='*60}")
    print("LOADING AND COMPARING ALL RUNS")
    print(f"{'='*60}")
    compare_all_runs()


if __name__ == "__main__":
    main()
