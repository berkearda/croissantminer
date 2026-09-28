"""Judge RAI cells that the Table 2 scorer needs but that have no verdict.

The scorer (scripts/figures/build_test88_headline_table.py) silently skips an RAI
cell whose gold is documented and whose candidate is non-empty when no judge verdict
exists. On 2026-09-26 this was the case for 26 cells over six agentic Table 2 systems
(five cells judged in May for most systems but not these), plus the
same cells for the two _rerun2609 systems. Same judge, prompt and call code as the
headline (imported from scripts/judge_rerun_test88.py); output is a NEW file:

  data/judged/judge_scores_v2min_glm5_gapfill_2026-09.parquet
"""
import argparse
import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
OUT = ROOT / "data" / "judged" / "judge_scores_v2min_glm5_gapfill_2026-09.parquet"


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


judge = _load("judge_rerun_test88", "scripts/judge_rerun_test88.py")
h = _load("h", "scripts/figures/build_test88_headline_table.py")
b = _load("b", "scripts/camera_ready/build_camera_ready_tables.py")


def missing_cells(sids):
    have = h.judges[h.judges.score.notna()]
    have = set(zip(have.system_id, have.paper_id, have.field_id))
    tasks = []
    for sid in sids:
        sdir = h.STRATEGY_DIRS[sid]
        for _, g in h.GOLD_TEST.iterrows():
            fid = g["field_id"]
            if fid not in h.LONG_TEXT_RAI_FIELDS or h.is_null_gold(g["gold_value"]):
                continue
            fp = sdir / f"{g['paper_id']}.json"
            if not fp.exists() or (sid, g["paper_id"], fid) in have:
                continue
            ext = json.load(open(fp)).get("extraction", {})
            cand = ext.get(fid, ext.get(fid.split(":")[-1]))
            if cand is None or not str(cand).strip():
                continue
            tasks.append({"paper_id": g["paper_id"], "field_id": fid, "system_id": sid,
                          "gold_value": str(g["gold_value"]), "candidate": str(cand), "v1_score": float("nan")})
    return tasks


def main(dry_run):
    sids = (list(b.T2_LABELS.values()) + ["claude_sonnet_4_5", "agentic_v2_sonnet_4_5", "agentic_lev_sonnet_4_5"]  # last two: Appendix H sweep
            + [k for k in h.STRATEGY_DIRS if k.endswith("_rerun2609")])
    tasks = missing_cells(sids)
    print(f"{len(tasks)} cells without a verdict over {len(set(t['system_id'] for t in tasks))} systems")
    if dry_run or not tasks:
        return
    rows = [judge.process_cell_v2min(t) for t in tasks]
    new = pd.DataFrame(rows)
    new["source"] = "judged_2026-09-26_gapfill"
    old = pd.read_parquet(OUT) if OUT.exists() else None
    out = pd.concat([old, new], ignore_index=True) if old is not None else new
    out = out[out.score.notna()].drop_duplicates(subset=["system_id", "paper_id", "field_id"], keep="last")
    out.to_parquet(OUT, index=False)
    print(f"saved {len(out)} verdicts ({int(new.score.isna().sum())} failed this run)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    main(ap.parse_args().dry_run)
