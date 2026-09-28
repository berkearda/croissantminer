#!/usr/bin/env python3
"""Build calibration + validation sets for the v3 rubric tuning loop.

Splits the 196 audit cells (200 minus the 4 deciding-vote outliers)
into:
  - 30-cell calibration set (used to tune rubric language)
  - 30-cell validation set  (used to verify rubric generalises)
  - 136 cells reserved for the full Stage A audit

Stratified by consensus rating to preserve the 84/51/61 distribution.
Fixed seed for reproducibility.
"""

from __future__ import annotations

import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
HUMAN = ROOT / "data" / "audit" / "_human_ratings.parquet"
AUDIT = ROOT / "data" / "annotations" / "audit_set_200.parquet"
OUT_CAL = ROOT / "data" / "audit" / "_calibration_30.parquet"
OUT_VAL = ROOT / "data" / "audit" / "_validation_30.parquet"

OUTLIERS = {58, 81, 170, 180}
SEED = 0
N_CAL_PER_CLASS = (13, 8, 9)  # consensus 1, 2, 3 (proportional to 84/51/61)


def main():
    audit = pd.read_parquet(AUDIT)
    humans = pd.read_parquet(HUMAN)
    df = audit.merge(humans[["row_id", "rating_consensus"]], on="row_id")

    df = df[~df["row_id"].isin(OUTLIERS)].copy()
    print(f"available cells (200 - 4 outliers): {len(df)}")

    cal_rows = []
    val_rows = []
    rng = pd.Series(range(len(df))).sample(frac=1, random_state=SEED).values  # noqa
    for cls, n_cal in zip([1, 2, 3], N_CAL_PER_CLASS):
        sub = df[df["rating_consensus"] == cls].sample(frac=1, random_state=SEED + cls).reset_index(drop=True)
        cal_rows.append(sub.iloc[:n_cal])
        val_rows.append(sub.iloc[n_cal:n_cal * 2])

    cal = pd.concat(cal_rows, ignore_index=True)
    val = pd.concat(val_rows, ignore_index=True)

    print(f"\ncalibration set: {len(cal)} cells")
    print(cal["rating_consensus"].value_counts().sort_index().to_string())
    print(f"\nvalidation set:  {len(val)} cells")
    print(val["rating_consensus"].value_counts().sort_index().to_string())

    # Sanity: disjoint
    assert set(cal["row_id"]).isdisjoint(set(val["row_id"]))
    print(f"\ndisjoint: cal ∩ val = {len(set(cal['row_id']) & set(val['row_id']))} (should be 0)")

    # Field diversity
    print(f"\ncalibration fields covered: {cal['field_id'].nunique()} unique")
    print(f"validation  fields covered: {val['field_id'].nunique()} unique")

    OUT_CAL.parent.mkdir(parents=True, exist_ok=True)
    cal.to_parquet(OUT_CAL, index=False)
    val.to_parquet(OUT_VAL, index=False)
    print(f"\nwrote {OUT_CAL}")
    print(f"wrote {OUT_VAL}")


if __name__ == "__main__":
    main()
