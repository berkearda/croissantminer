"""Evaluate ReAct-agent extractions against the 88-paper test gold set.

Why a thin wrapper: the canonical evaluator
(`evaluation/evaluate_all.py`) reads the legacy 8-paper
`data/groundtruth_30field/` directory. The merged annotation effort gave
us full 30-field gold for all 102 papers via
`data/annotations/gold.parquet`, so we can score the entire 88-paper test
split here using the SAME field-metric functions.

Inputs:
  data/extractions/react_agent/{paper_id}.json   one per test paper
  data/annotations/gold.parquet                  102 papers x 30 fields
  data/agentic/dev_test_split.json               14 dev + 88 test split
  data/papers_domain.csv                         per-paper domain tag

Outputs:
  results/react_agent_eval/eval_summary.json     headline numbers
  results/react_agent_eval/per_field.csv         per-field mean and N
  results/react_agent_eval/per_paper.csv         per-paper composite
  results/react_agent_eval/per_domain.csv        per-domain composite
  results/react_agent_eval/REPORT.md             human-readable report

Run from repo root:  python scripts/evaluate_react_agent.py
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Field-metric functions (validated by 39+ unit tests; do not reimplement)
from evaluation.field_metrics import (  # noqa: E402
    score_field, finalize_cache,
    get_field_category,
    CONSTRAINED_FIELDS, SHORT_TEXT_FIELDS, LONG_TEXT_RAI_FIELDS, ALL_30_FIELDS,
)

EXTRACTIONS_DIR = ROOT / "data" / "extractions" / "react_agent"
GOLD_FP = ROOT / "data" / "annotations" / "gold.parquet"
SPLIT_FP = ROOT / "data" / "agentic" / "dev_test_split.json"
DOMAIN_FP = ROOT / "data" / "papers_domain.csv"
OUT_DIR = ROOT / "results" / "react_agent_eval"

# Map our extraction's unprefixed general-field names to the prefixed names the
# metric functions and gold.parquet use.  Drop-in copy of evaluate_all.py's map.
FIELD_PREFIX_MAP = {
    "name": "sc:name", "description": "sc:description", "url": "sc:url",
    "license": "sc:license", "creator": "sc:creator", "publisher": "sc:publisher",
    "datePublished": "sc:datePublished", "inLanguage": "sc:inLanguage",
    "citeAs": "cr:citeAs", "isLiveDataset": "cr:isLiveDataset",
}

UNKNOWN_VALUES = {"unknown", "n/a", "none", "null", "not disclosed", "na"}


def classify_null(gt_val, pred_val) -> str:
    """5-bucket null classification (mirrors evaluate_all.py::classify_null)."""
    gt_empty = gt_val is None or not str(gt_val).strip()
    gt_unknown = (not gt_empty and str(gt_val).strip().lower() in UNKNOWN_VALUES)
    pred_empty = pred_val is None or not str(pred_val).strip()
    if gt_empty or gt_unknown:
        return "correct_null" if pred_empty else "hallucination"
    if pred_empty:
        return "miss"
    return "non_null"


def resolve_pred(extraction: dict, prefixed_field: str):
    """Look up a prediction in the extraction JSON, accounting for the
    unprefixed general-field convention used by react_agent outputs."""
    val = extraction.get(prefixed_field)
    if val is not None:
        return val
    short = prefixed_field.split(":")[-1] if ":" in prefixed_field else prefixed_field
    val = extraction.get(short)
    if val is not None:
        return val
    if not prefixed_field.startswith("rai:"):
        val = extraction.get(f"rai:{short}")
    return val


def bootstrap_ci(scores: list, n_boot: int = 2000, ci: float = 0.95, seed: int = 42):
    if not scores:
        return (0.0, 0.0)
    rng = np.random.default_rng(seed)
    arr = np.array(scores)
    means = [float(np.mean(rng.choice(arr, size=len(arr), replace=True)))
             for _ in range(n_boot)]
    means = np.sort(means)
    alpha = (1 - ci) / 2
    return float(means[int(alpha * n_boot)]), float(means[int((1 - alpha) * n_boot)])


def load_test_extractions(paper_ids: set[str]) -> dict[str, dict]:
    """Load each paper's extraction JSON; warn on missing."""
    out = {}
    for pid in sorted(paper_ids):
        p = EXTRACTIONS_DIR / f"{pid}.json"
        if not p.exists():
            continue
        try:
            data = json.loads(p.read_text())
        except json.JSONDecodeError as e:
            print(f"  [skip] {pid}: invalid JSON ({e})")
            continue
        # Strip the _meta block if present
        if isinstance(data, dict) and "_meta" in data:
            data = {k: v for k, v in data.items() if k != "_meta"}
        out[pid] = data
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=["dev", "test", "all"], default="test")
    parser.add_argument("--skip-judge", action="store_true",
                        help="Skip LLM judge for RAI fields (uses token-F1 instead).")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    split = json.loads(SPLIT_FP.read_text())
    if args.split == "all":
        paper_ids = set(split["dev"]) | set(split["test"])
    else:
        paper_ids = set(split[args.split])
    print(f"evaluating {len(paper_ids)} {args.split}-set papers")

    extractions = load_test_extractions(paper_ids)
    print(f"  found extractions for {len(extractions)} / {len(paper_ids)} papers")
    missing = paper_ids - set(extractions)
    if missing:
        print(f"  missing: {sorted(missing)[:6]}{'…' if len(missing) > 6 else ''}")

    gold_df = pd.read_parquet(GOLD_FP)
    gold_df = gold_df[gold_df["paper_id"].isin(paper_ids)]
    print(f"  gold rows for split: {len(gold_df)} ({gold_df['paper_id'].nunique()} papers)")

    domains = (
        pd.read_csv(DOMAIN_FP)[["paper_id", "domain"]] if DOMAIN_FP.exists()
        else pd.DataFrame({"paper_id": [], "domain": []})
    )
    pid_to_domain = dict(zip(domains["paper_id"], domains["domain"]))

    # Score every (paper, field) cell where we have both gold and extraction
    rows = []
    null_buckets = Counter()
    skipped_for_judge = 0

    for _, gold_row in gold_df.iterrows():
        pid = gold_row["paper_id"]
        prefixed_field = gold_row["field_id"]
        gt_val = gold_row["gold_value"]

        if pid not in extractions:
            continue

        pred_val = resolve_pred(extractions[pid], prefixed_field)

        nc = classify_null(gt_val, pred_val)
        null_buckets[nc] += 1

        # Score only cells with gold; null-bucket the rest
        gt_str = str(gt_val).strip() if gt_val is not None and str(gt_val).strip() else None
        pred_str = str(pred_val).strip() if pred_val is not None and str(pred_val).strip() else None

        cat = get_field_category(prefixed_field)
        if gt_str is None:
            # gold is null — credit for matching null, penalty for hallucinating
            score = 1.0 if pred_str is None else 0.0
            metric = "null_handling"
        elif pred_str is None:
            score = 0.0
            metric = "miss"
        else:
            result = score_field(pred_str, gt_str, prefixed_field)
            if result.get("skipped"):
                skipped_for_judge += 1
                continue
            score = float(result["score"])
            metric = result.get("metric", "?")

        rows.append({
            "paper_id": pid,
            "domain": pid_to_domain.get(pid, "Unknown"),
            "field_id": prefixed_field,
            "category": cat,
            "metric": metric,
            "gt_present": gt_str is not None,
            "pred_present": pred_str is not None,
            "score": score,
        })

    finalize_cache()  # flush any LLM-judge cache writes

    df = pd.DataFrame(rows)
    print(f"  scored {len(df)} cells (skipped for judge: {skipped_for_judge})")
    if df.empty:
        print("no scored cells — abort")
        return

    # ── Aggregates ─────────────────────────────────────────────────────────
    composite = float(df["score"].mean())
    ci_lo, ci_hi = bootstrap_ci(df["score"].tolist())

    per_cat = (
        df.groupby("category")["score"].agg(["mean", "count"]).round(4)
    )
    per_field = (
        df.groupby("field_id")["score"].agg(["mean", "count"]).round(4)
        .sort_values("mean", ascending=False)
    )
    per_paper = (
        df.groupby("paper_id")["score"].agg(["mean", "count"]).round(4)
        .sort_values("mean", ascending=False)
    )
    per_domain = (
        df.groupby("domain")["score"].agg(["mean", "count"]).round(4)
        .sort_values("mean", ascending=False)
    )

    # ── Output ─────────────────────────────────────────────────────────────
    summary = {
        "split": args.split,
        "n_papers_scored": int(df["paper_id"].nunique()),
        "n_papers_in_split": len(paper_ids),
        "n_cells_scored": int(len(df)),
        "composite_score": round(composite, 4),
        "composite_ci_95": [round(ci_lo, 4), round(ci_hi, 4)],
        "per_category": {k: {"mean": float(v["mean"]), "n": int(v["count"])}
                         for k, v in per_cat.iterrows()},
        "null_buckets": dict(null_buckets),
        "skip_judge": args.skip_judge,
    }
    (OUT_DIR / "eval_summary.json").write_text(json.dumps(summary, indent=2))
    per_field.to_csv(OUT_DIR / "per_field.csv")
    per_paper.to_csv(OUT_DIR / "per_paper.csv")
    per_domain.to_csv(OUT_DIR / "per_domain.csv")
    df.to_csv(OUT_DIR / "raw_cell_scores.csv", index=False)

    # Markdown report
    md = []
    md.append(f"# ReAct agent — {args.split}-set evaluation\n")
    md.append(f"- Papers scored: **{summary['n_papers_scored']} / {summary['n_papers_in_split']}**")
    md.append(f"- Cells scored: **{summary['n_cells_scored']}**")
    md.append(f"- **Composite score: {composite*100:.1f}% [95% CI {ci_lo*100:.1f}, {ci_hi*100:.1f}]**\n")
    md.append("## Per-category\n")
    md.append("| Category | Mean score | N |")
    md.append("|---|---:|---:|")
    for cat, row in per_cat.iterrows():
        md.append(f"| {cat} | {row['mean']*100:.1f}% | {int(row['count'])} |")
    md.append("\n## Null handling\n")
    md.append("| Bucket | Count |")
    md.append("|---|---:|")
    for k, v in sorted(null_buckets.items(), key=lambda x: -x[1]):
        md.append(f"| {k} | {v} |")
    md.append("\n## Per-domain\n")
    md.append("| Domain | Mean score | N cells |")
    md.append("|---|---:|---:|")
    for dom, row in per_domain.iterrows():
        md.append(f"| {dom} | {row['mean']*100:.1f}% | {int(row['count'])} |")
    md.append("\n## Per-field (sorted by mean)\n")
    md.append("| Field | Mean | N |")
    md.append("|---|---:|---:|")
    for fld, row in per_field.iterrows():
        md.append(f"| `{fld}` | {row['mean']*100:.1f}% | {int(row['count'])} |")
    (OUT_DIR / "REPORT.md").write_text("\n".join(md))

    print()
    print(f"Composite: {composite*100:.1f}%  [95% CI {ci_lo*100:.1f}, {ci_hi*100:.1f}]")
    print()
    print("Per-category:")
    for cat, row in per_cat.iterrows():
        print(f"  {cat:<12} {row['mean']*100:>5.1f}%  (n={int(row['count'])})")
    print()
    print(f"Saved: {OUT_DIR.relative_to(ROOT)}/eval_summary.json + per_*.csv + REPORT.md")


if __name__ == "__main__":
    main()
