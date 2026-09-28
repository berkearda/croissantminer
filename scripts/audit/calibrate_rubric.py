#!/usr/bin/env python3
"""Calibrate the v3 rubric against human consensus using Claude Opus 4.7.

Calls Opus 4.7 on the 30-cell calibration set, parses responses,
computes the same 4 agreement metrics used for Stage A judge selection
(Spearman rho, Pearson r, Cohen quadratic kappa, Krippendorff alpha
ordinal). Reports per-cell disagreements so we can iterate the rubric.

Usage:
  python scripts/audit/calibrate_rubric.py [--set calibration|validation]
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import cohen_kappa_score

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

# Load .env so ANTHROPIC_API_KEY etc. are picked up by the judge runner
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from evaluation.run_judge_ensemble import (  # noqa: E402
    JUDGES,
    JUDGE_SYSTEM,
    JUDGE_USER_TEMPLATE,
    JUDGE_USER_TEMPLATE_FEWSHOT,
    call_judge,
    parse_judge_response,
)
from evaluation.audit_report import krippendorff_alpha_ordinal  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("calibrate")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--set", choices=("calibration", "validation"), default="calibration")
    p.add_argument("--judge", default="claude-opus-4-7")
    p.add_argument("--fewshot", action="store_true",
                  help="Use 3-anchor few-shot prompt (JUDGE_USER_TEMPLATE_FEWSHOT)")
    args = p.parse_args()

    parquet_path = ROOT / "data" / "audit" / f"_{args.set}_30.parquet"
    suffix = "_fewshot" if args.fewshot else ""
    out_path = ROOT / "data" / "audit" / f"_{args.set}_judge_{JUDGES[args.judge].slug}{suffix}.parquet"
    df = pd.read_parquet(parquet_path)
    log.info("loaded %d cells from %s", len(df), parquet_path.name)

    cfg = JUDGES[args.judge]
    template = JUDGE_USER_TEMPLATE_FEWSHOT if args.fewshot else JUDGE_USER_TEMPLATE
    log.info("judge: %s (%s) | prompt: %s", cfg.name, cfg.model_id,
            "few-shot (3 anchors)" if args.fewshot else "zero-shot")

    rows = []
    n_fail = 0
    t0 = time.time()
    for i, task in enumerate(df.itertuples(index=False)):
        user = template.format(
            field_id=task.field_id,
            gold_value=str(task.gold_value)[:8000],
            candidate_value=str(task.candidate_value)[:8000],
        )
        try:
            raw, usage = call_judge(cfg, JUDGE_SYSTEM, user)
            score, reason = parse_judge_response(raw)
            rows.append({
                "row_id": task.row_id,
                "paper_id": task.paper_id,
                "field_id": task.field_id,
                "system_id": task.system_id,
                "consensus": int(task.rating_consensus),
                "judge_score": int(score) if score is not None else np.nan,
                "judge_reason": reason,
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
            })
            if score is None:
                n_fail += 1
        except Exception as e:
            log.warning("call failed for row %s: %s", task.row_id, e)
            rows.append({
                "row_id": task.row_id,
                "paper_id": task.paper_id,
                "field_id": task.field_id,
                "system_id": task.system_id,
                "consensus": int(task.rating_consensus),
                "judge_score": np.nan,
                "judge_reason": f"ERROR: {e}",
                "input_tokens": 0,
                "output_tokens": 0,
            })
            n_fail += 1
        if (i + 1) % 5 == 0:
            elapsed = time.time() - t0
            log.info("  %d/%d done (%.1fs)", i + 1, len(df), elapsed)

    res = pd.DataFrame(rows)
    res.to_parquet(out_path, index=False)
    elapsed = time.time() - t0
    cost = (res["input_tokens"].sum() * cfg.input_price_per_mtok +
            res["output_tokens"].sum() * cfg.output_price_per_mtok) / 1e6
    log.info("done: %d rows, %d failures, %.1fs, cost=$%.3f",
             len(res), n_fail, elapsed, cost)

    # === Agreement metrics ===
    valid = res.dropna(subset=["judge_score"])
    if valid.empty:
        log.error("no valid scores; aborting metric computation")
        return

    h = valid["consensus"].astype(int).values
    j = valid["judge_score"].astype(int).values

    spearman = stats.spearmanr(h, j).statistic
    pearson = stats.pearsonr(h, j).statistic
    kappa_q = cohen_kappa_score(h, j, weights="quadratic")
    krip = krippendorff_alpha_ordinal(np.vstack([h, j]).astype(float))
    n_match = (h == j).sum()
    n_off1 = (np.abs(h - j) == 1).sum()
    n_off2 = (np.abs(h - j) == 2).sum()

    print()
    print(f"=== {args.set.upper()} SET — {cfg.name} vs human consensus (n={len(valid)}) ===")
    print(f"  exact match:        {n_match}/{len(valid)} ({n_match/len(valid)*100:.1f}%)")
    print(f"  off-by-1:           {n_off1}/{len(valid)} ({n_off1/len(valid)*100:.1f}%)")
    print(f"  off-by-2 (worst):   {n_off2}/{len(valid)} ({n_off2/len(valid)*100:.1f}%)")
    print(f"  Spearman rho:       {spearman:.3f}")
    print(f"  Pearson r:          {pearson:.3f}")
    print(f"  Cohen kappa (quad): {kappa_q:.3f}")
    print(f"  Krippendorff alpha: {krip:.3f}")

    # Confusion matrix
    print(f"\n  confusion matrix (rows=human, cols=judge):")
    print(f"           judge=1  judge=2  judge=3")
    for hv in (1, 2, 3):
        cnts = [((h == hv) & (j == jv)).sum() for jv in (1, 2, 3)]
        print(f"  human={hv}      {cnts[0]:3d}      {cnts[1]:3d}      {cnts[2]:3d}")

    # Disagreements
    disagree = valid[valid["consensus"] != valid["judge_score"]]
    print(f"\n  disagreements: {len(disagree)}/{len(valid)}")
    if len(disagree):
        print(f"\n  --- disagreement details ---")
        for _, r in disagree.iterrows():
            print(f"  row {int(r['row_id']):3d} {r['field_id']:35s} "
                  f"human={int(r['consensus'])} judge={int(r['judge_score'])} :: {r['judge_reason'][:120]}")


if __name__ == "__main__":
    main()
