#!/usr/bin/env python3
"""Score frozen agentic systems on the held-out test 88.

Bypasses run_judge_ensemble.build_production_tasks() (which has an
agentic-on-dev-only filter for in-flight tuning). For frozen systems
that have completed prompt iteration, this script feeds (paper, field)
tasks directly to the judge.

Usage:
    python scripts/score_agentic_on_test.py \\
        --systems agentic_v2_gpt5_4_full_v4,agentic_lev_gemini_3_1_pro_gpt5_4_mini_v3
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from evaluation.field_metrics import LONG_TEXT_RAI_FIELDS  # noqa: E402
from evaluation.score_against_gold import STRATEGY_DIRS, DEFAULT_GOLD_METHODS  # noqa: E402
from evaluation.run_judge_ensemble import JUDGES, run_judge  # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--systems", required=True,
                  help="comma-separated agentic system_ids to score on test 88")
    p.add_argument("--judge", default="glm-5",
                  help="judge key from JUDGES (default: glm-5)")
    p.add_argument("--split", choices=["dev", "test"], default="test",
                  help="which split to score on (default: test)")
    args = p.parse_args()

    systems = [s.strip() for s in args.systems.split(",") if s.strip()]
    cfg = JUDGES[args.judge]

    # Load gold + selected split
    gold = pd.read_parquet(ROOT / "data" / "annotations" / "gold.parquet")
    gold = gold[gold["gold_method"].isin(DEFAULT_GOLD_METHODS)]
    gold = gold[gold["gold_value"].notna()]
    gold = gold[gold["field_id"].isin(LONG_TEXT_RAI_FIELDS)]

    split = json.loads((ROOT / "data" / "agentic" / "dev_test_split.json").read_text())
    paper_set = frozenset(split[args.split])
    gold_test = gold[gold["paper_id"].isin(paper_set)]

    print(f"Test gold: {len(gold_test)} (paper, field) cells across "
          f"{gold_test['paper_id'].nunique()} test papers, "
          f"{gold_test['field_id'].nunique()} RAI fields")

    rows = []
    for sys_id in systems:
        if sys_id not in STRATEGY_DIRS:
            print(f"  WARN: {sys_id} not in STRATEGY_DIRS, skipping")
            continue
        sdir = STRATEGY_DIRS[sys_id]
        if not sdir.exists():
            print(f"  WARN: {sys_id} dir does not exist: {sdir}")
            continue
        n_extracted = 0
        for _, g in gold_test.iterrows():
            ext_path = sdir / f"{g['paper_id']}.json"
            if not ext_path.exists():
                continue
            try:
                payload = json.load(open(ext_path))
            except Exception:
                continue
            ext = payload.get("extraction", payload)
            fid = g["field_id"]
            short = fid.split(":")[-1] if ":" in fid else fid
            cand = ext.get(fid, ext.get(short))
            if cand is None or not str(cand).strip():
                continue
            rows.append({
                "paper_id": g["paper_id"],
                "field_id": fid,
                "system_id": sys_id,
                "gold_value": str(g["gold_value"]),
                "candidate_value": str(cand).strip(),
            })
            n_extracted += 1
        print(f"  {sys_id}: {n_extracted} non-null candidate cells (test 88)")

    if not rows:
        print("No tasks built — nothing to score.")
        return

    df = pd.DataFrame(rows)
    df.insert(0, "row_id", range(1, len(df) + 1))
    print(f"\nTotal tasks: {len(df)}")
    print(f"Estimated cost: ~${len(df) * 0.0002:.2f} ({cfg.name})")

    out_path = ROOT / "data" / "judged" / f"judge_scores_{cfg.slug}.parquet"
    run_judge(cfg, df, out_path)


if __name__ == "__main__":
    main()
