#!/usr/bin/env python3
"""Audit each of the 30 Croissant fields to decide Tier 1 vs Tier 2.

For each field, compute:
1. Length distribution of gold_value (median, mean, p90, max chars)
2. Distinct-value cardinality (low = more categorical)
3. Top-5 most common gold values (the "distribution shape")
4. Sample 3 random gold values
5. Exact-match rate of single-pass extractions vs gold (high = Tier 1 viable)
6. Token-F1 distribution between extractions and gold
7. Recommended tier + reasoning

Output: docs/field_tier_audit.md
"""

from __future__ import annotations
import json
import random
import re
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
GOLD = ROOT / "data" / "annotations" / "gold.parquet"
EXT_BASE = ROOT / "data" / "extractions"
OUT = ROOT / "docs" / "field_tier_audit.md"

# Use the 12 single-pass extractions we have for the inter-system metric
SINGLE_PASS = [
    "claude_sonnet_4_5", "claude_sonnet_4_6", "claude_opus_4_7",
    "gpt5.4_full", "gpt5.4_mini",
    "gemini_3.1_pro", "gemini_2.5_flash",
    "deepseek_v3_2", "glm_5_1",
    "llama4_scout", "mistral_small_4", "qwen3_6_35b_a3b",
]


def normalize(v):
    """Light normalization for exact-match check: strip + lowercase + collapse whitespace."""
    if v is None:
        return None
    if isinstance(v, float) and pd.isna(v):
        return None
    s = str(v).strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s if s else None


def is_null_value(v):
    """Locked null rule from sec3_5_compute.py."""
    if v is None:
        return True
    if isinstance(v, float) and pd.isna(v):
        return True
    if not isinstance(v, str):
        return False
    s = v.strip().lower()
    return s in {"", "not specified", "unknown"} or s.startswith("[null")


def token_set(s):
    if s is None:
        return set()
    return set(re.findall(r"\b\w+\b", s.lower()))


def token_f1(gold, cand):
    g, c = token_set(gold), token_set(cand)
    if not g and not c:
        return 1.0
    if not g or not c:
        return 0.0
    inter = len(g & c)
    if inter == 0:
        return 0.0
    p = inter / len(c)
    r = inter / len(g)
    return 2 * p * r / (p + r)


def jaccard(gold, cand):
    g, c = token_set(gold), token_set(cand)
    if not g and not c:
        return 1.0
    if not (g | c):
        return 0.0
    return len(g & c) / len(g | c)


def load_extractions():
    """Returns dict[system_id][paper_id] -> dict of field values."""
    out = {}
    for sys in SINGLE_PASS:
        d = EXT_BASE / sys
        if not d.exists():
            continue
        out[sys] = {}
        for f in d.glob("*.json"):
            if f.name.startswith("_") or f.stem.startswith("_"):
                continue
            try:
                payload = json.load(open(f))
            except Exception:
                continue
            ext = payload.get("extraction", payload)
            out[sys][f.stem] = ext
    return out


