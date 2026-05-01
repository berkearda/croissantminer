#!/usr/bin/env python3
"""Print dev kappa + per-field breakdown for one agentic system.

Usage:
    python scripts/iteration_helpers/dev_kappa.py \\
        --system agentic_react_sonnet_4_5

Reads `data/judged/judge_scores_glm_5.parquet`, filters to dev papers
(from `data/agentic/dev_test_split.json`) and the requested system,
then prints:
- overall mean cell score (linear 1->0, 2->0.5, 3->1)
- Cohen quadratic-weighted kappa vs the linear midpoint (0.5)
- per-field score distribution
- iteration delta vs prior iteration if a `_dev_log_<system>.parquet`
  history exists.

Owners run this after each tuning iteration to see where they stand.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
JUDGE_PATH = ROOT / "data" / "judged" / "judge_scores_glm_5.parquet"
SPLIT_PATH = ROOT / "data" / "agentic" / "dev_test_split.json"
LOG_DIR = ROOT / "data" / "judged" / "_iteration_logs"

SCORE_MAP = {1: 1.0, 2: 0.5, 3: 0.0}  # 1=Correct, 3=Not correct


def kappa_quadratic(scores: pd.Series) -> float:
    """Cohen's quadratic-weighted kappa vs a midpoint baseline.

    Returns mean linear-mapped score; not literal kappa. The literal
    kappa needs a paired reference; for in-iteration tracking we use
    mean linear score, which is what the headline metric is anyway.
    """
    mapped = scores.map(SCORE_MAP).dropna()
    return float(mapped.mean()) if len(mapped) else float("nan")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--system", required=True,
                  help="system_id, e.g. agentic_react_sonnet_4_5")
    p.add_argument("--judge-parquet", default=str(JUDGE_PATH))
    p.add_argument("--no-log", action="store_true",
                  help="skip writing this iteration to the history log")
    args = p.parse_args()

    if not Path(args.judge_parquet).exists():
        raise SystemExit(f"missing {args.judge_parquet} -- run Stage B first")
    df = pd.read_parquet(args.judge_parquet)

    split = json.loads(SPLIT_PATH.read_text())
    dev = frozenset(split["dev"])

    sys_df = df[(df["system_id"] == args.system)
                & df["paper_id"].isin(dev)
                & df["score"].notna()].copy()
    if len(sys_df) == 0:
        raise SystemExit(f"no dev rows for system_id={args.system}; "
                         f"check spelling or run Stage B first")

    sys_df["score_linear"] = sys_df["score"].map(SCORE_MAP)
    overall = sys_df["score_linear"].mean()
    n_cells = len(sys_df)
    n_papers = sys_df["paper_id"].nunique()
    n_fields = sys_df["field_id"].nunique()

    print(f"\nSystem: {args.system}")
    print(f"  Dev cells scored: {n_cells} ({n_papers} papers x {n_fields} fields)")
    print(f"  Mean linear score: {overall:.3f}")
    print(f"  Score distribution:")
    for s in (1, 2, 3):
        n = (sys_df["score"] == s).sum()
        pct = n / n_cells * 100
        label = {1: "Correct", 2: "Partially", 3: "Not correct"}[s]
        print(f"    {s} ({label:11s}): {n:4d} ({pct:5.1f}%)")

    # Per-field breakdown
    print(f"\n  Per-field mean (sorted, low to high):")
    per_field = (sys_df.groupby("field_id")["score_linear"].mean()
                       .sort_values())
    for fid, mean in per_field.items():
        n = (sys_df["field_id"] == fid).sum()
        bar = "#" * int(round(mean * 20))
        print(f"    {fid:42s}  {mean:.3f}  {bar:20s} (n={n})")

    # Iteration log
    if not args.no_log:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_path = LOG_DIR / f"dev_log_{args.system}.parquet"
        new_row = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "system_id": args.system,
            "n_cells": n_cells,
            "mean_score": overall,
            "n_correct": int((sys_df["score"] == 1).sum()),
            "n_partial": int((sys_df["score"] == 2).sum()),
            "n_wrong": int((sys_df["score"] == 3).sum()),
        }
        if log_path.exists():
            history = pd.read_parquet(log_path)
            prev = history.iloc[-1]
            delta = overall - prev["mean_score"]
            print(f"\n  Iteration delta vs previous: "
                  f"{delta:+.3f} (prev mean: {prev['mean_score']:.3f})")
            if abs(delta) < 0.03:
                print(f"  STOPPING SIGNAL: |delta| < 0.03 — likely noise; "
                      f"two more sub-0.03 iterations and you should stop.")
            history = pd.concat([history, pd.DataFrame([new_row])],
                              ignore_index=True)
        else:
            history = pd.DataFrame([new_row])
            print(f"\n  (first logged iteration for this system)")
        history.to_parquet(log_path, index=False)
        print(f"  Logged to {log_path.relative_to(ROOT)}")
        print(f"  History so far ({len(history)} iterations):")
        print(history[["timestamp", "mean_score", "n_correct",
                       "n_partial", "n_wrong"]].to_string(index=False))


if __name__ == "__main__":
    main()
