#!/usr/bin/env python3
"""T-052: merge the 14 filled-in missing-gold values into gold.parquet.

Reads CroissantMiner_missing_gold_2026-04-25_Berke.xlsx, updates the 14
null-gold rows with the Final Gold Value, sets gold_method to
'adjudicated_berke', and stamps adjudicator_id. Snapshots gold.parquet
first per N9.
"""

from __future__ import annotations

import pandas as pd
import shutil
from pathlib import Path
from datetime import date

ROOT = Path(__file__).resolve().parent.parent.parent
GOLD_PARQUET = ROOT / "data" / "annotations" / "gold.parquet"
SNAPSHOT = ROOT / "data" / "annotations" / f"gold_pre_missing_berke_{date.today().isoformat()}.parquet"
XLSX = Path("~/Downloads/CroissantMiner_missing_gold_2026-04-25_Berke.xlsx")
ADJUDICATOR_ID = "A_Berke"


def main():
    print(f"snapshot: {SNAPSHOT}")
    shutil.copy2(GOLD_PARQUET, SNAPSHOT)

    gold = pd.read_parquet(GOLD_PARQUET)
    df = pd.read_excel(XLSX, sheet_name="Missing Gold")
    print(f"gold: {len(gold)} rows; missing-gold sheet: {len(df)} rows")

    pre_null = gold["gold_value"].isna().sum()
    print(f"pre-merge: {pre_null} null gold_value cells")

    n_updated = 0
    for _, ar in df.iterrows():
        paper = ar["Dataset ID"]
        field = ar["Field Name"]
        fgv = ar["Final Gold Value"]
        notes = ar.get("Notes (optional)")

        if pd.isna(fgv) or not str(fgv).strip():
            print(f"  WARN: row {ar['#']} ({paper}/{field}) has blank Final Gold Value; skipping")
            continue

        fgv_str = str(fgv).strip()
        # Treat [NULL ...] entries as actual NULL gold_value but still mark adjudicated.
        if fgv_str.upper().startswith("[NULL"):
            gold_value = None
        else:
            gold_value = fgv_str

        mask = (gold["paper_id"] == paper) & (gold["field_id"] == field)
        matches = mask.sum()
        if matches != 1:
            print(f"  WARN: {paper}/{field} matched {matches} rows; expected 1")
            continue
        if gold.loc[mask, "gold_value"].notna().iloc[0]:
            print(f"  WARN: {paper}/{field} already has non-null gold_value; skipping")
            continue

        gold.loc[mask, "gold_method"] = "adjudicated_berke"
        gold.loc[mask, "gold_value"] = gold_value
        gold.loc[mask, "adjudicator_id"] = ADJUDICATOR_ID
        if pd.notna(notes) and str(notes).strip():
            gold.loc[mask, "adjudication_notes"] = str(notes).strip()
        n_updated += 1

    print(f"updated: {n_updated} rows")

    post_null = gold["gold_value"].isna().sum()
    post_berke = (gold["gold_method"] == "adjudicated_berke").sum()
    print(f"post-merge: {post_null} null gold_value, {post_berke} adjudicated_berke")
    print("gold_method counts post-merge:")
    print(gold["gold_method"].value_counts(dropna=False).to_string())

    gold.to_parquet(GOLD_PARQUET, index=False)
    print(f"wrote {GOLD_PARQUET}")


if __name__ == "__main__":
    main()
