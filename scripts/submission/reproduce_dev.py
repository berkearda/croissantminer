#!/usr/bin/env python3
"""Reproducibility runner — score all systems on the 14-paper dev split.

Designed for a NeurIPS reviewer to run from a clean checkout and verify
the headline metric reproduces. The dev split is intentionally small
(14 papers × 30 fields = 420 cells) so the run finishes in <30 min and
costs <$5 in commercial-API tokens for the cells that need them; the
already-cached LLM-judge calls and pre-computed extractions make the
common case effectively free.

Outputs:
    /tmp/croissantminer_repro/per_system_dev.csv
    /tmp/croissantminer_repro/composite_dev.csv

Run:
    python scripts/submission/reproduce_dev.py
    python scripts/submission/reproduce_dev.py --systems claude_sonnet_4_6 claude_opus_4_7
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from evaluation.field_metrics import (  # noqa: E402
    CONSTRAINED_FIELDS,
    LONG_TEXT_RAI_FIELDS,
    SHORT_TEXT_FIELDS,
    score_field,
)
from evaluation.score_against_gold import STRATEGY_DIRS  # noqa: E402

OUT_DIR = Path("/tmp/croissantminer_repro")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Same lineup as the headline ranking (Sonnet 4.5 + iteration variants excluded)
HEADLINE_SYSTEMS = [
    "claude_sonnet_4_6",
    "claude_opus_4_7",
    "gpt5_4_full",
    "agentic_react_sonnet_4_6_v3",
    "agentic_specialist_premium_v4",
    "qwen3_6_35b_a3b",
    "glm_5_1",
    "agentic_v2_sonnet_4_6_v4",
    "gemini_2_5_flash",
    "gpt5_4_mini",
    "gemini_3_1_pro",
    "deepseek_v3_2",
    "agentic_lev_sonnet_4_6_sonnet_4_6_v3",
    "mistral_small_4",
    "llama4_scout",
]

TIER1 = set(CONSTRAINED_FIELDS) | set(SHORT_TEXT_FIELDS)
TIER2 = set(LONG_TEXT_RAI_FIELDS)
SCORE_MAP = {1: 1.0, 2: 0.5, 3: 0.0}


def is_null_gold(val) -> bool:
    if val is None:
        return True
    s = str(val).strip()
    return s == "" or s.upper().startswith("[NULL")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--systems", nargs="+", default=HEADLINE_SYSTEMS,
                    help="System ids to score (default: full headline lineup)")
    args = ap.parse_args()

    print("Loading data and judge cache …")
    split = json.loads((ROOT / "data/agentic/dev_test_split.json").read_text())
    DEV_PAPERS = frozenset(split["dev"])
    print(f"  Dev split: {len(DEV_PAPERS)} papers")

    gold = pd.read_parquet(ROOT / "data/annotations/gold.parquet")
    gold = gold[gold["paper_id"].isin(DEV_PAPERS)]
    print(f"  Gold cells (dev): {len(gold)}")

    # Load the judge scores from the released parquet (no fresh API calls
    # — the released file already has all dev cells scored)
    judge = pd.read_parquet(ROOT / "data/judged/judge_scores_v2min_glm5.parquet")
    judge = judge[judge["paper_id"].isin(DEV_PAPERS)]
    judge["mapped"] = judge["score"].map(SCORE_MAP)
    judge_lookup = {
        (r.system_id, r.paper_id, r.field_id): r.mapped
        for r in judge.itertuples()
    }

    rows = []
    for sid in args.systems:
        sdir = STRATEGY_DIRS.get(sid)
        if sdir is None or not sdir.exists():
            print(f"  [skip] {sid}: no extraction dir at {sdir}")
            continue
        n_cells = 0
        sum_score = 0.0
        per_field = {}
        for _, g in gold.iterrows():
            ext_path = sdir / f"{g['paper_id']}.json"
            if not ext_path.exists():
                continue
            try:
                payload = json.load(open(ext_path))
                ext = payload.get("extraction", payload) if isinstance(payload, dict) else {}
            except Exception:
                continue
            fid = g["field_id"]
            short = fid.split(":")[-1] if ":" in fid else fid
            cand = ext.get(fid, ext.get(short))
            cand_empty = cand is None or not str(cand).strip()
            gold_null = is_null_gold(g["gold_value"])
            if gold_null and cand_empty:
                continue
            if gold_null:
                score = 0.0
            elif fid in TIER1:
                r = score_field(cand, g["gold_value"], fid)
                if r["skipped"]:
                    continue
                score = r["score"]
            elif fid in TIER2:
                if cand_empty:
                    score = 0.0
                else:
                    score = judge_lookup.get((sid, g["paper_id"], fid))
                    if score is None:
                        continue
            else:
                continue
            n_cells += 1
            sum_score += score
            per_field.setdefault(fid, []).append(score)

        if n_cells == 0:
            continue
        # Composite: per-field mean, then mean over fields
        per_field_means = {f: sum(s) / len(s) for f, s in per_field.items()}
        composite = sum(per_field_means.values()) / len(per_field_means)
        rows.append({"system": sid, "n_cells": n_cells, "composite_dev": round(composite, 4)})
        print(f"  {sid:46s}  composite={composite:.3f}  cells={n_cells}")

    if rows:
        df = pd.DataFrame(rows).sort_values("composite_dev", ascending=False)
        df.to_csv(OUT_DIR / "composite_dev.csv", index=False)
        print(f"\nWrote {OUT_DIR / 'composite_dev.csv'}")
        print(df.to_string(index=False))
    else:
        print("No systems scored. Check that data/extractions/<system>/ files exist.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
