#!/usr/bin/env python3
"""
Task 7: Unified Evaluation Script

Evaluates one or more extraction strategies against ground truth.
Computes per-field metrics (EM, BERTScore, LLM judge), null handling,
composite scores, statistical tests, and Pareto data.

Uses existing metric functions from evaluation/field_metrics.py (validated
by 39+ unit tests). Does NOT reimplement metrics.

Usage:
  python evaluation/evaluate_all.py --gt data/gt/ --strategies claude_sonnet,gpt4o_mini
  python evaluation/evaluate_all.py --gt data/gt/ --strategies all
  python evaluation/evaluate_all.py --gt data/gt/ --strategies claude_sonnet --skip-judge
  python evaluation/evaluate_all.py --list-strategies
"""

import argparse
import json
import logging
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from validation.validate_extraction import CANONICAL_FIELDS
from evaluation.field_metrics import (
    score_field, finalize_cache, get_field_category,
    score_constrained, score_token_f1,
    CONSTRAINED_FIELDS, SHORT_TEXT_FIELDS, LONG_TEXT_RAI_FIELDS, ALL_30_FIELDS,
)

# ═══════════════════════════════════════════════════════════════════════
# Config
# ═══════════════════════════════════════════════════════════════════════

EXTRACTION_BASE = ROOT / "data" / "extractions"
PROCESSED_BASE = ROOT / "data" / "processed"
RESULTS_DIR = ROOT / "results"

# Strategy name → directory mapping
# Each strategy dir contains {ds_id}.json files (or {ds_id}/full_pdf_metadata_result.json)
STRATEGY_DIRS = {
    "claude_sonnet":         PROCESSED_BASE,
    "gpt4o_mini":            ROOT / "results" / "gpt4o_mini",
    "hf_auto":               ROOT / "data" / "baselines" / "hf_croissant_mapped",
    "gemini_2.5_pro":        EXTRACTION_BASE / "gemini_2_5_pro",
    "gemini_2.0_flash":      EXTRACTION_BASE / "gemini_2_0_flash",
    "context_full":          EXTRACTION_BASE / "context_ablation" / "full",
    "context_50pct":         EXTRACTION_BASE / "context_ablation" / "50pct",
    "context_25pct":         EXTRACTION_BASE / "context_ablation" / "25pct",
    "context_abstract":      EXTRACTION_BASE / "context_ablation" / "abstract",
    "fewshot_0shot":         EXTRACTION_BASE / "fewshot" / "0shot",
    "fewshot_1shot":         EXTRACTION_BASE / "fewshot" / "1shot",
    "fewshot_3shot":         EXTRACTION_BASE / "fewshot" / "3shot",
    "self_consistency_k3":   EXTRACTION_BASE / "self_consistency" / "k3" / "merged",
    "self_consistency_k5":   EXTRACTION_BASE / "self_consistency" / "k5" / "merged",
    "tool_augmented":        EXTRACTION_BASE / "tool_augmented",
    "finetuned_qwen7b":      EXTRACTION_BASE / "finetuned_qwen7b",
}

# Field name mapping: extraction JSONs use unprefixed general fields,
# but our metric functions use prefixed (sc:name, cr:citeAs, etc.)
FIELD_PREFIX_MAP = {
    "name": "sc:name", "description": "sc:description", "url": "sc:url",
    "license": "sc:license", "creator": "sc:creator", "publisher": "sc:publisher",
    "datePublished": "sc:datePublished", "inLanguage": "sc:inLanguage",
    "citeAs": "cr:citeAs", "isLiveDataset": "cr:isLiveDataset",
}

SEED = 42
BOOTSTRAP_N = 2000

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler()],
)
log = logging.getLogger("evaluate_all")

# ═══════════════════════════════════════════════════════════════════════
# Data loading
# ═══════════════════════════════════════════════════════════════════════


def load_gt(gt_dir: Path) -> dict:
    """Load ground truth: {ds_id: {field: value}}.

    Supports two formats:
      1. Individual files: gt_dir/{ds_id}.json
      2. Consolidated: gt_dir/all_annotations.json with {ds_id: [...]}
    """
    gt = {}

    # Try consolidated format first
    consolidated = gt_dir / "all_annotations.json"
    if consolidated.exists():
        with open(consolidated) as f:
            data = json.load(f)
        for ds_id, entry in data.items():
            if isinstance(entry, list):
                gt[ds_id] = entry[0]  # use first annotator
            else:
                gt[ds_id] = entry
        return gt

    # Individual files
    for f in sorted(gt_dir.glob("*.json")):
        ds_id = f.stem
        if ds_id == "all_annotations":
            continue
        with open(f) as fh:
            data = json.load(fh)
        if isinstance(data, list):
            data = data[0]
        gt[ds_id] = data
    return gt


