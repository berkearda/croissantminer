#!/usr/bin/env python3
"""Empirical Tier 1 vs Tier 2 audit: directly compare rule-based scoring
to GLM-5 LLM judge scoring on the same cells, per field.

For each field, sample 10 (paper, system) cells where gold and candidate
both exist, score both ways, and compute correlation. High correlation
(>= 0.7) means rule-based captures the same signal as LLM judge -> Tier 1
is sufficient. Low correlation (< 0.5) means rule-based misses semantic
equivalence -> Tier 2 needed.

Output: docs/field_tier_empirical_audit.md
"""

from __future__ import annotations
import json
import os
import random
import re
import time
from pathlib import Path

import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent.parent
GOLD = ROOT / "data" / "annotations" / "gold.parquet"
EXT_BASE = ROOT / "data" / "extractions"
OUT_MD = ROOT / "docs" / "field_tier_empirical_audit.md"
OUT_PARQUET = ROOT / "data" / "audit" / "_field_tier_empirical.parquet"

# Try to load .env
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

SINGLE_PASS = [
    "claude_sonnet_4_5", "claude_sonnet_4_6", "claude_opus_4_7",
    "gpt5.4_full", "gpt5.4_mini",
    "gemini_3.1_pro", "gemini_2.5_flash",
    "deepseek_v3_2", "glm_5_1",
    "llama4_scout", "mistral_small_4", "qwen3_6_35b_a3b",
]

N_PER_FIELD = 30  # cells per field (bumped from 10 for tighter Spearman CI)
SEED = 42


def is_null(v):
    if v is None: return True
    if isinstance(v, float) and pd.isna(v): return True
    if not isinstance(v, str): return False
    s = v.strip().lower()
    return s in {"", "not specified", "unknown"} or s.startswith("[null")


def normalize(s):
    if s is None: return None
    s = str(s).strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s if s else None


def token_set(s):
    if s is None: return set()
    return set(re.findall(r"\b\w+\b", s.lower()))


def token_f1(g, c):
    gs, cs = token_set(g), token_set(c)
    if not gs and not cs: return 1.0
    if not gs or not cs: return 0.0
    inter = len(gs & cs)
    if inter == 0: return 0.0
    p = inter / len(cs); r = inter / len(gs)
    return 2 * p * r / (p + r)


def jaccard(g, c):
    gs, cs = token_set(g), token_set(c)
    if not gs and not cs: return 1.0
    if not (gs | cs): return 0.0
    return len(gs & cs) / len(gs | cs)


def exact_match(g, c):
    return 1.0 if normalize(g) == normalize(c) else 0.0


def rule_score(field_id, g, c):
    """Best Tier 1 score per field."""
    # Constrained / exact-match-with-normalization fields
    if field_id in {"sc:license", "sc:datePublished", "sc:inLanguage",
                   "cr:isLiveDataset", "sc:url"}:
        return exact_match(g, c)
    # Token-F1 fields
    if field_id in {"sc:name", "sc:creator", "sc:publisher", "cr:citeAs",
                   "sc:description", "rai:dataAnnotationPlatform"}:
        return token_f1(g, c)
    # Jaccard fields
    if field_id in {"rai:dataCollectionType"}:
        return jaccard(g, c)
    # All other RAI fields: try token-F1 anyway as the rule-based candidate
    return token_f1(g, c)


def map_judge(score):
    """Map judge 1/2/3 to 1.0/0.5/0.0 (1=correct, 3=wrong in our gold convention)."""
    if score == 1: return 1.0
    if score == 2: return 0.5
    if score == 3: return 0.0
    return None


