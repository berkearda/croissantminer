#!/usr/bin/env python3
"""Table-2-style results under the pilot (independently seeded) gold.

Restricted to the pilot papers that received the full three independent
raters. Reports Core / RAI / Composite with 2,000-replicate paper-clustered
bootstrap CIs, exactly as Table 2 does, under both gold sets on the same
cells so the two columns are directly comparable.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

spec = importlib.util.spec_from_file_location(
    "btb", ROOT / "scripts" / "figures" / "build_test88_headline_table.py")
btb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(btb)

from evaluation.field_metrics import score_field  # noqa: E402

PILOT = ROOT / "data" / "rebuttal_pilot"
SM = {1: 1.0, 2: 0.5, 3: 0.0}
CORE = {"name", "description", "url", "license", "creator", "publisher",
        "datePublished", "inLanguage", "citeAs", "isLiveDataset"}
# (system_id, display label, architecture) mirroring Table 2
SYSTEMS = [
    ("claude_sonnet_4_6", "Claude Sonnet 4.6", "Single-Pass"),
    ("claude_opus_4_7", "Claude Opus 4.7", "Single-Pass"),
    ("gpt5_4_full", "GPT-5.4", "Single-Pass"),
    ("qwen3_6_35b_a3b", "Qwen 3.6 35B-A3B", "Single-Pass"),
    ("glm_5_1", "GLM-5.1", "Single-Pass"),
    ("gemini_2_5_flash", "Gemini 2.5 Flash", "Single-Pass"),
    ("gpt5_4_mini", "GPT-5.4 Mini", "Single-Pass"),
    ("gemini_3_1_pro", "Gemini 3.1 Pro Preview", "Single-Pass"),
    ("deepseek_v3_2", "DeepSeek V3.2", "Single-Pass"),
    ("mistral_small_4", "Mistral Small 4", "Single-Pass"),
    ("llama4_scout", "Llama 4 Scout 17B", "Single-Pass"),
    ("claude_sonnet_4_5", "Claude Sonnet 4.5", "Single-Pass"),
    ("agentic_react_sonnet_4_6_v3", "ReAct (Sonnet 4.6)", "ReAct"),
    ("agentic_react_gpt_5_4_v3", "ReAct (GPT-5.4)", "ReAct"),
    ("agentic_react_gemini_3_1_pro_v3", "ReAct (Gemini 3.1 Pro)", "ReAct"),
    ("agentic_specialist_premium_v4", "Parallel Specialists (Sonnet 4.6)", "Parallel Specialists"),
    ("agentic_specialist_gpt5_4_full_v4", "Parallel Specialists (GPT-5.4)", "Parallel Specialists"),
    ("agentic_specialist_gemini_3_1_pro_v4", "Parallel Specialists (Gemini 3.1 Pro)", "Parallel Specialists"),
    ("agentic_v2_sonnet_4_6_v4", "Triage + Critique (Sonnet 4.6)", "Triage + Critique"),
    ("agentic_v2_gpt5_4_full_v4", "Triage + Critique (GPT-5.4)", "Triage + Critique"),
    ("agentic_v2_gemini_3_1_pro_v4", "Triage + Critique (Gemini 3.1 Pro)", "Triage + Critique"),
    ("agentic_lev_sonnet_4_6_sonnet_4_6_v3", "Locator-Extractor (Sonnet 4.6)", "Locator-Extractor"),
    ("agentic_lev_gpt5_4_full", "Locator-Extractor (GPT-5.4)", "Locator-Extractor"),
    ("agentic_lev_gemini_3_1_pro_gpt5_4_mini_v3", "Locator-Extractor (Gemini 3.1 Pro + GPT-5.4 Mini)", "Locator-Extractor"),
    ("agentic_lev_gemini_3_1_pro", "Locator-Extractor (Gemini 3.1 Pro)", "Locator-Extractor"),
]
SEEDS = {"claude_sonnet_4_5", "gpt5_4_full"}


def cells_for(sysid, gold_df, judge_df, allowed):
    sdir = btb.STRATEGY_DIRS.get(sysid)
    jl = {(r.paper_id, r.field_id): SM.get(int(r.score))
          for r in judge_df[judge_df.system_id == sysid].itertuples()
          if pd.notna(r.score)}
    rows = []
    for g in gold_df.itertuples():
        key = (g.paper_id, g.field_id)
        if key not in allowed:
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
            rows.append((g.paper_id, fid, 0.0))
        elif fid in btb.TIER1:
            r = score_field(cand, g.gold_value, fid)
            if not r["skipped"]:
                rows.append((g.paper_id, fid, r["score"]))
        else:
            if empty:
                rows.append((g.paper_id, fid, 0.0))
            else:
                s = jl.get((g.paper_id, fid))
                if s is not None:
                    rows.append((g.paper_id, fid, s))
    return pd.DataFrame(rows, columns=["paper_id", "field_id", "score"])


def macro(df, tier=None):
    if tier:
        df = df[df.field_id.map(lambda f: (f.split(":")[-1] in CORE) == (tier == "core"))]
    if not len(df):
        return float("nan")
    return float(df.groupby("field_id")["score"].mean().mean())


def main():
    ratings = pd.read_parquet(PILOT / "pilot_ratings.parquet")
    per_paper_raters = ratings[ratings.rating.notna()].groupby("paper_id")["slot"].nunique()
    three = set(per_paper_raters[per_paper_raters >= 3].index)
    print(f"papers with three independent raters: {len(three)}")

    pilot = pd.read_parquet(PILOT / "pilot_gold.parquet")
    pilot = pilot[pilot.gold_value.notna() & pilot.paper_id.isin(three)]
    cur = pd.read_parquet(ROOT / "data/annotations/gold.parquet")
    cur = cur[cur.gold_method.isin(btb.DEFAULT_GOLD_METHODS) & cur.gold_value.notna()]
    allowed = set(map(tuple, pilot[["paper_id", "field_id"]].values)) & \
              set(map(tuple, cur[["paper_id", "field_id"]].values))
    print(f"cells scored: {len(allowed)}")

    jp = pd.read_parquet(ROOT / "data/judged/judge_scores_pilot_glm5.parquet")
    rows = []
    for sysid, label, arch in SYSTEMS:
        if sysid not in btb.STRATEGY_DIRS:
            print("MISSING", sysid); continue
        dp = cells_for(sysid, pilot, jp, allowed)
        dc = cells_for(sysid, cur, btb.judges, allowed)
        if not len(dp):
            continue
        p, lo, hi = btb.bootstrap_ci(dp)
        c, _, _ = btb.bootstrap_ci(dc)
        rows.append({"system": label, "architecture": arch,
                     "core": macro(dp, "core"), "rai": macro(dp, "rai"),
                     "composite": p, "lo": lo, "hi": hi,
                     "composite_current_gold": c, "seed_model": sysid in SEEDS})
    out = pd.DataFrame(rows)
    ordered = []
    for arch in ["Single-Pass", "ReAct", "Parallel Specialists",
                 "Triage + Critique", "Locator-Extractor"]:
        blk = out[out.architecture == arch].sort_values("composite", ascending=False)
        blk = blk.copy()
        blk.insert(0, "rank", range(1, len(blk) + 1))
        ordered.append(blk)
    out = pd.concat(ordered, ignore_index=True)
    print("\n=== Table-2 style, scored against the PILOT gold ===")
    cur_arch = None
    for r in out.itertuples():
        if r.architecture != cur_arch:
            print(f"  -- {r.architecture} --"); cur_arch = r.architecture
        star = " *" if r.seed_model else ""
        print(f"{r.rank:>2}  {r.system:50s} {r.core:.3f}  {r.rai:.3f}  "
              f"{r.composite:.3f} [{r.lo:.3f}, {r.hi:.3f}]"
              f"   (10-paper score vs current gold {r.composite_current_gold:.3f}){star}")
    print("\n* seeded one of the two gold sets; inflated against the gold it seeded")
    out.to_csv(ROOT / "results" / "pilot_table2_style.csv", index=False)
    print(f"\nsaved {ROOT/'results'/'pilot_table2_style.csv'}")


if __name__ == "__main__":
    main()
