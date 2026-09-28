#!/usr/bin/env python3
"""Ranking stability of the re-annotation pilot (NeurIPS rebuttal, T-088).

Scores the single-pass systems twice on the SAME pilot papers and cells:
  (a) against the current gold  (Sonnet-4.5-seeded, human-verified)
  (b) against the pilot gold    (GPT-5.4-seeded, independently re-annotated)
and reports the Spearman correlation between the two rankings.

Uses the canonical per-cell rules: Tier 1 rule-based for core fields, GLM-5
v2-min verdicts for the RAI fields, gold-null + empty candidate skipped,
gold-null + non-empty candidate = 0, gold-real + empty candidate = 0.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

spec = importlib.util.spec_from_file_location(
    "btb", ROOT / "scripts" / "figures" / "build_test88_headline_table.py")
btb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(btb)

from evaluation.field_metrics import score_field  # noqa: E402

PILOT = ROOT / "data" / "rebuttal_pilot"
SM = {1: 1.0, 2: 0.5, 3: 0.0}
SINGLE = ["claude_sonnet_4_6", "claude_opus_4_7", "gpt5_4_full", "gpt5_4_mini",
          "gemini_3_1_pro", "gemini_2_5_flash", "deepseek_v3_2",
          "mistral_small_4", "llama4_scout", "qwen3_6_35b_a3b", "glm_5_1",
          "claude_sonnet_4_5"]


def score(sysid, gold_df, judge_df, papers, fields):
    sdir = btb.STRATEGY_DIRS.get(sysid)
    jl = {(r.paper_id, r.field_id): SM.get(int(r.score))
          for r in judge_df[judge_df.system_id == sysid].itertuples()
          if pd.notna(r.score)}
    cells = []
    for g in gold_df.itertuples():
        if g.paper_id not in papers or (g.paper_id, g.field_id) not in fields:
            continue
        path = sdir / f"{g.paper_id}.json"
        if not path.exists():
            continue
        payload = json.load(open(path))
        ext = payload.get("extraction", payload)
        if not isinstance(ext, dict):
            ext = {}
        fid = g.field_id
        cand = ext.get(fid, ext.get(fid.split(":")[-1]))
        empty = cand is None or not str(cand).strip()
        if btb.is_null_gold(g.gold_value):
            if empty:
                continue
            cells.append((fid, 0.0))
        elif fid in btb.TIER1:
            r = score_field(cand, g.gold_value, fid)
            if not r["skipped"]:
                cells.append((fid, r["score"]))
        else:
            if empty:
                cells.append((fid, 0.0))
            else:
                s = jl.get((g.paper_id, fid))
                if s is not None:
                    cells.append((fid, s))
    if not cells:
        return float("nan"), 0
    df = pd.DataFrame(cells, columns=["field_id", "score"])
    return float(df.groupby("field_id")["score"].mean().mean()), len(df)


def main():
    pilot = pd.read_parquet(PILOT / "pilot_gold.parquet")
    pilot = pilot[pilot.gold_value.notna()]
    cur = pd.read_parquet(ROOT / "data/annotations/gold.parquet")
    cur = cur[cur.gold_method.isin(btb.DEFAULT_GOLD_METHODS) & cur.gold_value.notna()]

    # restrict both to exactly the same (paper, field) cells
    common = set(map(tuple, pilot[["paper_id", "field_id"]].values)) & \
             set(map(tuple, cur[["paper_id", "field_id"]].values))
    papers = {p for p, _ in common}
    print(f"pilot papers: {len(papers)} | common cells: {len(common)}")

    jp = pd.read_parquet(ROOT / "data/judged/judge_scores_pilot_glm5.parquet")
    jc = btb.judges

    rows = []
    for s in SINGLE:
        if s not in btb.STRATEGY_DIRS:
            continue
        a, na = score(s, cur, jc, papers, common)
        b, nb = score(s, pilot, jp, papers, common)
        rows.append({"system": s, "vs_current_gold": a, "vs_pilot_gold": b,
                     "n_cells_current": na, "n_cells_pilot": nb})
    out = pd.DataFrame(rows).sort_values("vs_current_gold", ascending=False)
    print("\n" + out.round(3).to_string(index=False))

    ranked = out[out.system != "claude_sonnet_4_5"].dropna()
    r, p = spearmanr(ranked.vs_current_gold, ranked.vs_pilot_gold)
    print(f"\nSpearman(ranking vs current gold, ranking vs pilot gold) = "
          f"{r:.3f} (p = {p:.5f}, {len(ranked)} ranked systems)")
    top_cur = ranked.sort_values("vs_current_gold", ascending=False).system.tolist()
    top_pil = ranked.sort_values("vs_pilot_gold", ascending=False).system.tolist()
    print(f"top-3 vs current gold: {top_cur[:3]}")
    print(f"top-3 vs pilot gold:   {top_pil[:3]}")
    (ROOT / "results").mkdir(exist_ok=True)
    out.to_csv(ROOT / "results" / "pilot_ranking_stability.csv", index=False)
    print(f"\nsaved {ROOT/'results'/'pilot_ranking_stability.csv'}")


if __name__ == "__main__":
    main()
