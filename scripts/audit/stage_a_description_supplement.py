#!/usr/bin/env python3
"""Stage A supplement: validate GLM-5 (and re-rank candidates) on sc:description.

Yesterday's 60-cell audit was sampled from the 20 RAI prose fields. Adding
sc:description to Tier 2 brings the audit set to 21 fields. To confirm
GLM-5 still wins, sample 10 sc:description cells and run all 7 candidates.

Output:
  - data/audit/_supplement_description_judge_<slug>.parquet (per candidate)
  - prints inter-judge agreement table + re-ranking
"""

from __future__ import annotations
import json
import random
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

import sys
sys.path.insert(0, str(ROOT))
from evaluation.run_judge_ensemble import (  # noqa: E402
    JUDGES, JUDGE_SYSTEM, JUDGE_USER_TEMPLATE, call_judge, parse_judge_response,
)

GOLD = ROOT / "data" / "annotations" / "gold.parquet"
EXT_BASE = ROOT / "data" / "extractions"
OUT_DIR = ROOT / "data" / "audit"

CANDIDATES = ["gpt-5.5", "gemini-2.5-pro", "gemini-3.1-pro",
              "llama-3.3-70b", "llama-4-maverick",
              "deepseek-v3-2", "glm-5", "qwen-3-max"]
SINGLE_PASS = [
    "claude_sonnet_4_5", "claude_sonnet_4_6", "claude_opus_4_7",
    "gpt5.4_full", "gpt5.4_mini",
    "gemini_3.1_pro", "gemini_2.5_flash",
    "deepseek_v3_2", "glm_5_1",
    "llama4_scout", "mistral_small_4", "qwen3_6_35b_a3b",
]

N_SAMPLES = 10
SEED = 7


def is_null(v):
    if v is None: return True
    if isinstance(v, float) and pd.isna(v): return True
    if not isinstance(v, str): return False
    s = v.strip().lower()
    return s in {"", "not specified", "unknown"} or s.startswith("[null")


def main():
    random.seed(SEED)
    gold = pd.read_parquet(GOLD)
    desc = gold[(gold.field_id == "sc:description") &
               ~gold.gold_value.apply(is_null)].copy()
    print(f"sc:description gold rows (non-null): {len(desc)}")

    # Build candidate pool: (paper_id, system_id) pairs with non-null extraction
    candidates = []
    for _, r in desc.iterrows():
        paper = r.paper_id
        for sys_name in SINGLE_PASS:
            ext_path = EXT_BASE / sys_name / f"{paper}.json"
            if not ext_path.exists():
                continue
            try:
                payload = json.load(open(ext_path))
            except Exception:
                continue
            ext = payload.get("extraction", payload)
            cand = ext.get("sc:description", ext.get("description"))
            if cand is None or is_null(cand):
                continue
            candidates.append({
                "paper_id": paper, "field_id": "sc:description",
                "system_id": sys_name,
                "gold_value": str(r.gold_value),
                "candidate_value": str(cand),
            })
    print(f"available (paper, system) cells: {len(candidates)}")

    sampled = random.sample(candidates, min(N_SAMPLES, len(candidates)))
    sample_df = pd.DataFrame(sampled)
    print(f"sampled {len(sample_df)} cells")

    # Run each judge
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results = {}
    for cand_name in CANDIDATES:
        if cand_name not in JUDGES:
            print(f"  [skip] {cand_name} not in JUDGES registry")
            continue
        cfg = JUDGES[cand_name]
        print(f"\n--- {cand_name} ({cfg.model_id}) ---")
        rows = []
        t0 = time.time()
        for i, s in enumerate(sampled):
            user = JUDGE_USER_TEMPLATE.format(
                field_id=s["field_id"],
                gold_value=s["gold_value"][:8000],
                candidate_value=s["candidate_value"][:8000],
            )
            try:
                raw, _ = call_judge(cfg, JUDGE_SYSTEM, user)
                score, reason = parse_judge_response(raw)
            except Exception as e:
                print(f"  cell {i}: failed: {str(e)[:80]}")
                score, reason = None, f"ERROR: {e}"
            rows.append({**s, "judge_score": score, "judge_reason": reason})
        df = pd.DataFrame(rows)
        out_path = OUT_DIR / f"_supplement_description_judge_{cfg.slug}.parquet"
        df.to_parquet(out_path, index=False)
        results[cand_name] = df
        n_valid = df["judge_score"].notna().sum()
        print(f"  {n_valid}/{len(df)} valid, {time.time()-t0:.0f}s -> {out_path.name}")

    # Combine into a wide table for cross-judge comparison
    print("\n=== sc:description supplement: per-cell judge scores ===")
    wide = sample_df[["paper_id", "system_id"]].copy()
    for cand_name, df in results.items():
        wide[cand_name] = df["judge_score"].values
    print(wide.to_string(index=False))

    # Per-candidate score distribution
    print("\n=== per-candidate score distribution ===")
    for cand_name, df in results.items():
        valid = df["judge_score"].dropna()
        if len(valid) == 0:
            print(f"  {cand_name}: 0 valid"); continue
        dist = valid.value_counts().sort_index().to_dict()
        print(f"  {cand_name}: n={len(valid)}, dist={dist}, mean={valid.mean():.2f}")

    # Compute pairwise inter-candidate agreement (Spearman over all 10 cells)
    from scipy.stats import spearmanr
    print("\n=== pairwise spearman (judge vs judge) ===")
    cands = list(results.keys())
    print(f"{'judge':25s}", end="")
    for c in cands:
        print(f" {c[:12]:>12s}", end="")
    print()
    for c1 in cands:
        v1 = results[c1]["judge_score"].astype(float)
        print(f"{c1:25s}", end="")
        for c2 in cands:
            v2 = results[c2]["judge_score"].astype(float)
            mask = v1.notna() & v2.notna()
            if mask.sum() < 3:
                print(f" {'n/a':>12s}", end="")
                continue
            sp = spearmanr(v1[mask], v2[mask]).statistic
            if pd.isna(sp):
                print(f" {'-':>12s}", end="")
            else:
                print(f" {sp:>12.3f}", end="")
        print()

    # Median across all judges as proxy ground truth, then per-judge agreement with median
    print("\n=== per-judge agreement with inter-judge median ===")
    all_scores = pd.DataFrame({c: results[c]["judge_score"].astype(float)
                                for c in cands})
    median = all_scores.median(axis=1)
    print(f"{'judge':25s} {'spearman':>10s} {'abs_diff':>10s} {'exact':>8s}")
    for c in cands:
        v = all_scores[c]
        mask = v.notna() & median.notna()
        sp = spearmanr(v[mask], median[mask]).statistic if mask.sum() >= 3 else float("nan")
        diff = (v[mask] - median[mask]).abs().mean()
        exact = (v[mask] == median[mask]).sum()
        print(f"{c:25s} {sp:>10.3f} {diff:>10.2f} {exact:>4d}/{mask.sum():d}")


if __name__ == "__main__":
    main()
