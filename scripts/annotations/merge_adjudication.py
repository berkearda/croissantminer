#!/usr/bin/env python3
"""T-072: merge the 140-cell senior adjudication into gold.parquet.

Reads the adjudication xlsx, updates the 140 tie_split rows in gold.parquet
with adjudicated rating + value + adjudicator_id. Snapshots gold.parquet
before writing per N9.
"""

from __future__ import annotations

import pandas as pd
import shutil
import sys
from pathlib import Path
from datetime import date

ROOT = Path(__file__).resolve().parent.parent.parent
GOLD_PARQUET = ROOT / "data" / "annotations" / "gold.parquet"
SNAPSHOT = ROOT / "data" / "annotations" / f"gold_pre_adjudication_v2_{date.today().isoformat()}.parquet"
ADJUD_XLSX = Path("~/Downloads/CroissantMiner_adjudication_140cells_2026-04-25_Mubashara (3).xlsx")
ADJUDICATOR_ID = "A_Mubashara"


def main():
    print(f"snapshot: {SNAPSHOT}")
    shutil.copy2(GOLD_PARQUET, SNAPSHOT)

    gold = pd.read_parquet(GOLD_PARQUET)
    adj = pd.read_excel(ADJUD_XLSX, sheet_name="Adjudications")
    print(f"gold: {len(gold)} rows; adjudication: {len(adj)} rows")

    pre_tie = (gold["gold_method"] == "tie_split").sum()
    pre_nonnull_gold = gold["gold_value"].notna().sum()
    print(f"pre-merge: {pre_tie} tie_split rows, {pre_nonnull_gold} non-null gold_value")

    n_updated = 0
    for _, ar in adj.iterrows():
        paper, field = ar["Dataset ID"], ar["Field Name"]
        rating = int(ar["Final Rating (1/2/3)"])
        ai_value = ar["AI-Extracted Value"]
        final_value = ar["Final Value (gold)"]
        notes = ar.get("Adjudication Notes")

        # Decide gold_value:
        # rating 1 -> AI extraction was correct, use it
        # rating 2/3 -> use the Final Value the adjudicator wrote
        if rating == 1:
            gold_value = str(ai_value) if pd.notna(ai_value) else None
        else:
            if pd.notna(final_value) and str(final_value).strip():
                gold_value = str(final_value).strip()
            else:
                gold_value = None  # T-073 fallback (shouldn't happen now)

        # Locate the matching row in gold.parquet
        mask = (gold["paper_id"] == paper) & (gold["field_id"] == field)
        matches = mask.sum()
        if matches != 1:
            print(f"  WARN: {paper}/{field} matched {matches} rows; expected 1")
            continue
        existing_method = gold.loc[mask, "gold_method"].iloc[0]
        if existing_method not in ("tie_split", "adjudicated"):
            print(f"  WARN: {paper}/{field} is {existing_method!r}; skipping to avoid clobber")
            continue

        gold.loc[mask, "gold_method"] = "adjudicated"
        gold.loc[mask, "gold_rating"] = rating
        gold.loc[mask, "gold_value"] = gold_value
        gold.loc[mask, "adjudicator_id"] = ADJUDICATOR_ID
        if pd.notna(notes) and str(notes).strip():
            gold.loc[mask, "adjudication_notes"] = str(notes).strip()
        n_updated += 1

    print(f"updated: {n_updated} rows")

    # Verify
    post_tie = (gold["gold_method"] == "tie_split").sum()
    post_adjudicated = (gold["gold_method"] == "adjudicated").sum()
    post_nonnull_gold = gold["gold_value"].notna().sum()
    print(f"post-merge: {post_tie} tie_split, {post_adjudicated} adjudicated, {post_nonnull_gold} non-null gold_value")

    # Save
    gold.to_parquet(GOLD_PARQUET, index=False)
    print(f"wrote {GOLD_PARQUET}")


if __name__ == "__main__":
    main()