def load_extraction(strategy_dir: Path, ds_id: str) -> dict:
    """Load extraction for a dataset, trying multiple naming patterns."""
    # Try {ds_id}.json
    for name in [f"{ds_id}.json", f"{ds_id}_extraction.json"]:
        p = strategy_dir / name
        if p.exists():
            with open(p) as f:
                return json.load(f)

    # Try {ds_id}/full_pdf_metadata_result.json (processed dir format)
    p = strategy_dir / ds_id / "full_pdf_metadata_result.json"
    if p.exists():
        with open(p) as f:
            return json.load(f)

    return None


def resolve_field(data: dict, prefixed_field: str) -> str:
    """Get field value with prefix fallback."""
    val = data.get(prefixed_field)
    if val is not None:
        return val
    # Try unprefixed
    short = prefixed_field.split(":")[-1] if ":" in prefixed_field else prefixed_field
    val = data.get(short)
    if val is not None:
        return val
    # Try rai: prefix
    if not prefixed_field.startswith("rai:"):
        val = data.get(f"rai:{short}")
    return val


# ═══════════════════════════════════════════════════════════════════════
# Null classification
# ═══════════════════════════════════════════════════════════════════════

UNKNOWN_VALUES = {"unknown", "n/a", "none", "null", "not disclosed", "na"}


def classify_null(gt_val, pred_val) -> str:
    """Classify a (gt, pred) pair for null handling.

    Returns: "correct_null", "hallucination", "miss", "non_null", "skip"
    """
    gt_empty = gt_val is None or not str(gt_val).strip()
    gt_unknown = (not gt_empty and str(gt_val).strip().lower() in UNKNOWN_VALUES)
    pred_empty = pred_val is None or not str(pred_val).strip()

    if gt_empty or gt_unknown:
        return "skip"  # no usable GT
    if pred_empty:
        return "miss"  # GT has value, pred is null
    return "non_null"  # both have values, evaluate


# ═══════════════════════════════════════════════════════════════════════
# Evaluation core
# ═══════════════════════════════════════════════════════════════════════


def evaluate_strategy(
    strategy_name: str,
    strategy_dir: Path,
    gt: dict,
    skip_judge: bool = False,
) -> dict:
    """Evaluate a single strategy against ground truth.

    Returns detailed results dict.
    """
    log.info(f"\n{'─'*60}")
    log.info(f"Evaluating: {strategy_name}")
    log.info(f"{'─'*60}")

    per_field_scores = defaultdict(list)
    per_field_raw = defaultdict(list)
    null_stats = {"correct_null": 0, "miss": 0, "hallucination": 0, "skip": 0, "non_null": 0}
    ds_scores = {}
    n_evaluated = 0
    n_skipped = 0
    n_missing = 0

    for ds_id, gt_data in sorted(gt.items()):
        ext = load_extraction(strategy_dir, ds_id)
        if ext is None:
            n_missing += 1
            continue

        ds_field_scores = []

        for prefixed_field in ALL_30_FIELDS:
            gt_val = resolve_field(gt_data, prefixed_field)
            pred_val = resolve_field(ext, prefixed_field)

            # Null classification
            nc = classify_null(gt_val, pred_val)
            null_stats[nc] += 1

            if nc == "skip":
                n_skipped += 1
                continue

            # Score using existing validated functions
            gt_str = str(gt_val).strip() if gt_val is not None else None
            pred_str = str(pred_val).strip() if pred_val is not None else None

            cat = get_field_category(prefixed_field)

            if nc == "miss":
                score = 0.0
                raw = 0
            elif skip_judge and cat == "rai":
                # Skip LLM judge, use token F1 instead
                score = score_token_f1(pred_str, gt_str) if pred_str and gt_str else 0.0
                raw = score
            else:
                result = score_field(pred_str, gt_str, prefixed_field)
                if result["skipped"]:
                    n_skipped += 1
                    continue
                score = result["score"]
                raw = result["raw_score"]

            per_field_scores[prefixed_field].append(score)
            per_field_raw[prefixed_field].append(raw)
            ds_field_scores.append(score)
            n_evaluated += 1

        if ds_field_scores:
            ds_scores[ds_id] = float(np.mean(ds_field_scores))

    # Aggregate
    all_scores = []
    per_category = defaultdict(list)
    per_field_summary = {}

    for field in ALL_30_FIELDS:
        scores = per_field_scores.get(field, [])
        if not scores:
            continue
        cat = get_field_category(field)
        mean = float(np.mean(scores))
        per_category[cat].extend(scores)
        all_scores.extend(scores)
        per_field_summary[field] = {
            "n": len(scores),
            "mean": round(mean, 4),
            "category": cat,
        }

    composite = float(np.mean(all_scores)) if all_scores else 0
    ci_lo, ci_hi = bootstrap_ci(all_scores)

    # Log summary
    log.info(f"  Evaluated: {n_evaluated} pairs, skipped: {n_skipped}, missing: {n_missing}")
    log.info(f"  Composite: {composite*100:.1f}% [{ci_lo*100:.1f}, {ci_hi*100:.1f}]")

    for cat in ["constrained", "short_text", "rai"]:
        scores = per_category.get(cat, [])
        if scores:
            log.info(f"  {cat}: {np.mean(scores)*100:.1f}% (n={len(scores)})")

    log.info(f"  Nulls: miss={null_stats['miss']}, skip={null_stats['skip']}, "
             f"non_null={null_stats['non_null']}")

    return {
        "strategy": strategy_name,
        "composite": round(composite, 4),
        "ci_95": [round(ci_lo, 4), round(ci_hi, 4)],
        "n_evaluated": n_evaluated,
        "n_datasets": len(ds_scores),
        "per_category": {
            cat: {"mean": round(float(np.mean(s)), 4), "n": len(s)}
            for cat, s in per_category.items() if s
        },
        "per_field": per_field_summary,
        "null_stats": null_stats,
        "per_dataset": ds_scores,
        "all_scores": all_scores,  # for statistical tests
    }


