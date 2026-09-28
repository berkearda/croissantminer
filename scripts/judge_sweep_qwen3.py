#!/usr/bin/env python3
"""Judge the Qwen3 size-sweep extractions with GLM-5 (v2-min rubric).

Reuses call_judge + v2min_user from scripts/judge_rerun_test88.py, i.e. the
exact prompt and parsing behind data/judged/judge_scores_v2min_glm5.parquet.
Scores test-88 Tier-2 cells with non-null gold and non-empty candidates.

Output: data/judged/judge_scores_sweep_qwen3_glm5.parquet
(same column layout as the v2min parquet; 'score' is the verdict).

Usage:
    python scripts/judge_sweep_qwen3.py --smoke      # 1 system, 1 paper
    python scripts/judge_sweep_qwen3.py              # everything
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

spec = importlib.util.spec_from_file_location(
    "jr", ROOT / "scripts" / "judge_rerun_test88.py")
jr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jr)

spec2 = importlib.util.spec_from_file_location(
    "btb", ROOT / "scripts" / "figures" / "build_test88_headline_table.py")
btb = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(btb)

SYSTEMS = ["qwen3_4b_sweep", "qwen3_8b_sweep", "qwen3_14b_sweep", "qwen3_32b_sweep"]
OUT = ROOT / "data" / "judged" / "judge_scores_sweep_qwen3_glm5.parquet"


def build_tasks(systems, papers_limit=None):
    tasks = []
    gold = btb.GOLD_TEST
    for sysid in systems:
        sdir = ROOT / "data" / "extractions" / sysid
        papers_done = set()
        for _, g in gold.iterrows():
            pid, fid = g["paper_id"], g["field_id"]
            if papers_limit is not None:
                papers_done.add(pid)
                if len(papers_done) > papers_limit and pid not in list(papers_done)[:papers_limit]:
                    continue
            if fid in btb.TIER1:
                continue
            if btb.is_null_gold(g["gold_value"]):
                continue
            path = sdir / f"{pid}.json"
            if not path.exists():
                continue
            payload = json.load(open(path))
            ext = payload.get("extraction", payload)
            if not isinstance(ext, dict):
                continue  # failed extraction: all cells score as misses
            short = fid.split(":")[-1]
            cand = ext.get(fid, ext.get(short))
            if cand is None or not str(cand).strip():
                continue  # miss -> scored 0 downstream, no judge needed
            tasks.append({"system_id": sysid, "paper_id": pid, "field_id": fid,
                          "gold_value": str(g["gold_value"]),
                          "candidate": str(cand)})
    return tasks


def judge_one(t):
    r = jr.call_judge(jr.v2min_user, t["field_id"],
                      t["gold_value"][:8000], t["candidate"][:8000])
    row = dict(t)
    if r is None:
        row.update(score=None, reason="JUDGE_FAILED", input_tokens=0, output_tokens=0)
    else:
        row.update(score=r["score"], reason=r["reason"],
                   input_tokens=r["input_tokens"], output_tokens=r["output_tokens"])
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--workers", type=int, default=25)
    args = ap.parse_args()

    systems = SYSTEMS[:1] if args.smoke else SYSTEMS
    limit = 1 if args.smoke else None
    tasks = build_tasks(systems, papers_limit=limit)
    print(f"{len(tasks)} judge calls to make across {len(systems)} system(s)")

    done_keys = set()
    existing = None
    if OUT.exists():
        existing = pd.read_parquet(OUT)
        done_keys = set(zip(existing.system_id, existing.paper_id, existing.field_id))
        tasks = [t for t in tasks
                 if (t["system_id"], t["paper_id"], t["field_id"]) not in done_keys]
        print(f"resume: {len(done_keys)} already judged, {len(tasks)} remaining")

    rows = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(judge_one, t): t for t in tasks}
        for i, f in enumerate(as_completed(futs), 1):
            rows.append(f.result())
            if i % 200 == 0:
                print(f"  {i}/{len(tasks)}")
                # checkpoint
                df = pd.DataFrame(rows)
                out = pd.concat([existing, df]) if existing is not None else df
                out.to_parquet(OUT, index=False)

    df = pd.DataFrame(rows)
    out = pd.concat([existing, df]) if existing is not None else df
    out.to_parquet(OUT, index=False)
    fails = int((out["score"].isna()).sum()) if len(out) else 0
    print(f"saved {len(out)} rows to {OUT} | parse failures: {fails}")
    if len(df):
        print("score distribution (new rows):")
        print(df["score"].value_counts(dropna=False).to_string())


if __name__ == "__main__":
    main()
