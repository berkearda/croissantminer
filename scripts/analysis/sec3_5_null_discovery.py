#!/usr/bin/env python3
"""Sec 3.5 Tier 1: empirical discovery of null-equivalent strings.

Walks gold.parquet (gold_value column) + silver/extractions/*.json
(extraction dict values) and emits a CSV of distinct stripped values
with frequencies and a proposed populated/not classification.

Output: docs/sec3_5_null_candidates.csv
Reviewer eyeballs the proposed classifications; we lock the rule
before any coverage stats are computed.
"""

from __future__ import annotations

import json
import re
import pandas as pd
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
GOLD_PARQUET = ROOT / "data" / "annotations" / "gold.parquet"
SILVER_DIR = ROOT / "silver" / "extractions"
OUT_CSV = ROOT / "docs" / "sec3_5_null_candidates.csv"

# Pre-seed obvious null patterns so we can show the user what would
# be auto-classified vs left UNCERTAIN. The user may overrule any of these.
HARD_NULL_LITERALS = {
    "", "null", "none", "n/a", "na", "nan",
    "not specified", "not stated", "not provided", "not mentioned",
    "not available", "not applicable", "not reported", "not described",
    "unspecified", "unknown",
    "[null]", "[n/a]", "-", "--", "---",
}

NULL_PHRASE_PATTERNS = [
    r"^the (paper|dataset|authors?) (do(es)? not|don'?t) (specify|state|provide|mention|describe|report|discuss|address|disclose)",
    r"^no (information|details?|specific|explicit) (is|are|was|were)?\s*(provided|given|available|mentioned|stated)",
    r"^(this )?information (is )?not (provided|specified|available|stated|disclosed)",
    r"^not (explicitly|directly) (specified|stated|mentioned|provided|described)",
    r"^(no|none) (specified|stated|provided|reported)",
]
NULL_PHRASE_RE = re.compile("|".join(NULL_PHRASE_PATTERNS), re.IGNORECASE)


def classify(stripped_lower: str) -> str:
    if stripped_lower in HARD_NULL_LITERALS:
        return "NULL"
    # Berke convention: [NULL - <reason>] / [NULL] - <reason> / [Null ...] etc.
    if stripped_lower.startswith("[null"):
        return "NULL"
    if NULL_PHRASE_RE.match(stripped_lower):
        return "NULL"
    return "POPULATED"


def main():
    counter: Counter[str] = Counter()
    source_counter: dict[str, Counter[str]] = {"gold": Counter(), "silver": Counter()}

    # Gold side
    gold = pd.read_parquet(GOLD_PARQUET)
    for v in gold["gold_value"]:
        if pd.isna(v):
            stripped = ""
        else:
            stripped = str(v).strip()
        counter[stripped] += 1
        source_counter["gold"][stripped] += 1
    print(f"gold: {len(gold)} cells; {sum(1 for v in gold['gold_value'] if pd.isna(v))} are pandas NA")

    # Silver side
    n_silver_cells = 0
    for f in sorted(SILVER_DIR.glob("*.json")):
        with f.open() as fh:
            d = json.load(fh)
        ext = d.get("extraction", {})
        for k, v in ext.items():
            if v is None:
                stripped = ""
            elif isinstance(v, (list, dict)):
                stripped = json.dumps(v, ensure_ascii=False).strip()
            else:
                stripped = str(v).strip()
            counter[stripped] += 1
            source_counter["silver"][stripped] += 1
            n_silver_cells += 1
    print(f"silver: {n_silver_cells} cells across {len(list(SILVER_DIR.glob('*.json')))} files")

    rows = []
    for value, freq in counter.most_common():
        lower = value.lower()
        proposed = classify(lower)
        # Mark short repeated values as UNCERTAIN if not auto-NULL — these
        # are most likely placeholders we should eyeball.
        if proposed == "POPULATED" and len(value) < 25 and freq >= 5:
            proposed = "UNCERTAIN"
        rows.append({
            "value": value,
            "freq_total": freq,
            "freq_gold": source_counter["gold"][value],
            "freq_silver": source_counter["silver"][value],
            "len_chars": len(value),
            "proposed_class": proposed,
        })

    df = pd.DataFrame(rows)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_CSV, index=False)

    print()
    print(f"distinct stripped values: {len(df)}")
    print(f"  proposed NULL:       {(df['proposed_class']=='NULL').sum()}")
    print(f"  proposed POPULATED:  {(df['proposed_class']=='POPULATED').sum()}")
    print(f"  proposed UNCERTAIN:  {(df['proposed_class']=='UNCERTAIN').sum()}")
    print()
    print("by-class cell coverage (how many of the 18,060 cells each class accounts for):")
    print(df.groupby("proposed_class")["freq_total"].sum())
    print()
    print(f"wrote {OUT_CSV}")
    print()
    print("--- top 20 NULL-proposed values ---")
    print(df[df["proposed_class"] == "NULL"].head(20).to_string(index=False))
    print()
    print("--- top 30 UNCERTAIN-proposed values (need your eyeball) ---")
    print(df[df["proposed_class"] == "UNCERTAIN"].head(30).to_string(index=False))


if __name__ == "__main__":
    main()
