#!/usr/bin/env python3
"""T-053: score one or more extraction strategies against gold.parquet.

Reads `data/annotations/gold.parquet` (3,060 cells, 22-rater pipeline)
and scores each strategy in `data/extractions/<slug>/{paper}.json`.

Tier 1 (rule-based) wired and runnable today. Tier 2 (LLM-judge ensemble)
is scaffolded but defers to an external judge runner produced by T-021.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evaluation.field_metrics import (  # noqa: E402
    score_constrained, score_token_f1,
    CONSTRAINED_FIELDS, SHORT_TEXT_FIELDS, LONG_TEXT_RAI_FIELDS,
)

GOLD_PARQUET = ROOT / "data" / "annotations" / "gold.parquet"
EXTRACTION_BASE = ROOT / "data" / "extractions"
RESULTS_DIR = ROOT / "results" / "v5_scoring"

# Locked 22-strategy lineup per decisions.md 2026-04-27.
# Main table = 16, appendix = 6. Order reflects display order.
STRATEGY_DIRS = {
    # 12 single-pass (10 proprietary + 3 open-weight, but Sonnet 4.5 here is
    # the gold-reference single-pass; agentic variants below)
    "claude_sonnet_4_5":          ROOT / "data" / "processed",
    "claude_sonnet_4_6":          EXTRACTION_BASE / "claude_sonnet_4_6",
    "claude_opus_4_7":            EXTRACTION_BASE / "claude_opus_4_7",
    "gpt5_4_full":                EXTRACTION_BASE / "gpt5.4_full",
    "gpt5_4_mini":                EXTRACTION_BASE / "gpt5.4_mini",
    "gemini_3_1_pro":             EXTRACTION_BASE / "gemini_3.1_pro",
    "gemini_2_5_flash":           EXTRACTION_BASE / "gemini_2.5_flash",
    "deepseek_v3_2":              EXTRACTION_BASE / "deepseek_v3_2",
    "glm_5_1":                    EXTRACTION_BASE / "glm_5_1",
    "llama4_scout":               EXTRACTION_BASE / "llama4_scout",
    "mistral_small_4":            EXTRACTION_BASE / "mistral_small_4",
    "qwen3_6_35b_a3b":            EXTRACTION_BASE / "qwen3_6_35b_a3b",
    # 4 agentic at fixed Sonnet 4.5 backbone (architecture-isolation block)
    "agentic_v2_sonnet_4_5":      EXTRACTION_BASE / "agentic_v2_sonnet_4_5",
    "agentic_lev_sonnet_4_5":     EXTRACTION_BASE / "agentic_lev_sonnet_4_5",
    "agentic_react_sonnet_4_5":   EXTRACTION_BASE / "agentic_react_sonnet_4_5",
    "agentic_specialist_sonnet_4_5": EXTRACTION_BASE / "agentic_specialist_sonnet_4_5",
    # 6 appendix (backbone-isolation block)
    "agentic_v2_gpt5_4_full":     EXTRACTION_BASE / "agentic_v2_gpt5_4_full",
    "agentic_v2_gemini_3_1_pro":  EXTRACTION_BASE / "agentic_v2_gemini_3_1_pro",
    "agentic_v2_llama4_scout":    EXTRACTION_BASE / "agentic_v2_llama4_scout",
    "agentic_lev_gpt5_4_full":    EXTRACTION_BASE / "agentic_lev_gpt5_4_full",
    "agentic_lev_gemini_3_1_pro": EXTRACTION_BASE / "agentic_lev_gemini_3_1_pro",
    "agentic_lev_llama4_scout":   EXTRACTION_BASE / "agentic_lev_llama4_scout",
}

# gold_method values that count as "settled" gold by default.
DEFAULT_GOLD_METHODS = (
    "unanimous_3of3", "unanimous_4of4",
    "majority_2of3", "majority_3of4",
    "adjudicated", "tie_resolved_via_correction",
)

BOOTSTRAP_N = 2000
SEED = 42

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("score_against_gold")


# ── data loading ───────────────────────────────────────────────────


def load_gold(gold_methods: tuple[str, ...]) -> pd.DataFrame:
    g = pd.read_parquet(GOLD_PARQUET)
    g = g[g["gold_method"].isin(gold_methods)].copy()
    g = g[g["gold_value"].notna()].copy()
    log.info(
        "loaded gold: %d cells across %d papers x %d fields "
        "(filter: %s)",
        len(g), g["paper_id"].nunique(), g["field_id"].nunique(),
        ",".join(gold_methods),
    )
    return g


def load_extraction(strategy_dir: Path, paper_id: str) -> dict | None:
    """One JSON per paper. Tries flat layout first, then agentic subdir."""
    candidates = [
        strategy_dir / f"{paper_id}.json",
        strategy_dir / paper_id / "extraction.json",
        strategy_dir / paper_id / "full_result.json",
        # Legacy gold-reference single-pass under data/processed/<paper>/
        strategy_dir / paper_id / "full_pdf_metadata_result.json",
    ]
    for path in candidates:
        if path.exists():
            with open(path) as f:
                return json.load(f)
    return None


def get_pred_value(extraction_payload: dict, field_id: str) -> str | None:
    """Resolve a prediction for `field_id` across the variants we've seen.

    Extraction JSONs sometimes nest under `extraction:`, sometimes flat.
    Field names may carry the sc:/cr:/rai: prefix or be unprefixed for
    the 10 core fields. We try several lookups in priority order.
    """
    payload = extraction_payload.get("extraction", extraction_payload)

    if field_id in payload and payload[field_id] is not None:
        return payload[field_id]

    short = field_id.split(":")[-1] if ":" in field_id else field_id
    if short in payload and payload[short] is not None:
        return payload[short]

    return None


# ── scoring ────────────────────────────────────────────────────────


def score_cell(pred_val, gold_val, field_id: str, skip_judge: bool) -> dict:
    """Score one (system, paper, field) cell.

    Returns {"score": float in [0,1] or None, "tier": "tier1"|"tier2",
             "raw": ..., "skipped_reason": ...}.
    """
    pred_str = str(pred_val).strip() if pred_val is not None else None
    gold_str = str(gold_val).strip() if gold_val is not None else None

    if not gold_str:
        return {"score": None, "tier": None, "raw": None,
                "skipped_reason": "gold_empty"}

    if not pred_str:
        # Pred is null but gold has a value: this is a miss, score 0.
        tier = "tier1" if field_id in CONSTRAINED_FIELDS \
            or field_id in SHORT_TEXT_FIELDS else "tier2"
        return {"score": 0.0, "tier": tier, "raw": 0,
                "skipped_reason": None, "miss": True}

    if field_id in CONSTRAINED_FIELDS:
        score = score_constrained(pred_str, gold_str, field_id)
        return {"score": float(score), "tier": "tier1",
                "raw": float(score), "skipped_reason": None}

    if field_id in SHORT_TEXT_FIELDS:
        score = score_token_f1(pred_str, gold_str)
        return {"score": float(score), "tier": "tier1",
                "raw": float(score), "skipped_reason": None}

    if field_id in LONG_TEXT_RAI_FIELDS:
        if skip_judge:
            # Fallback while T-021 judge ensemble is being built:
            # token F1 as a stand-in so the pipeline produces numbers
            # end-to-end. Real Tier 2 numbers come from T-021.
            score = score_token_f1(pred_str, gold_str)
            return {"score": float(score), "tier": "tier2_proxy",
                    "raw": float(score), "skipped_reason": None}
        return {"score": None, "tier": "tier2",
                "raw": None,
                "skipped_reason": "tier2_judge_pending"}

    return {"score": None, "tier": None, "raw": None,
            "skipped_reason": f"unknown_field:{field_id}"}


def score_strategy(
    strategy_name: str,
    strategy_dir: Path,
    gold: pd.DataFrame,
    skip_judge: bool,
) -> dict:
    log.info("scoring strategy: %s", strategy_name)
    if not strategy_dir.exists():
        log.warning("  strategy dir missing: %s", strategy_dir)
        return {
            "strategy": strategy_name, "n_papers": 0,
            "missing_extractions": [], "per_field": {}, "composite": None,
            "error": f"missing_dir:{strategy_dir}",
        }

    per_field_scores: dict[str, list[float]] = defaultdict(list)
    per_paper_means: list[float] = []
    null_buckets = {"correct_null": 0, "miss": 0, "non_null": 0,
                    "skip": 0, "tier2_pending": 0}
    n_cells_scored = 0
    n_cells_skipped = 0
    missing_extractions: list[str] = []

    for paper_id, paper_rows in gold.groupby("paper_id", sort=True):
        ext = load_extraction(strategy_dir, paper_id)
        if ext is None:
            missing_extractions.append(paper_id)
            continue

        paper_scores: list[float] = []
        for _, row in paper_rows.iterrows():
            field_id = row["field_id"]
            gold_val = row["gold_value"]
            pred_val = get_pred_value(ext, field_id)

            result = score_cell(pred_val, gold_val, field_id, skip_judge)
            if result["score"] is None:
                n_cells_skipped += 1
                if result["skipped_reason"] == "tier2_judge_pending":
                    null_buckets["tier2_pending"] += 1
                else:
                    null_buckets["skip"] += 1
                continue

            n_cells_scored += 1
            per_field_scores[field_id].append(result["score"])
            paper_scores.append(result["score"])

            if result.get("miss"):
                null_buckets["miss"] += 1
            elif pred_val is None and gold_val is None:
                null_buckets["correct_null"] += 1
            else:
                null_buckets["non_null"] += 1

        if paper_scores:
            per_paper_means.append(float(np.mean(paper_scores)))

    # Per-field summary with bootstrap CI.
    rng = np.random.default_rng(SEED)
    per_field_summary: dict[str, dict] = {}
    for field_id, scores in per_field_scores.items():
        arr = np.asarray(scores, dtype=float)
        if len(arr) == 0:
            continue
        boots = rng.choice(arr, size=(BOOTSTRAP_N, len(arr)), replace=True)
        boot_means = boots.mean(axis=1)
        per_field_summary[field_id] = {
            "n": int(len(arr)),
            "mean": float(arr.mean()),
            "ci_lo": float(np.quantile(boot_means, 0.025)),
            "ci_hi": float(np.quantile(boot_means, 0.975)),
        }

    # Composite: mean across all 30 fields the strategy was scored on,
    # weighting each field equally (1/n_fields_scored).
    field_means = [v["mean"] for v in per_field_summary.values()]
    composite_mean = float(np.mean(field_means)) if field_means else None

    # Composite CI via paper-level cluster bootstrap.
    composite_ci = None
    if per_paper_means:
        paper_arr = np.asarray(per_paper_means, dtype=float)
        boots = rng.choice(paper_arr, size=(BOOTSTRAP_N, len(paper_arr)),
                          replace=True)
        bm = boots.mean(axis=1)
        composite_ci = {
            "ci_lo": float(np.quantile(bm, 0.025)),
            "ci_hi": float(np.quantile(bm, 0.975)),
            "n_papers": int(len(paper_arr)),
        }

    return {
        "strategy": strategy_name,
        "strategy_dir": str(strategy_dir.relative_to(ROOT)),
        "n_papers_scored": len(per_paper_means),
        "n_cells_scored": n_cells_scored,
        "n_cells_skipped": n_cells_skipped,
        "missing_extractions": missing_extractions,
        "null_buckets": null_buckets,
        "composite_mean": composite_mean,
        "composite_ci": composite_ci,
        "per_field": per_field_summary,
    }


# ── CLI ────────────────────────────────────────────────────────────


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--strategies", default="all",
                  help="comma-separated, or 'all' to use the locked 22-system lineup")
    p.add_argument("--gold-methods", default=",".join(DEFAULT_GOLD_METHODS),
                  help="which gold_method values count as gold")
    p.add_argument("--skip-judge", action="store_true",
                  help="for Tier 2 prose fields, fall back to token-F1 "
                       "instead of returning a pending placeholder. Useful "
                       "for end-to-end pipeline testing before the T-021 "
                       "judge ensemble lands.")
    p.add_argument("--list-strategies", action="store_true")
    p.add_argument("--output-dir", default=str(RESULTS_DIR))
    args = p.parse_args()

    if args.list_strategies:
        for k, v in STRATEGY_DIRS.items():
            present = "OK" if v.exists() else "MISSING"
            print(f"  [{present:7s}] {k:35s} -> {v.relative_to(ROOT)}")
        return

    if args.strategies == "all":
        names = list(STRATEGY_DIRS.keys())
    else:
        names = [s.strip() for s in args.strategies.split(",")]
        unknown = [n for n in names if n not in STRATEGY_DIRS]
        if unknown:
            raise SystemExit(f"unknown strategies: {unknown}")

    gold_methods = tuple(m.strip() for m in args.gold_methods.split(","))
    gold = load_gold(gold_methods)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    summary_rows = []
    for name in names:
        result = score_strategy(name, STRATEGY_DIRS[name], gold,
                               skip_judge=args.skip_judge)
        with open(out_dir / f"{name}.json", "w") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        composite = result.get("composite_mean")
        ci = result.get("composite_ci") or {}
        summary_rows.append({
            "strategy": name,
            "n_papers": result.get("n_papers_scored"),
            "n_cells_scored": result.get("n_cells_scored"),
            "composite_mean": composite,
            "composite_ci_lo": ci.get("ci_lo"),
            "composite_ci_hi": ci.get("ci_hi"),
            "missing_papers": len(result.get("missing_extractions", [])),
        })

    summary = pd.DataFrame(summary_rows)
    summary = summary.sort_values(
        "composite_mean", ascending=False, na_position="last"
    )
    summary.to_csv(out_dir / "_summary.csv", index=False)
    log.info("wrote %d per-strategy reports + _summary.csv to %s",
            len(summary_rows), out_dir)
    print()
    print(summary.to_string(index=False, float_format=lambda x: f"{x:.4f}"
                            if pd.notna(x) else "  -  "))


if __name__ == "__main__":
    main()
