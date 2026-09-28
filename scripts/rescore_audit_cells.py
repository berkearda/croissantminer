"""Rescore the 178 audit-corrected test-88 cells under v1 + v2min judges,
plus re-run rule-based scoring for Tier 1 cells.

Reads the new gold from data/annotations/gold.parquet, identifies all
(paper_id, field_id) pairs where gold_method='audit_corrected_2026-05-04'
on test-88 papers, and:

- For Tier 2 cells (LLM judge): deletes stale rows from
  judge_scores_glm_5.parquet AND judge_scores_v2min_glm5.parquet, then
  re-calls GLM-5 with v1 and v2min prompts on each (system, paper, field).
- For Tier 1 cells (constrained / token-F1): deletes stale rows from
  tier1_scores.parquet, then re-runs evaluation/field_metrics.score_field
  on each affected (system, paper, field).

Writes back to all three parquets.
"""
import json, os, sys, time, urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

from evaluation.score_against_gold import STRATEGY_DIRS
from evaluation.field_metrics import (
    CONSTRAINED_FIELDS, SHORT_TEXT_FIELDS, score_field,
)
from scripts.judge_rerun_test88 import (
    v1_user, v2min_user, call_judge, get_candidate, MODEL,
)

API_KEY = os.environ["DEEPINFRA_API_KEY"]
TIER1 = set(CONSTRAINED_FIELDS) | set(SHORT_TEXT_FIELDS)

split = json.loads((ROOT / "data/agentic/dev_test_split.json").read_text())
TEST_PAPERS = frozenset(split["test"])

print("[load] gold.parquet …", flush=True)
GOLD = pd.read_parquet(ROOT / "data/annotations/gold.parquet")
audit_test = GOLD[
    (GOLD["gold_method"] == "audit_corrected_2026-05-04")
    & (GOLD["paper_id"].isin(TEST_PAPERS))
    & GOLD["gold_value"].notna()
].copy()
print(f"[plan] audit-corrected test-88 cells: {len(audit_test)}", flush=True)

audit_keys = set(zip(audit_test["paper_id"], audit_test["field_id"]))
gold_lookup = {(r["paper_id"], r["field_id"]): r["gold_value"]
               for _, r in audit_test.iterrows()}

# Split into Tier 1 and Tier 2
tier1_keys = {k for k in audit_keys if k[1] in TIER1}
tier2_keys = audit_keys - tier1_keys
print(f"[plan] Tier 1 (rule-based): {len(tier1_keys)}", flush=True)
print(f"[plan] Tier 2 (LLM judge):  {len(tier2_keys)}", flush=True)

# === Step 1: drop stale rows from all 3 parquets ===
def prune_and_save(path, keys, label):
    df = pd.read_parquet(path)
    df["__k"] = list(zip(df["paper_id"], df["field_id"]))
    n0 = len(df)
    keep = df[~df["__k"].isin(keys)].drop(columns=["__k"])
    keep.to_parquet(path, index=False)
    print(f"[prune] {label}: {n0} -> {len(keep)} (-{n0 - len(keep)})", flush=True)

prune_and_save(ROOT / "data/judged/judge_scores_glm_5.parquet", audit_keys, "v1")
prune_and_save(ROOT / "data/judged/judge_scores_v2min_glm5.parquet", audit_keys, "v2min")
prune_and_save(ROOT / "data/judged/tier1_scores.parquet", audit_keys, "tier1")

# === Step 2: build the (system, paper, field) task list from existing systems in v1 ===
v1_existing = pd.read_parquet(ROOT / "data/judged/judge_scores_glm_5_pre_audit_2026-05-04.parquet")
v2_existing = pd.read_parquet(ROOT / "data/judged/judge_scores_v2min_glm5_pre_audit_2026-05-04.parquet")
t1_existing = pd.read_parquet(ROOT / "data/judged/tier1_scores_pre_audit_2026-05-04.parquet")

# Union of (system_id) across snapshots
all_systems = sorted(set(v1_existing["system_id"]).union(v2_existing["system_id"]).union(t1_existing["system_id"]))
print(f"[plan] Systems to rescore: {len(all_systems)}", flush=True)

# === Step 3: Tier 1 rule-based rescore ===
tier1_rows = []
for paper, field in tier1_keys:
    gold_value = gold_lookup[(paper, field)]
    for sys_id in all_systems:
        sdir = STRATEGY_DIRS.get(sys_id)
        if sdir is None:
            continue
        ext_path = sdir / f"{paper}.json"
        if not ext_path.exists():
            continue
        try:
            payload = json.loads(ext_path.read_text())
            ext = payload.get("extraction", payload) if isinstance(payload, dict) else {}
        except Exception:
            continue
        short = field.split(":")[-1] if ":" in field else field
        cand = ext.get(field, ext.get(short))
        if cand is None or not str(cand).strip():
            continue
        result = score_field(str(cand), gold_value, field)
        if result.get("skipped") or result.get("score") is None:
            continue
        tier1_rows.append({
            "system_id": sys_id, "paper_id": paper, "field_id": field,
            "category": result["category"],
            "score": float(result["score"]),
            "metric": result["metric"],
        })