def main():
    gold = pd.read_parquet(GOLD)
    print(f"gold: {len(gold)} rows, {gold['paper_id'].nunique()} papers, "
          f"{gold['field_id'].nunique()} fields")
    extractions = load_extractions()
    print(f"loaded {len(extractions)} single-pass extraction systems")

    # All 30 fields, in canonical order
    field_order = [
        "sc:name", "sc:description", "sc:url", "sc:license", "sc:creator",
        "sc:publisher", "sc:datePublished", "sc:inLanguage", "cr:citeAs",
        "cr:isLiveDataset",
        "rai:dataCollection", "rai:dataCollectionType",
        "rai:dataCollectionMissingData", "rai:dataCollectionRawData",
        "rai:dataCollectionTimeframe", "rai:dataImputationProtocol",
        "rai:dataManipulationProtocol", "rai:dataPreprocessingProtocol",
        "rai:dataAnnotationProtocol", "rai:dataAnnotationPlatform",
        "rai:dataAnnotationAnalysis", "rai:annotationsPerItem",
        "rai:annotatorDemographics", "rai:machineAnnotationTools",
        "rai:dataReleaseMaintenancePlan", "rai:personalSensitiveInformation",
        "rai:dataSocialImpact", "rai:dataBiases", "rai:dataLimitations",
        "rai:dataUseCases",
    ]

    rows = []
    for fid in field_order:
        sub = gold[gold["field_id"] == fid].copy()
        # Drop null gold cells
        sub = sub[~sub["gold_value"].apply(is_null_value)]
        if len(sub) == 0:
            rows.append({
                "field": fid, "n_gold": 0,
                "len_med": 0, "len_mean": 0, "len_p90": 0, "len_max": 0,
                "card": 0, "card_pct": 0,
                "match_rate": 0, "tokf1_med": 0, "jaccard_med": 0,
                "samples": "", "top_values": "",
                "tier_recommend": "—", "reason": "no usable gold",
            })
            continue

        lengths = sub["gold_value"].astype(str).str.len()
        n = len(sub)
        cardinality = sub["gold_value"].nunique()

        # Top 3 distinct values (frequency)
        top_vals = sub["gold_value"].astype(str).str.strip().str.lower().value_counts().head(3)
        top_str = "; ".join(f"{v[:40]}({c})" for v, c in top_vals.items())

        # 3 random samples
        random.seed(0)
        samples_idx = random.sample(range(len(sub)), min(3, len(sub)))
        samples = " | ".join(str(sub.iloc[i]["gold_value"])[:80] for i in samples_idx)

        # Inter-system: for each paper in this field, compute exact-match
        # rate of single-pass extractions vs gold
        match_count = 0
        match_total = 0
        f1_scores = []
        jac_scores = []
        for _, gold_row in sub.iterrows():
            paper = gold_row["paper_id"]
            gv_norm = normalize(gold_row["gold_value"])
            for sys, papers in extractions.items():
                if paper not in papers:
                    continue
                ext = papers[paper]
                short = fid.split(":")[-1] if ":" in fid else fid
                cand = ext.get(fid, ext.get(short))
                if cand is None or is_null_value(cand):
                    continue
                cand_norm = normalize(cand)
                match_total += 1
                if gv_norm == cand_norm:
                    match_count += 1
                f1_scores.append(token_f1(str(gold_row["gold_value"]), str(cand)))
                jac_scores.append(jaccard(str(gold_row["gold_value"]), str(cand)))

        match_rate = match_count / match_total if match_total > 0 else 0.0
        tokf1_med = pd.Series(f1_scores).median() if f1_scores else 0.0
        jac_med = pd.Series(jac_scores).median() if jac_scores else 0.0

        # Tier recommendation heuristic
        if lengths.median() <= 30 and cardinality / n < 0.5:
            tier = "Tier 1 (exact match)"
            reason = f"short ({lengths.median():.0f}c median) + categorical (card/n={cardinality/n:.2f})"
        elif lengths.median() <= 100 and (match_rate > 0.4 or jac_med > 0.6):
            tier = "Tier 1 (Jaccard or token-F1)"
            reason = f"short prose ({lengths.median():.0f}c median); match-rate {match_rate:.2f}, jaccard {jac_med:.2f}"
        elif lengths.median() > 200:
            tier = "Tier 2 (LLM judge)"
            reason = f"long prose ({lengths.median():.0f}c median); semantic equivalence dominates"
        elif match_rate < 0.2 and tokf1_med < 0.4:
            tier = "Tier 2 (LLM judge)"
            reason = f"low surface overlap (match {match_rate:.2f}, F1 {tokf1_med:.2f}); semantic"
        else:
            tier = "Borderline"
            reason = f"len {lengths.median():.0f}c, card/n {cardinality/n:.2f}, match {match_rate:.2f}, F1 {tokf1_med:.2f}"

        rows.append({
            "field": fid, "n_gold": n,
            "len_med": int(lengths.median()), "len_mean": int(lengths.mean()),
            "len_p90": int(lengths.quantile(0.9)), "len_max": int(lengths.max()),
            "card": cardinality, "card_pct": round(cardinality / n, 2),
            "match_rate": round(match_rate, 2),
            "tokf1_med": round(float(tokf1_med), 2),
            "jaccard_med": round(float(jac_med), 2),
            "top_values": top_str,
            "samples": samples,
            "tier_recommend": tier, "reason": reason,
        })

    df = pd.DataFrame(rows)

    # Write markdown
    lines = [
        "# Field-by-field tier audit (Tier 1 vs Tier 2)",
        "",
        f"Computed from `gold.parquet` ({sum(r['n_gold'] for r in rows)} usable cells, "
        f"locked null rule applied) and {len(extractions)} single-pass extraction systems.",
        "",
        "## Per-field summary",
        "",
        "| Field | n | len(med/p90/max) | card | match | F1 | Jacc | Tier recommend | Reason |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| `{r['field']}` | {r['n_gold']} | {r['len_med']}/{r['len_p90']}/{r['len_max']} | "
            f"{r['card']} ({r['card_pct']}) | {r['match_rate']} | {r['tokf1_med']} | "
            f"{r['jaccard_med']} | **{r['tier_recommend']}** | {r['reason']} |"
        )

    lines.extend(["", "## Per-field detail", ""])
    for r in rows:
        lines.append(f"### `{r['field']}` — {r['tier_recommend']}")
        lines.append("")
        lines.append(f"- n usable gold = {r['n_gold']}; "
                    f"length median/mean/p90/max = "
                    f"{r['len_med']}/{r['len_mean']}/{r['len_p90']}/{r['len_max']} chars")
        lines.append(f"- distinct values = {r['card']} of {r['n_gold']} "
                    f"(card/n = {r['card_pct']})")
        lines.append(f"- single-pass exact-match rate vs gold = {r['match_rate']}; "
                    f"token-F1 median = {r['tokf1_med']}; Jaccard median = {r['jaccard_med']}")
        if r['top_values']:
            lines.append(f"- top 3 gold values: {r['top_values']}")
        if r['samples']:
            lines.append(f"- 3 random samples: `{r['samples']}`")
        lines.append(f"- **Reasoning:** {r['reason']}")
        lines.append("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines))
    print(f"\nwrote {OUT}")

    # Print quick summary table
    print()
    print(f"{'field':40s} {'n':>4s} {'len_med':>7s} {'card':>5s} {'match':>5s} {'F1':>5s} {'tier':>30s}")
    for r in rows:
        print(f"{r['field']:40s} {r['n_gold']:>4d} {r['len_med']:>7d} "
              f"{r['card']:>5d} {r['match_rate']:>5.2f} {r['tokf1_med']:>5.2f} "
              f"{r['tier_recommend']:>30s}")


if __name__ == "__main__":
    main()
