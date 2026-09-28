#!/usr/bin/env python3
"""Score the Qwen3 size sweep with the canonical headline recipe.

Reuses per_cell_scores_test88 + bootstrap_ci from
scripts/figures/build_test88_headline_table.py unchanged, by registering the
sweep systems in STRATEGY_DIRS and appending their judge verdicts to the
in-memory judge table. Failed extractions (invalid JSON) are scored as
misses, matching how the paper treats missing predictions, and reported
separately so the effect is visible.

Output: results/qwen3_size_sweep.csv  (+ printed summary)
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

spec = importlib.util.spec_from_file_location(
    "btb", ROOT / "scripts" / "figures" / "build_test88_headline_table.py")
btb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(btb)

SIZES = [("qwen3_4b_sweep", "Qwen3-4B", 4.0),
         ("qwen3_8b_sweep", "Qwen3-8B", 8.2),
         ("qwen3_14b_sweep", "Qwen3-14B", 14.8),
         ("qwen3_32b_sweep", "Qwen3-32B", 32.8)]

CORE = {"name", "description", "url", "license", "creator", "publisher",
        "datePublished", "inLanguage", "citeAs", "isLiveDataset"}


def valid_papers(sdir: Path) -> set:
    out = set()
    for f in sdir.glob("*.json"):
        if f.name == "_summary.json":
            continue
        if isinstance(json.load(open(f)).get("extraction"), dict):
            out.add(f.stem)
    return out


def main():
    sweep_judge = ROOT / "data/judged/judge_scores_sweep_qwen3_glm5.parquet"
    if sweep_judge.exists():
        extra = pd.read_parquet(sweep_judge)
        extra = extra[extra["score"].notna()]
        btb.judges = pd.concat([btb.judges, extra], ignore_index=True)
        print(f"loaded {len(extra)} sweep judge verdicts")

    # matched set: papers every size extracted successfully, so the size
    # comparison runs on identical inputs AND identical scored cells
    present = [(s, l, p) for s, l, p in SIZES
               if (ROOT / "data" / "extractions" / s).exists()]
    matched = None
    for sysid, _, _ in present:
        v = valid_papers(ROOT / "data" / "extractions" / sysid) & set(btb.test)
        matched = v if matched is None else (matched & v)
    print(f"matched test papers (valid extraction in all {len(present)} sizes): "
          f"{len(matched)}")

    rows = []
    for sysid, label, params in present:
        sdir = ROOT / "data" / "extractions" / sysid
        btb.STRATEGY_DIRS[sysid] = sdir

        files = [f for f in sdir.glob("*.json") if f.name != "_summary.json"]
        invalid = [f.stem for f in files
                   if not isinstance(json.load(open(f)).get("extraction"), dict)]
        test_invalid = [p for p in invalid if p in btb.test]

        # canonical scorer assumes a dict extraction; feed it only the valid
        # papers, then add zero-score rows for failed extractions (misses)
        import tempfile, shutil
        tmp = Path(tempfile.mkdtemp(prefix=f"{sysid}_valid_"))
        for f in files:
            if f.stem not in invalid:
                shutil.copy(f, tmp / f.name)
        btb.STRATEGY_DIRS[sysid] = tmp
        df = btb.per_cell_scores_test88(sysid)
        if len(test_invalid):
            miss = btb.GOLD_TEST[
                btb.GOLD_TEST.paper_id.isin(test_invalid)
                & ~btb.GOLD_TEST.gold_value.map(btb.is_null_gold)]
            df = pd.concat([df, pd.DataFrame({
                "paper_id": miss.paper_id.values,
                "field_id": miss.field_id.values,
                "score": 0.0})], ignore_index=True)
        shutil.rmtree(tmp, ignore_errors=True)
        if not len(df):
            print(f"SKIP {label}: no scored cells")
            continue
        df["tier"] = df["field_id"].map(
            lambda f: "core" if f.split(":")[-1] in CORE else "rai")

        def field_macro(sub):
            per_field = sub.groupby("field_id")["score"].mean()
            return float(per_field.mean()) if len(per_field) else float("nan")

        point, lo, hi = btb.bootstrap_ci(df)
        dfm = df[df.paper_id.isin(matched)]
        m_point, m_lo, m_hi = btb.bootstrap_ci(dfm)
        rows.append({
            "system": label, "params_b": params,
            "core": field_macro(df[df.tier == "core"]),
            "rai": field_macro(df[df.tier == "rai"]),
            "composite": point, "ci_lo": lo, "ci_hi": hi,
            "composite_matched": m_point, "matched_lo": m_lo, "matched_hi": m_hi,
            "core_matched": field_macro(dfm[dfm.tier == "core"]),
            "rai_matched": field_macro(dfm[dfm.tier == "rai"]),
            "papers_scored": df.paper_id.nunique(),
            "cells_scored": len(df),
            "failed_extractions_test88": len(test_invalid),
        })
        print(f"{label}: all-papers {point:.3f} [{lo:.3f}, {hi:.3f}] | "
              f"matched {m_point:.3f} [{m_lo:.3f}, {m_hi:.3f}] | "
              f"{len(test_invalid)} failed extractions in test-88")

    if not rows:
        return
    out = pd.DataFrame(rows)
    (ROOT / "results").mkdir(exist_ok=True)
    out.to_csv(ROOT / "results" / "qwen3_size_sweep.csv", index=False)
    print("\n" + out.round(3).to_string(index=False))
    if len(out) > 2:
        from scipy.stats import spearmanr
        r, p = spearmanr(out.params_b, out.composite)
        rm, pm = spearmanr(out.params_b, out.composite_matched)
        print(f"\nSpearman(params, composite): all-papers {r:.3f} (p={p:.3f}) | "
              f"matched {rm:.3f} (p={pm:.3f})")
    print(f"\nsaved {ROOT/'results'/'qwen3_size_sweep.csv'}")


if __name__ == "__main__":
    main()
