#!/usr/bin/env python3
"""Judge for the re-annotation pilot (NeurIPS rebuttal, T-088).

Two modes, both using the paper's judge (GLM-5, v2-min rubric) via the same
call path as the headline scores:

  goldpair : semantic agreement between the pilot gold (GPT-5.4-seeded,
             re-annotated) and the current gold (Sonnet-4.5-seeded), one call
             per cell where both are non-null. Reference = current gold,
             candidate = pilot gold.
  systems  : score system outputs against the PILOT gold, for the ranking
             stability check. Reads data/rebuttal_pilot/pilot_judge_todo.csv.

Outputs:
  data/judged/judge_pilot_goldpair_glm5.parquet
  data/judged/judge_scores_pilot_glm5.parquet
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

PILOT = ROOT / "data" / "rebuttal_pilot"


def judge_one(t):
    r = jr.call_judge(jr.v2min_user, t["field_id"],
                      str(t["reference"])[:8000], str(t["candidate"])[:8000])
    row = {k: t[k] for k in t if k not in ("reference", "candidate")}
    if r is None:
        row.update(score=None, reason="JUDGE_FAILED")
    else:
        row.update(score=r["score"], reason=r["reason"])
    return row


def run(tasks, out_path, workers):
    done = set()
    existing = None
    keycols = [c for c in ("system_id", "paper_id", "field_id") if c in tasks[0]]
    if out_path.exists():
        existing = pd.read_parquet(out_path)
        existing = existing[existing["score"].notna()]
        done = set(map(tuple, existing[keycols].values))
        tasks = [t for t in tasks if tuple(t[c] for c in keycols) not in done]
        print(f"resume: {len(done)} judged, {len(tasks)} remaining")
    print(f"{len(tasks)} judge calls")
    rows = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = [pool.submit(judge_one, t) for t in tasks]
        for i, f in enumerate(as_completed(futs), 1):
            rows.append(f.result())
            if i % 250 == 0:
                print(f"  {i}/{len(tasks)}")
                df = pd.DataFrame(rows)
                pd.concat([existing, df]).to_parquet(out_path, index=False) \
                    if existing is not None else df.to_parquet(out_path, index=False)
    df = pd.DataFrame(rows)
    out = pd.concat([existing, df]) if existing is not None else df
    out.to_parquet(out_path, index=False)
    print(f"saved {len(out)} rows to {out_path} | failures: "
          f"{int(out['score'].isna().sum())}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["goldpair", "systems"])
    ap.add_argument("--workers", type=int, default=25)
    args = ap.parse_args()

    pilot = pd.read_parquet(PILOT / "pilot_gold.parquet")
    pilot = pilot[pilot.gold_value.notna()]
    cur = pd.read_parquet(ROOT / "data/annotations/gold.parquet")

    if args.mode == "goldpair":
        m = pilot.merge(cur[["paper_id", "field_id", "gold_value"]],
                        on=["paper_id", "field_id"], suffixes=("_pilot", "_cur"))
        # only cells where both gold sets have real content; null-vs-null and
        # null-vs-value are handled by the null-status agreement statistic
        m = m[~m.gold_value_pilot.map(btb.is_null_gold)
              & ~m.gold_value_cur.map(btb.is_null_gold)]
        tasks = [{"paper_id": r.paper_id, "field_id": r.field_id,
                  "reference": r.gold_value_cur, "candidate": r.gold_value_pilot}
                 for r in m.itertuples()]
        run(tasks, ROOT / "data/judged/judge_pilot_goldpair_glm5.parquet",
            args.workers)
        return

    todo = pd.read_csv(PILOT / "pilot_judge_todo.csv")
    gold_lookup = {(r.paper_id, r.field_id): r.gold_value
                   for r in pilot.itertuples()}
    tasks = []
    for r in todo.itertuples():
        gold = gold_lookup.get((r.paper_id, r.field_id))
        if gold is None:
            continue
        sdir = btb.STRATEGY_DIRS.get(r.system_id)
        if sdir is None:
            continue
        path = sdir / f"{r.paper_id}.json"
        if not path.exists():
            continue
        payload = json.load(open(path))
        ext = payload.get("extraction", payload)
        if not isinstance(ext, dict):
            continue
        cand = ext.get(r.field_id, ext.get(r.field_id.split(":")[-1]))
        if cand is None or not str(cand).strip():
            continue
        tasks.append({"system_id": r.system_id, "paper_id": r.paper_id,
                      "field_id": r.field_id, "reference": gold,
                      "candidate": cand})
    run(tasks, ROOT / "data/judged/judge_scores_pilot_glm5.parquet",
        args.workers)


if __name__ == "__main__":
    main()