def main():
    random.seed(SEED)
    gold = pd.read_parquet(GOLD)
    gold = gold[~gold["gold_value"].apply(is_null)].copy()

    # Load all single-pass extractions
    extractions = {}
    for sys in SINGLE_PASS:
        d = EXT_BASE / sys
        if not d.exists(): continue
        extractions[sys] = {}
        for f in d.glob("*.json"):
            if f.name.startswith("_") or f.stem.startswith("_"): continue
            try:
                payload = json.load(open(f))
            except Exception:
                continue
            ext = payload.get("extraction", payload)
            extractions[sys][f.stem] = ext

    # Build sample list per field
    field_order = sorted(gold["field_id"].unique())
    samples = []
    for fid in field_order:
        sub = gold[gold["field_id"] == fid].copy()
        candidates = []
        short = fid.split(":")[-1] if ":" in fid else fid
        for _, gold_row in sub.iterrows():
            paper = gold_row["paper_id"]
            for sysname, papers in extractions.items():
                if paper not in papers: continue
                ext = papers[paper]
                cand = ext.get(fid, ext.get(short))
                if cand is None or is_null(cand): continue
                candidates.append({
                    "field_id": fid,
                    "paper_id": paper,
                    "system_id": sysname,
                    "gold_value": str(gold_row["gold_value"]),
                    "candidate_value": str(cand),
                })
        if not candidates:
            print(f"  {fid}: no candidates with non-null extraction; skipping")
            continue
        # Sample N per field (or all if fewer)
        n = min(N_PER_FIELD, len(candidates))
        sub_samples = random.sample(candidates, n)
        samples.extend(sub_samples)
        print(f"  {fid}: {len(candidates)} available, sampled {n}")

    print(f"\nTotal cells to score: {len(samples)}")

    # Score each cell with rule + LLM judge
    cfg = JUDGES["glm-5"]
    results = []
    t0 = time.time()
    for i, s in enumerate(samples):
        rule = rule_score(s["field_id"], s["gold_value"], s["candidate_value"])
        user = JUDGE_USER_TEMPLATE.format(
            field_id=s["field_id"],
            gold_value=s["gold_value"][:8000],
            candidate_value=s["candidate_value"][:8000],
        )
        try:
            raw, _ = call_judge(cfg, JUDGE_SYSTEM, user)
            score, _ = parse_judge_response(raw)
            judge_norm = map_judge(score) if score else None
        except Exception as e:
            print(f"  cell {i}: judge failed: {str(e)[:80]}")
            judge_norm = None
        results.append({**s, "rule_score": rule, "judge_score": judge_norm})
        if (i + 1) % 30 == 0:
            elapsed = time.time() - t0
            print(f"  scored {i+1}/{len(samples)} ({elapsed:.0f}s)")

    df = pd.DataFrame(results)
    df.to_parquet(OUT_PARQUET, index=False)
    valid = df.dropna(subset=["judge_score"])
    print(f"\nValid: {len(valid)}/{len(df)} cells")

    # Per-field correlation
    rows = []
    for fid in field_order:
        sub = valid[valid["field_id"] == fid]
        if len(sub) < 3:
            rows.append({"field": fid, "n": len(sub),
                        "rule_mean": None, "judge_mean": None,
                        "spearman": None, "pearson": None,
                        "diff_mean": None, "verdict": "insufficient data"})
            continue
        sp = stats.spearmanr(sub["rule_score"], sub["judge_score"]).statistic
        pe = stats.pearsonr(sub["rule_score"], sub["judge_score"]).statistic
        diff = (sub["rule_score"] - sub["judge_score"]).abs().mean()

        # Decision
        if sp >= 0.7 and diff < 0.25:
            verdict = "Tier 1 (rule == judge)"
        elif sp >= 0.5:
            verdict = "Borderline"
        else:
            verdict = "Tier 2 (rule misses signal)"
        rows.append({"field": fid, "n": len(sub),
                    "rule_mean": round(sub["rule_score"].mean(), 2),
                    "judge_mean": round(sub["judge_score"].mean(), 2),
                    "spearman": round(sp, 2) if not pd.isna(sp) else None,
                    "pearson": round(pe, 2) if not pd.isna(pe) else None,
                    "diff_mean": round(diff, 2),
                    "verdict": verdict})

    summary = pd.DataFrame(rows)
    print()
    print(summary.to_string(index=False))

    # Markdown
    lines = ["# Empirical field-tier audit (rule-based vs GLM-5 judge correlation)",
             "",
             f"Sampled {len(valid)} cells across {len(field_order)} fields, scored with both rule-based and GLM-5 judge.",
             "",
             "Decision rule:",
             "- **Tier 1** if Spearman >= 0.7 AND mean abs diff < 0.25",
             "- **Tier 2** if Spearman < 0.5",
             "- **Borderline** otherwise",
             "",
             "## Per-field summary",
             "",
             "| Field | n | rule_mean | judge_mean | spearman | pearson | abs_diff | Verdict |",
             "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| `{r['field']}` | {r['n']} | {r['rule_mean']} | "
                    f"{r['judge_mean']} | {r['spearman']} | {r['pearson']} | "
                    f"{r['diff_mean']} | **{r['verdict']}** |")
    lines.extend(["", "## Per-field disagreement examples", ""])
    for fid in field_order:
        sub = valid[valid["field_id"] == fid]
        if len(sub) < 3: continue
        # Show 2 cells with biggest disagreement
        sub = sub.copy()
        sub["abs_diff"] = (sub["rule_score"] - sub["judge_score"]).abs()
        worst = sub.nlargest(2, "abs_diff")
        if worst["abs_diff"].max() < 0.1: continue
        lines.append(f"### `{fid}` — biggest rule-vs-judge disagreements")
        lines.append("")
        for _, w in worst.iterrows():
            lines.append(f"- **rule={w['rule_score']:.2f}, judge={w['judge_score']:.2f}** "
                       f"({w['paper_id'][:25]}, {w['system_id']})")
            lines.append(f"  - Gold: `{w['gold_value'][:160]}`")
            lines.append(f"  - Cand: `{w['candidate_value'][:160]}`")
            lines.append("")

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines))
    print(f"\nwrote {OUT_MD}")
    print(f"wrote {OUT_PARQUET}")


if __name__ == "__main__":
    main()
