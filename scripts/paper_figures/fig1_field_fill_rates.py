"""Figure 1 — Per-field fill-rate ranking across the 602-paper benchmark.

Replaces the legacy `fig1_dataset_stats` and `fig2_field_value_distribution`
in §3.5. Single panel: 30 fields ranked by overall (gold + silver) fill rate
descending, with paired bars showing gold vs silver fill rate per field.
Field labels are coloured by group (core vs rai) so the reader can answer
the brief's two questions in one glance: which fields are universally
reported, and is the gap larger across the core/RAI boundary or within the
RAI fields themselves.

Inputs:
  data/analysis/coverage.parquet   18,060 rows (602 papers x 30 fields x
                                   {gold, silver}); locked null rule already
                                   applied. Source:
                                   scripts/analysis/sec3_5_compute.py.

Headline numbers reproduced from this file:
  gold mean populated/paper   = 21.4   (102 papers)
  silver mean populated/paper = 18.7   (500 papers)
  full corpus mean            = 19.16
  license fill rate           = 20.6%   (sparsest core field)
  rai:dataImputationProtocol  =  2.5%   (sparsest field overall)
  rai:dataCollectionMissingData = 5.0%
  rai:dataCollectionTimeframe = 22.4%

Outputs:
  results/figures/fig1_field_fill_rates.{pdf,png}
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.paper_figures.style import (  # noqa: E402
    COLORS, DOUBLE_COL, save_fig, setup_style,
)


COVERAGE_FP = ROOT / "data" / "analysis" / "coverage.parquet"

# Brief's palette directive: gold = blue tone, silver = orange tone, RAI = third colour.
GOLD_COLOUR = COLORS["claude"]    # blue
SILVER_COLOUR = COLORS["gpt"]     # orange
CORE_LABEL_COLOUR = "#222222"     # dark grey for core field labels
RAI_LABEL_COLOUR = COLORS["purple"]  # third colour for RAI field labels


def load_coverage() -> pd.DataFrame:
    cov = pd.read_parquet(COVERAGE_FP)
    assert {"paper_id", "split", "field_id", "field_group", "populated"} <= set(cov.columns)
    return cov


def per_field_rates(cov: pd.DataFrame) -> pd.DataFrame:
    """Return one row per field with gold, silver, and overall fill rate."""
    by_split = (
        cov.groupby(["field_id", "split"])["populated"]
        .mean()
        .unstack("split")
        .rename(columns={"gold": "gold_rate", "silver": "silver_rate"})
    )
    overall = cov.groupby("field_id")["populated"].mean().rename("overall_rate")
    group = cov.groupby("field_id")["field_group"].first()
    df = by_split.join(overall).join(group)
    df = df.sort_values("overall_rate", ascending=True)  # ascending → top of axis = densest after invert
    return df.reset_index()


def main() -> None:
    setup_style()
    cov = load_coverage()
    rates = per_field_rates(cov)

    n = len(rates)
    y = np.arange(n)
    bar_h = 0.4

    fig, ax = plt.subplots(figsize=(DOUBLE_COL, 9.5))

    # Paired bars: gold and silver per field
    ax.barh(y - bar_h / 2, rates["gold_rate"] * 100, height=bar_h,
            color=GOLD_COLOUR, edgecolor="white", linewidth=0.4, label="gold (102 papers)")
    ax.barh(y + bar_h / 2, rates["silver_rate"] * 100, height=bar_h,
            color=SILVER_COLOUR, edgecolor="white", linewidth=0.4, label="silver (500 papers)")

    # Tick labels coloured by field group
    ax.set_yticks(y)
    ax.set_yticklabels(rates["field_id"], fontsize=8)
    for tick, group in zip(ax.get_yticklabels(), rates["field_group"]):
        tick.set_color(CORE_LABEL_COLOUR if group == "core" else RAI_LABEL_COLOUR)

    # Leave a slim margin past 100% so the right-edge "100%" labels
    # don't bleed past the axes.
    ax.set_xlim(0, 108)
    ax.set_xlabel("Fill rate (% of papers where the field is populated)", fontsize=10)
    ax.set_xticks([0, 20, 40, 60, 80, 100])
    ax.set_xticklabels([f"{x}%" for x in [0, 20, 40, 60, 80, 100]])
    ax.invert_yaxis()  # densest at top after the ascending sort

    # Vertical guide line at the brief's "license = 20.6%" so it's locatable
    ax.axvline(20.6, color="#888888", linestyle=":", linewidth=0.7, zorder=0)
    ax.text(21.0, n - 0.5, "license = 20.6%", fontsize=7, color="#888",
            rotation=90, va="bottom", ha="left")

    # Single combined legend below the plot (split colours + label-colour key)
    split_handles = [
        mpatches.Patch(color=GOLD_COLOUR, label="gold (n = 102)"),
        mpatches.Patch(color=SILVER_COLOUR, label="silver (n = 500)"),
        mpatches.Patch(color=CORE_LABEL_COLOUR, label="core field (label colour)"),
        mpatches.Patch(color=RAI_LABEL_COLOUR, label="RAI field (label colour)"),
    ]
    ax.legend(handles=split_handles, loc="lower center",
              bbox_to_anchor=(0.5, -0.10), ncol=4,
              fontsize=8, frameon=False)

    ax.set_title(
        "Per-field fill rate across the 602-paper benchmark\n"
        f"(gold mean = {rates['gold_rate'].mean()*100:.1f}%, "
        f"silver mean = {rates['silver_rate'].mean()*100:.1f}%; "
        "fields sorted by overall fill rate)",
        fontsize=10, pad=10,
    )

    fig.tight_layout(rect=[0, 0.03, 1, 1])
    save_fig(fig, "fig1_field_fill_rates")


if __name__ == "__main__":
    main()
