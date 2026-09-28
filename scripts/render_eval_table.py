#!/usr/bin/env python3
"""Render the current evaluation composite table to PNG for sharing.

Output: docs/eval_table_2026-05-02.png
"""

import json, sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def build_table_df():
    from evaluation.field_metrics import (CONSTRAINED_FIELDS, SHORT_TEXT_FIELDS, score_field)
    from evaluation.score_against_gold import STRATEGY_DIRS, DEFAULT_GOLD_METHODS

    # Tier 1 from cached file + recompute for any new bake-off systems
    t1 = pd.read_parquet(ROOT / "data/judged/tier1_scores.parquet")
    t1 = t1[["system_id", "paper_id", "field_id", "score"]].copy()
    t1["tier"] = "T1"

    GOLD = pd.read_parquet(ROOT / "data/annotations/gold.parquet")
    GOLD = GOLD[GOLD["gold_method"].isin(DEFAULT_GOLD_METHODS)]
    TIER1 = CONSTRAINED_FIELDS + SHORT_TEXT_FIELDS

    all_systems_with_extractions = [
        s for s, d in STRATEGY_DIRS.items() if d.exists() and any(d.glob("*.json"))
    ]
    cached_systems = set(t1["system_id"].unique())
    missing_t1 = [s for s in all_systems_with_extractions if s not in cached_systems]

    extras = []
    for sys_id in missing_t1:
        sdir = STRATEGY_DIRS[sys_id]
        for _, g in GOLD[GOLD["field_id"].isin(TIER1)].iterrows():
            ext_path = sdir / f"{g['paper_id']}.json"
            if not ext_path.exists():
                continue
            payload = json.load(open(ext_path))
            ext = payload.get("extraction", payload)
            fid = g["field_id"]
            short = fid.split(":")[-1] if ":" in fid else fid
            cand = ext.get(fid, ext.get(short))
            r = score_field(cand, g["gold_value"], fid)
            if r["skipped"]:
                continue
            extras.append({"system_id": sys_id, "paper_id": g["paper_id"],
                           "field_id": fid, "score": r["score"], "tier": "T1"})
    if extras:
        t1 = pd.concat([t1, pd.DataFrame(extras)], ignore_index=True)

    # Tier 2 from judge parquet
    t2 = pd.read_parquet(ROOT / "data/judged/judge_scores_glm_5.parquet")
    t2 = t2[t2["score"].notna()].copy()
    SCORE_MAP = {1: 1.0, 2: 0.5, 3: 0.0}
    t2["score_lin"] = t2["score"].map(SCORE_MAP)
    t2 = t2[["system_id", "paper_id", "field_id", "score_lin"]].rename(columns={"score_lin": "score"})
    t2["tier"] = "T2"

    both = pd.concat([t1, t2], ignore_index=True)

    # Composite: equal weight per field
    per_field = both.groupby(["system_id", "field_id"])["score"].mean().reset_index()
    composite = per_field.groupby("system_id").agg(
        n_fields=("field_id", "nunique"),
        composite=("score", "mean"),
    ).reset_index()
    tier_means = both.groupby(["system_id", "tier"])["score"].mean().unstack("tier")
    tier_means.columns = [f"mean_{c}" for c in tier_means.columns]
    agg = composite.merge(tier_means, on="system_id", how="left").round(3)
    agg = agg.sort_values("composite", ascending=False).reset_index(drop=True)
    return agg