print(f"[tier1] computed {len(tier1_rows)} rule-based scores", flush=True)
if tier1_rows:
    t1 = pd.read_parquet(ROOT / "data/judged/tier1_scores.parquet")
    t1 = pd.concat([t1, pd.DataFrame(tier1_rows)], ignore_index=True)
    t1.to_parquet(ROOT / "data/judged/tier1_scores.parquet", index=False)
    print(f"[tier1] saved -> tier1_scores.parquet ({len(t1)} total rows)", flush=True)

# === Step 4: Tier 2 LLM judge rescore (v1 + v2min, parallel) ===
tier2_tasks = []
for paper, field in tier2_keys:
    gold_value = str(gold_lookup[(paper, field)])
    for sys_id in all_systems:
        cand = get_candidate(sys_id, paper, field)
        if cand is None or not str(cand).strip():
            continue
        tier2_tasks.append({
            "paper_id": paper, "field_id": field, "system_id": sys_id,
            "gold_value": gold_value, "candidate": str(cand),
        })
print(f"[tier2] tasks queued: {len(tier2_tasks)} (each → 2 judge calls)", flush=True)

def score_one(task):
    out = {**task}
    try:
        r1 = call_judge(v1_user, task["field_id"], task["gold_value"][:8000], task["candidate"][:8000])
        out["v1_score"], out["v1_reason"] = r1["score"], r1["reason"]
        out["v1_in_tok"], out["v1_out_tok"] = r1["input_tokens"], r1["output_tokens"]
    except Exception as e:
        out["v1_score"], out["v1_reason"] = None, f"err:{e}"
        out["v1_in_tok"], out["v1_out_tok"] = 0, 0
    try:
        r2 = call_judge(v2min_user, task["field_id"], task["gold_value"][:8000], task["candidate"][:8000])
        out["v2_score"], out["v2_reason"] = r2["score"], r2["reason"]
        out["v2_in_tok"], out["v2_out_tok"] = r2["input_tokens"], r2["output_tokens"]
    except Exception as e:
        out["v2_score"], out["v2_reason"] = None, f"err:{e}"
        out["v2_in_tok"], out["v2_out_tok"] = 0, 0
    return out

results = []
t0 = time.time()
with ThreadPoolExecutor(max_workers=30) as ex:
    futures = [ex.submit(score_one, t) for t in tier2_tasks]
    for i, fut in enumerate(as_completed(futures), 1):
        results.append(fut.result())
        if i % 100 == 0:
            elapsed = time.time() - t0
            rate = i / elapsed
            eta = (len(futures) - i) / rate if rate else 0
            print(f"[tier2] {i}/{len(futures)} done ({rate:.1f}/s, ETA {eta:.0f}s)", flush=True)
print(f"[tier2] done in {time.time()-t0:.1f}s", flush=True)

# === Step 5: persist v1 + v2min scores ===
v1_rows = [{
    "paper_id": r["paper_id"], "field_id": r["field_id"], "system_id": r["system_id"],
    "judge": "glm_5", "score": r["v1_score"], "reason": r["v1_reason"],
    "input_tokens": r["v1_in_tok"], "output_tokens": r["v1_out_tok"],
    "scored_at": pd.Timestamp.utcnow().isoformat(),
} for r in results if r["v1_score"] is not None]

v2_rows = [{
    "paper_id": r["paper_id"], "field_id": r["field_id"], "system_id": r["system_id"],
    "gold_value": r["gold_value"][:8000], "candidate": r["candidate"][:8000],
    "v1_score": r["v1_score"], "score": r["v2_score"], "reason": r["v2_reason"],
    "input_tokens": r["v2_in_tok"], "output_tokens": r["v2_out_tok"],
} for r in results if r["v2_score"] is not None]

v1_path = ROOT / "data/judged/judge_scores_glm_5.parquet"
v1 = pd.read_parquet(v1_path)
v1 = pd.concat([v1, pd.DataFrame(v1_rows)], ignore_index=True)
v1.to_parquet(v1_path, index=False)
print(f"[v1] saved {len(v1_rows)} new rows -> {len(v1)} total", flush=True)

v2_path = ROOT / "data/judged/judge_scores_v2min_glm5.parquet"
v2 = pd.read_parquet(v2_path)
v2 = pd.concat([v2, pd.DataFrame(v2_rows)], ignore_index=True)
v2.to_parquet(v2_path, index=False)
print(f"[v2min] saved {len(v2_rows)} new rows -> {len(v2)} total", flush=True)

print(f"\n[done] Rescored {len(audit_keys)} audit-corrected cells.")
print(f"  Tier 1: {len(tier1_rows)} rule-based scores")
print(f"  Tier 2: {len(v1_rows)} v1 + {len(v2_rows)} v2min judge scores")