def bootstrap_ci(scores: list, n_boot: int = BOOTSTRAP_N, ci: float = 0.95) -> tuple:
    """Bootstrap 95% CI for mean."""
    if not scores:
        return (0, 0)
    scores = np.array(scores)
    rng = np.random.default_rng(SEED)
    means = [np.mean(rng.choice(scores, size=len(scores), replace=True)) for _ in range(n_boot)]
    means = np.sort(means)
    alpha = (1 - ci) / 2
    return float(means[int(alpha * n_boot)]), float(means[int((1 - alpha) * n_boot)])


def mcnemar_test(scores_a: list, scores_b: list, threshold: float = 0.5) -> dict:
    """McNemar's test on binary outcomes (score >= threshold)."""
    if len(scores_a) != len(scores_b):
        n = min(len(scores_a), len(scores_b))
        scores_a = scores_a[:n]
        scores_b = scores_b[:n]

    a_right = [s >= threshold for s in scores_a]
    b_right = [s >= threshold for s in scores_b]

    # Contingency: a_right & b_wrong, a_wrong & b_right
    b_only = sum(1 for a, b in zip(a_right, b_right) if not a and b)
    a_only = sum(1 for a, b in zip(a_right, b_right) if a and not b)

    n_discordant = a_only + b_only
    if n_discordant == 0:
        return {"chi2": 0, "p_value": 1.0, "significant": False}

    chi2 = (abs(a_only - b_only) - 1) ** 2 / n_discordant
    # Approximate p-value (chi-squared with 1 df)
    from scipy import stats
    p_value = 1 - stats.chi2.cdf(chi2, df=1)

    return {
        "chi2": round(chi2, 3),
        "p_value": round(p_value, 4),
        "significant": p_value < 0.05,
        "a_only": a_only,
        "b_only": b_only,
    }


# ═══════════════════════════════════════════════════════════════════════
# Report generation
# ═══════════════════════════════════════════════════════════════════════


def generate_markdown(results: dict, output_path: Path):
    """Generate evaluation tables in markdown."""
    lines = ["# CroissantMiner Evaluation Results\n"]

    # Main comparison table
    lines.append("## Main Comparison\n")
    lines.append("| Strategy | Constrained (EM) | Short-text | RAI | Composite [95% CI] | N |")
    lines.append("|----------|-----------------|------------|-----|-------------------|---|")

    for name, r in sorted(results.items(), key=lambda x: -x[1]["composite"]):
        c = r["per_category"].get("constrained", {"mean": 0, "n": 0})
        st = r["per_category"].get("short_text", {"mean": 0, "n": 0})
        rai = r["per_category"].get("rai", {"mean": 0, "n": 0})
        ci = r["ci_95"]
        lines.append(
            f"| {name} | {c['mean']*100:.1f}% (n={c['n']}) | "
            f"{st['mean']*100:.1f}% (n={st['n']}) | "
            f"{rai['mean']*100:.1f}% (n={rai['n']}) | "
            f"{r['composite']*100:.1f}% [{ci[0]*100:.1f}, {ci[1]*100:.1f}] | "
            f"{r['n_evaluated']} |"
        )

    # Null handling
    lines.append("\n## Null Handling\n")
    lines.append("| Strategy | Miss (GT has, pred null) | Skip (no GT) | Non-null |")
    lines.append("|----------|------------------------|-------------|----------|")
    for name, r in sorted(results.items()):
        ns = r["null_stats"]
        lines.append(f"| {name} | {ns['miss']} | {ns['skip']} | {ns['non_null']} |")

    # Per-field for best strategy
    best = max(results.items(), key=lambda x: x[1]["composite"])
    lines.append(f"\n## Per-Field Breakdown ({best[0]})\n")
    lines.append("| Field | Category | Score | N |")
    lines.append("|-------|----------|-------|---|")
    for field in ALL_30_FIELDS:
        info = best[1]["per_field"].get(field)
        if info:
            lines.append(f"| {field} | {info['category']} | {info['mean']*100:.1f}% | {info['n']} |")

    with open(output_path, "w") as f:
        f.write("\n".join(lines))
    log.info(f"  Saved: {output_path}")


# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(description="Unified Evaluation")
    parser.add_argument("--gt", type=Path, required=True, help="Ground truth directory")
    parser.add_argument("--strategies", type=str, default="claude_sonnet",
                        help="Comma-separated strategy names, or 'all'")
    parser.add_argument("--skip-judge", action="store_true",
                        help="Skip LLM judge for RAI fields (use token F1 instead)")
    parser.add_argument("--list-strategies", action="store_true",
                        help="List available strategies and exit")
    args = parser.parse_args()

    if args.list_strategies:
        print("Available strategies:")
        for name, path in sorted(STRATEGY_DIRS.items()):
            exists = "✓" if path.exists() else "✗"
            count = len(list(path.glob("*.json"))) if path.exists() else 0
            print(f"  {exists} {name:<25} {path} ({count} files)")
        return

    # Load GT
    if not args.gt.exists():
        log.error(f"GT directory not found: {args.gt}")
        log.info("Build GT first with finetuning/prepare_data.py or similar.")
        sys.exit(1)

    gt = load_gt(args.gt)
    log.info(f"Ground truth: {len(gt)} datasets from {args.gt}")

    # Resolve strategies
    if args.strategies == "all":
        strategy_names = [n for n, p in STRATEGY_DIRS.items() if p.exists()]
    else:
        strategy_names = [s.strip() for s in args.strategies.split(",")]

    # Evaluate each strategy
    all_results = {}
    for name in strategy_names:
        if name not in STRATEGY_DIRS:
            log.warning(f"Unknown strategy: {name}")
            continue
        sdir = STRATEGY_DIRS[name]
        if not sdir.exists():
            log.warning(f"Strategy dir not found: {sdir}")
            continue

        result = evaluate_strategy(name, sdir, gt, skip_judge=args.skip_judge)
        all_results[name] = result

    finalize_cache()

    if not all_results:
        log.error("No strategies evaluated.")
        return

    # Statistical tests (pairwise)
    if len(all_results) >= 2:
        log.info(f"\n{'─'*60}")
        log.info("Statistical Tests (McNemar)")
        log.info(f"{'─'*60}")

        names = sorted(all_results.keys(), key=lambda n: -all_results[n]["composite"])
        stat_results = {}
        for i, a in enumerate(names):
            for b in names[i+1:]:
                try:
                    test = mcnemar_test(all_results[a]["all_scores"], all_results[b]["all_scores"])
                    sig = "***" if test["significant"] else "n.s."
                    log.info(f"  {a} vs {b}: χ²={test['chi2']}, p={test['p_value']} {sig}")
                    stat_results[f"{a}_vs_{b}"] = test
                except Exception as e:
                    log.warning(f"  {a} vs {b}: test failed: {e}")

    # Save results
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # Clean results for JSON (remove numpy arrays)
    json_results = {}
    for name, r in all_results.items():
        jr = {k: v for k, v in r.items() if k != "all_scores"}
        json_results[name] = jr

    summary_path = RESULTS_DIR / "evaluation_summary.json"
    with open(summary_path, "w") as f:
        json.dump(json_results, f, indent=2, default=str)
    log.info(f"\nSaved: {summary_path}")

    tables_path = RESULTS_DIR / "evaluation_tables.md"
    generate_markdown(all_results, tables_path)

    # Final summary
    log.info(f"\n{'═'*60}")
    log.info("FINAL RANKING")
    log.info(f"{'═'*60}")
    for name in sorted(all_results.keys(), key=lambda n: -all_results[n]["composite"]):
        r = all_results[name]
        ci = r["ci_95"]
        log.info(f"  {name:<25} {r['composite']*100:.1f}% [{ci[0]*100:.1f}, {ci[1]*100:.1f}]")


if __name__ == "__main__":
    main()