def render_png(df, out_path):
    BAKEOFF = {
        "agentic_lev_gemini_3_1_pro_sonnet_4_6",
        "agentic_lev_gemini_3_1_pro_gpt5_4_mini",
        "agentic_lev_gemini_3_1_pro_gpt5_4_full",
    }
    BAKEOFF_WINNER = "agentic_lev_gemini_3_1_pro_gpt5_4_mini"
    GOLD_SEED = "claude_sonnet_4_5"

    rows = []
    for i, r in df.iterrows():
        rank = i + 1
        sys_id = r["system_id"]
        kind = "agentic / dev 14" if sys_id.startswith("agentic_") else "single-pass / 102"
        n = int(r["n_fields"])
        n_str = f"{n}/30" if n != 30 else "30"
        # add markers
        display_id = sys_id
        if sys_id == GOLD_SEED:
            display_id = sys_id + "  ⚠"
        elif sys_id == BAKEOFF_WINNER:
            display_id = sys_id + "  ★"
        elif sys_id in BAKEOFF:
            display_id = sys_id + "  ★"
        elif n < 30:
            display_id = sys_id + "  †"
        rows.append([rank, display_id,
                     f"{r['composite']:.3f}",
                     f"{r['mean_T1']:.3f}",
                     f"{r['mean_T2']:.3f}",
                     n_str, kind])

    cols = ["#", "System", "Composite", "Tier 1", "Tier 2", "n fields", "Split"]

    n_rows = len(rows)
    fig_h = 0.36 * (n_rows + 7)
    fig_w = 13.5
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=160)
    ax.axis("off")

    title = "CroissantMiner — Current Evaluation (composite, equal-weight 1/30 per field)"
    subtitle = ("Tier 1: rule-based on 10 short/constrained fields  |  "
                "Tier 2: GLM-5 LLM-judge on 20 prose RAI fields  |  "
                "Single-pass = 102 papers, agentic = dev 14 only (round-0 except where noted)")

    fig.text(0.5, 0.965, title, ha="center", va="bottom",
             fontsize=14, fontweight="bold")
    fig.text(0.5, 0.945, subtitle, ha="center", va="bottom",
             fontsize=9, color="#555")

    table = ax.table(
        cellText=rows, colLabels=cols, loc="center",
        cellLoc="left",
        colWidths=[0.05, 0.42, 0.09, 0.08, 0.08, 0.09, 0.19],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 1.45)

    # Header styling
    for j in range(len(cols)):
        c = table[(0, j)]
        c.set_facecolor("#1F2A44")
        c.set_text_props(color="white", fontweight="bold")
        c.set_height(0.06)

    # Per-row coloring
    for i, r in df.iterrows():
        sys_id = r["system_id"]
        ridx = i + 1  # 0 is header
        if sys_id == GOLD_SEED:
            color = "#FFE8B0"  # gold tint
        elif sys_id == BAKEOFF_WINNER:
            color = "#D4F1D4"  # green tint
        elif sys_id in BAKEOFF:
            color = "#E6F4E6"  # lighter green
        elif sys_id.startswith("agentic_"):
            color = "#F0F4FA"  # blue-grey for agentic
        else:
            color = "#FFFFFF" if i % 2 == 0 else "#F8F8F8"
        for j in range(len(cols)):
            table[(ridx, j)].set_facecolor(color)
        # Composite cell — bold for top 5
        if i < 5:
            table[(ridx, 2)].set_text_props(fontweight="bold")

    # Footnotes
    footnotes = [
        "⚠  Sonnet 4.5 is the gold-reference seed (its single-pass outputs were validated by 22 annotators to build gold). 0.897 reflects circular within-family",
        "    similarity, not a fair ranking — slated for §5.1 footnote-only, not headline comparison.",
        "★  Bake-off variants from 2026-05-01 Phase 0.5: new mixed-backbone LEV with runtime LLM locator (replaces precomputed Phase-1 Gemini-Flash triage).",
        "    C2 (Gemini-3.1-Pro locator + GPT-5.4-mini extractor) wins by 'cheapest within 0.03 of best' rule; ~$0.008/paper, ~38× cheaper than C3.",
        "†  LEV-Gemini-3.1-Pro covers only 22/30 fields (8 RAI fields had zero non-null gold ∩ non-null extraction overlap). Composite not directly comparable.",
        "Missing rows (extraction or scoring pending): agentic_react_*, agentic_specialist_*, agentic_v2/lev_llama4_scout, bake-off C1 (Llama-locator).",
    ]
    fig.text(0.06, 0.02, "\n".join(footnotes),
             fontsize=8, color="#333", va="bottom", family="monospace")

    plt.subplots_adjust(top=0.92, bottom=0.20, left=0.04, right=0.98)
    fig.savefig(out_path, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main():
    out = ROOT / "docs" / "eval_table_2026-05-02.png"
    df = build_table_df()
    render_png(df, out)
    print(f"wrote {out.relative_to(ROOT)}")
    print(f"size: {out.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
