"""Paraphrase the free-text gold values for the 30 parser-ablation papers (paraphrased-gold check).

Robustness / circularity check: reword each GT value (meaning preserved, wording
changed) with Sonnet 4.6 and GPT-5.4, producing paraphrased gold parquets that
plug into the SAME scoring pipeline (run_judge_ensemble + reproduce_dev.py).

Scope: the 23 free-text fields (20 RAI long-text + 3 short-text); non-null cells
only. Constrained fields and [NULL] cells are copied through unchanged.

Output: data/annotations/gold_paraphrased_<model>.parquet  (same schema as
gold.parquet, only gold_value reworded for the target cells).
"""
import argparse, hashlib, json, sys, threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from evaluation.field_metrics import LONG_TEXT_RAI_FIELDS, SHORT_TEXT_FIELDS  # noqa: E402
from scripts._agentic_helpers import resolve_backbone, call_llm  # noqa: E402

SETTLED = {"unanimous_3of3", "unanimous_4of4", "majority_2of3",
           "majority_3of4", "adjudicated", "tie_resolved_via_correction"}
TARGET = set(LONG_TEXT_RAI_FIELDS) | set(SHORT_TEXT_FIELDS)
SAMPLE = ROOT / "data/extractions/parser_ablation/sample30.json"

SYSTEM = ("You reword text while preserving its exact meaning. You never add, "
          "remove, or alter any facts, numbers, names, or claims.")
USER = ("Reword the following ground-truth value for the metadata field "
        "'{field}'. Express the SAME information with different wording and "
        "sentence structure. Do not add or drop any detail. Output ONLY the "
        "reworded text, with no preamble.\n\nValue:\n{value}")


def is_null(v):
    s = str(v).strip()
    return v is None or s == "" or s.upper().startswith("[NULL")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="sonnet-4-6 or gpt-5.4")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    mslug = args.model.replace("-", "_").replace(".", "_")
    cfg = resolve_backbone(args.model)
    cache_fp = ROOT / f"data/annotations/_paraphrase_cache_{mslug}.json"
    cache = json.loads(cache_fp.read_text()) if cache_fp.exists() else {}
    lock = threading.Lock()

    papers = json.loads(SAMPLE.read_text())["papers"]
    gold = pd.read_parquet(ROOT / "data/annotations/gold.parquet")
    settled = gold[gold.gold_method.isin(SETTLED)]
    todo = settled[(settled.paper_id.isin(papers)) & (settled.field_id.isin(TARGET))]
    todo = todo[~todo.gold_value.apply(is_null)]
    print(f"{args.model}: paraphrasing {len(todo)} non-null cells", flush=True)

    def work(row):
        key = hashlib.md5(f"{row.field_id}||{row.gold_value}".encode()).hexdigest()
        with lock:
            if key in cache:
                return row.Index, cache[key]
        user = USER.format(field=row.field_id, value=str(row.gold_value)[:6000])
        try:
            out, _ = call_llm(cfg, SYSTEM, user, max_tokens=2048)
            out = out.strip()
        except Exception as e:
            print(f"  FAIL {row.paper_id}/{row.field_id}: {type(e).__name__}", flush=True)
            return row.Index, None
        with lock:
            cache[key] = out
        return row.Index, out

    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for idx, out in pool.map(work, todo.itertuples()):
            done += 1
            if done % 50 == 0:
                cache_fp.write_text(json.dumps(cache, ensure_ascii=False))
                print(f"  {done}/{len(todo)}", flush=True)
    cache_fp.write_text(json.dumps(cache, ensure_ascii=False))

    # Build paraphrased gold: copy full gold, replace gold_value for target cells
    out_gold = gold.copy()
    n_replaced = 0
    for row in todo.itertuples():
        key = hashlib.md5(f"{row.field_id}||{row.gold_value}".encode()).hexdigest()
        para = cache.get(key)
        if para:
            out_gold.loc[row.Index, "gold_value"] = para
            n_replaced += 1
    out_fp = ROOT / f"data/annotations/gold_paraphrased_{mslug}.parquet"
    out_gold.to_parquet(out_fp, index=False)
    print(f"replaced {n_replaced} cells -> {out_fp}", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
