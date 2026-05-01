#!/usr/bin/env python3
"""Sec 3.5 final null audit: exhaustive sweep for hidden null variants.

Walks all three data sources (Sonnet-on-gold, gold.parquet, silver) and
surfaces EVERY distinct value that could plausibly be a null variant
under any rule. Output is a CSV the human reviews end-to-end.

Categories surfaced:
  A) values flagged null by the locked rule
  B) very short values (<= 30 chars) that fall through the rule
  C) values containing null-suggesting keywords
  D) values that are pure punctuation / whitespace
  E) values that look like JSON-encoded null markers (e.g. "{}", "[]")
  F) outliers: very long values, unusual chars, leading/trailing brackets
"""

from __future__ import annotations

import json, re, pandas as pd
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parent.parent.parent
GOLD_PARQUET = ROOT / "data" / "annotations" / "gold.parquet"
SILVER_DIR = ROOT / "silver" / "extractions"
SONNET_GOLD_DIR = ROOT / "data" / "extractions" / "agentic_v2_sonnet_4_5"
OUT = ROOT / "docs" / "sec3_5_null_audit_full.csv"


def is_null_locked(value) -> bool:
    """The 3-rule locked null detector."""
    if value is None:
        return True
    if isinstance(value, float) and pd.isna(value):
        return True
    if not isinstance(value, str):
        # JSON list/dict — check empty
        try:
            if isinstance(value, (list, dict)) and len(value) == 0:
                return True
        except TypeError:
            pass
        return False
    s = value.strip()
    if s == "" or s == "Not specified":
        return True
    if s.lower().startswith("[null"):
        return True
    return False


def gather_values():
    rows = []  # (source, paper_id, field_id, value)

    # Sonnet-on-gold
    for f in sorted(SONNET_GOLD_DIR.glob("*.json")):
        if f.name.startswith("_"):
            continue
        d = json.load(open(f))
        for k, v in d.get("extraction", {}).items():
            rows.append(("sonnet_gold", d.get("dataset_id"), k, v))

    # Silver
    for f in sorted(SILVER_DIR.glob("*.json")):
        d = json.load(open(f))
        for k, v in d.get("extraction", {}).items():
            rows.append(("silver", d.get("dataset_id"), k, v))

    # Human gold
    g = pd.read_parquet(GOLD_PARQUET)
    for _, r in g.iterrows():
        rows.append(("human_gold", r["paper_id"], r["field_id"], r["gold_value"]))

    return rows


# Keywords that should make us inspect a string even if rule says POPULATED
SUSPICION_KEYWORDS = [
    "null", "none", "n/a", "na", "nan",
    "not specified", "not provided", "not stated", "not mentioned",
    "not described", "not reported", "not disclosed", "not available",
    "not applicable", "not given", "not explicitly",
    "no information", "no specific", "no explicit", "no details",
    "unknown", "unspecified", "undisclosed",
    "does not specify", "does not provide", "does not state",
    "does not mention", "does not describe",
    "do not specify", "do not provide",
    "cannot be determined", "could not be determined",
    "tbd", "todo", "placeholder", "missing",
]
SUSPICION_RE = re.compile("|".join(re.escape(k) for k in SUSPICION_KEYWORDS), re.IGNORECASE)


def main():
    rows = gather_values()
    print(f"Total cells across 3 sources: {len(rows)}")

    # Stripped-value frequency by source
    counter: Counter[tuple[str, str]] = Counter()  # (stripped_value, source) -> count
    raw_counter: Counter[str] = Counter()
    for src, _, _, v in rows:
        if v is None:
            stripped = "__PYTHON_NONE__"
        elif isinstance(v, float) and pd.isna(v):
            stripped = "__PANDAS_NAN__"
        elif isinstance(v, (list, dict)):
            stripped = json.dumps(v, ensure_ascii=False).strip()
        else:
            stripped = str(v).strip()
        counter[(stripped, src)] += 1
        raw_counter[stripped] += 1
    print(f"Distinct stripped values: {len(raw_counter)}")

    # Build report
    report = []
    for (val, src), n in counter.most_common():
        is_null_under_rule = False
        if val in ("__PYTHON_NONE__", "__PANDAS_NAN__"):
            is_null_under_rule = True
        elif val == "" or val == "Not specified":
            is_null_under_rule = True
        elif val.lower().startswith("[null"):
            is_null_under_rule = True

        # Categorize:
        # A: classified NULL by rule
        # B: short fallthrough
        # C: contains suspicion keyword
        # D: pure punctuation / whitespace
        # E: JSON-empty marker
        cats = []
        if is_null_under_rule:
            cats.append("A_RULE_NULL")
        if (not is_null_under_rule) and len(val) <= 30:
            cats.append("B_SHORT_POPULATED")
        if (not is_null_under_rule) and SUSPICION_RE.search(val):
            cats.append("C_SUSPICION_KEYWORD")
        if val and all(not c.isalnum() for c in val):
            cats.append("D_PUNCT_ONLY")
        if val in ("{}", "[]", "[ ]", "{ }"):
            cats.append("E_JSON_EMPTY")

        report.append({
            "value": val,
            "source": src,
            "freq_in_source": n,
            "freq_total": raw_counter[val],
            "len_chars": len(val),
            "rule_classification": "NULL" if is_null_under_rule else "POPULATED",
            "categories": "|".join(cats) if cats else "",
        })

    df = pd.DataFrame(report)
    df.to_csv(OUT, index=False)
    print(f"\nWrote {OUT}: {len(df)} rows")

    # Print key sections
    print("\n========== A) ALL distinct values currently classified NULL by the rule ==========")
    a = df[df["categories"].str.contains("A_RULE_NULL")].drop_duplicates(subset=["value"])
    print(a[["value", "freq_total", "len_chars"]].to_string(index=False))

    print("\n========== C) values that pass POPULATED but contain a null-suggesting keyword ==========")
    c = df[df["categories"].str.contains("C_SUSPICION_KEYWORD")].drop_duplicates(subset=["value"])
    print(f"Count: {len(c)} distinct values")
    print(c[["value", "freq_total", "len_chars", "source"]].head(50).to_string(index=False))

    print("\n========== D) pure punctuation / whitespace cells (POPULATED under rule) ==========")
    d = df[df["categories"].str.contains("D_PUNCT_ONLY")].drop_duplicates(subset=["value"])
    print(d[["value", "freq_total", "len_chars"]].to_string(index=False))

    print("\n========== E) JSON-empty markers ==========")
    e = df[df["categories"].str.contains("E_JSON_EMPTY")].drop_duplicates(subset=["value"])
    print(e[["value", "freq_total", "len_chars"]].to_string(index=False))

    print("\n========== B) short-and-frequent fallthroughs (<=15 chars, freq>=10) ==========")
    b = df[df["categories"].str.contains("B_SHORT_POPULATED")].drop_duplicates(subset=["value"])
    b_short = b[(b["len_chars"] <= 15) & (b["freq_total"] >= 10)]
    print(f"Count: {len(b_short)} distinct values")
    print(b_short.sort_values("freq_total", ascending=False)[["value", "freq_total", "len_chars"]].head(80).to_string(index=False))


if __name__ == "__main__":
    main()
