"""Judge the re-run Locator-Extractor Gemini cells with the headline v2-min GLM-5 judge.

Prompt, model and call code are imported from scripts/judge_rerun_test88.py
(not copied), so the verdicts match the pinned judge file. That script writes
into data/judged/judge_scores_v2min_glm5.parquet, which must stay as released,
so this wrapper writes a NEW file instead:

  data/judged/judge_scores_v2min_glm5_lev_rerun_2026-09.parquet

For each new system (merge_lev_rerun.py) it holds:
  - verdicts copied from the pinned file for papers that were not re-run
    (source = "copied:<original system_id>"), and
  - new verdicts for every RAI cell of a re-run paper that the scorer needs:
    gold documented and candidate non-empty (source = "judged_2026-09-26").
Resumable: cells already in the output are skipped.
"""
import argparse
import importlib.util
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.dont_write_bytecode = True
OUT = ROOT / "data" / "judged" / "judge_scores_v2min_glm5_lev_rerun_2026-09.parquet"
PINNED = ROOT / "data" / "judged" / "judge_scores_v2min_glm5.parquet"


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


judge = _load("judge_rerun_test88", "scripts/judge_rerun_test88.py")
h = _load("h", "scripts/figures/build_test88_headline_table.py")


def main(concurrency, dry_run, limit=None):
    pinned = pd.read_parquet(PINNED)
    done = pd.read_parquet(OUT) if OUT.exists() else pd.DataFrame(columns=list(pinned.columns) + ["source"])
    done = done[done.score.notna()]            # failed calls (e.g. HTTP 402) are retried
    done_keys = set(zip(done.system_id, done.paper_id, done.field_id))
    copied, tasks = [], []
    for manifest in sorted((ROOT / "data" / "extractions").glob("*_rerun2609/_rerun_manifest.json")):
        m = json.loads(manifest.read_text())
        new_sid, old_sid, rerun = m["system_id"], m["based_on"], set(m["replaced_papers"])
        old = pinned[(pinned.system_id == old_sid) & ~pinned.paper_id.isin(rerun)].copy()
        old["source"] = f"copied:{old_sid}"
        old["system_id"] = new_sid
        copied.append(old[[k not in done_keys for k in zip(old.system_id, old.paper_id, old.field_id)]])
        sdir = manifest.parent
        for _, g in h.GOLD_TEST[h.GOLD_TEST.paper_id.isin(rerun)].iterrows():
            fid = g["field_id"]
            if fid not in h.LONG_TEXT_RAI_FIELDS or h.is_null_gold(g["gold_value"]):
                continue
            ext = json.load(open(sdir / f"{g['paper_id']}.json")).get("extraction", {})
            cand = ext.get(fid, ext.get(fid.split(":")[-1]))
            if cand is None or not str(cand).strip() or (new_sid, g["paper_id"], fid) in done_keys:
                continue
            tasks.append({"paper_id": g["paper_id"], "field_id": fid, "system_id": new_sid,
                          "gold_value": str(g["gold_value"]), "candidate": str(cand), "v1_score": float("nan")})
    n_copy = sum(len(c) for c in copied)
    print(f"copy {n_copy} verdicts from the pinned file; judge {len(tasks)} new cells "
          f"(model {judge.MODEL}); output {OUT.relative_to(ROOT)}", flush=True)
    if dry_run:
        return
    if limit:
        tasks, copied = tasks[:limit], []
    results, t0 = [], time.time()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futs = [pool.submit(judge.process_cell_v2min, t) for t in tasks]
        for i, fut in enumerate(as_completed(futs), 1):
            results.append(fut.result())
            if i % 100 == 0 or i == len(tasks):
                print(f"  {i}/{len(tasks)} in {(time.time() - t0) / 60:.1f} min", flush=True)
    new = pd.DataFrame(results)
    if len(new):
        new["source"] = "judged_2026-09-26"
    out = pd.concat([done, *copied, new], ignore_index=True)
    out = out.drop_duplicates(subset=["system_id", "paper_id", "field_id"], keep="last")
    out.to_parquet(OUT, index=False)
    errors = new.score.isna().sum() if len(new) else 0
    cost = (new.input_tokens.sum() * 0.40 + new.output_tokens.sum() * 1.30) / 1e6 if len(new) else 0
    print(f"saved {len(out)} rows; new verdicts {len(new)} (errors {errors}); judge cost ${cost:.2f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--concurrency", type=int, default=10)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=None, help="judge only the first N cells (smoke test)")
    a = ap.parse_args()
    main(a.concurrency, a.dry_run, a.limit)
