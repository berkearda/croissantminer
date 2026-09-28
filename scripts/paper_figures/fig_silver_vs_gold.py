#!/usr/bin/env python3
"""A3 — Silver-vs-gold validation figure for the appendix.

Single panel: per-field fill-rate scatter, gold (102 papers) on x-axis,
silver (500 papers) on y-axis. 30 points (one per Croissant field).
Diagonal y=x reference. Pearson r and Spearman rho annotated.

Story: silver split is consistent with the human-validated gold split,
validating its use as a larger proxy for §3.4 prose.

Output: docs/figure_iterations/A3/fig_silver_vs_gold_iter<N>.{png,pdf}
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data" / "analysis" / "coverage.parquet"
OUT_DIR = ROOT / "docs" / "figure_iterations" / "A3"
OUT_DIR.mkdir(parents=True, exist_ok=True)

COLORS = {"core": "#0072B2", "rai": "#D55E00"}
MARKER = {"core": "o", "rai": "s"}

# Hand-pick which points to label (extremes that anchor the eye)
LABEL_FIELDS = {
    "isLiveDataset":                 "isLiveDataset",
    "citeAs":                        "citeAs",
    "license":                       "license",
    "rai:dataImputationProtocol":    "dataImputation",
    "rai:dataCollectionMissingData": "dataMissing",
    "rai:dataUseCases":              "dataUseCases",
}

# Per-field (dx, dy, ha, va) — manual offsets to avoid label collisions.
LABEL_OFFSETS = {
    "isLiveDataset":                 (-6, 8, "right", "bottom"),
    "citeAs":                        (-5, -3, "right", "top"),
    "license":                       (5, -2, "left", "top"),
    "rai:dataImputationProtocol":    (5, -2, "left", "top"),
    "rai:dataCollectionMissingData": (5, 4, "left", "bottom"),
    "rai:dataUseCases":              (-18, -2, "right", "center"),
}


def render(iteration: int) -> Path:
    df = pd.read_parquet(DATA)
    fr = (df.groupby(["split", "field_id", "field_group"])["populated"]
            .mean().reset_index())
    g = fr[fr["split"] == "gold"].set_index("field_id")
    s = fr[fr["split"] == "silver"].set_index("field_id")
    m = g[["populated", "field_group"]].join(s["populated"], rsuffix="_silver")
    m = m.rename(columns={"populated": "gold", "populated_silver": "silver"})
    m = (m * 100).where(m.dtypes == float, m).reset_index()
    # The .where above messed with dtype; redo cleanly:
    m = g[["populated", "field_group"]].join(s["populated"], rsuffix="_silver")
    m = m.rename(columns={"populated": "gold", "populated_silver": "silver"})
    m["gold"] = m["gold"] * 100
    m["silver"] = m["silver"] * 100
    m = m.reset_index()

    pearson_r = np.corrcoef(m["gold"], m["silver"])[0, 1]
    spearman_rho, sp_p = spearmanr(m["gold"], m["silver"])

    # Square scatter; included with width=0.7\linewidth = 3.85" at 1:1.
    fig, ax = plt.subplots(figsize=(3.85, 3.85), dpi=300)

    # Diagonal y=x reference (drawn first, behind data)
    ax.plot([0, 100], [0, 100], color="#999999", linestyle="--",
            linewidth=0.8, zorder=1, label="y = x (perfect agreement)")

    # Scatter, split by group
    for grp, sub in m.groupby("field_group"):
        ax.scatter(
            sub["gold"], sub["silver"],
            s=70, c=COLORS[grp], marker=MARKER[grp],
            edgecolor="black", linewidth=0.6, alpha=0.85,
            label=f"{'core' if grp == 'core' else 'RAI'} ({len(sub)})",
            zorder=3,
        )

    # Annotate the picked extremes with manual offsets
    for _, row in m.iterrows():
        if row["field_id"] not in LABEL_FIELDS:
            continue
        label = LABEL_FIELDS[row["field_id"]]
        dx, dy, ha, va = LABEL_OFFSETS[row["field_id"]]
        ax.annotate(
            label,
            xy=(row["gold"], row["silver"]),
            xytext=(row["gold"] + dx, row["silver"] + dy),
            fontsize=6.5, color="#333", ha=ha, va=va,
            arrowprops=dict(arrowstyle="-", color="#888", lw=0.5),
        )

    ax.set_xlim(-3, 105)
    ax.set_ylim(-3, 105)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_xticklabels(["0%", "25%", "50%", "75%", "100%"], fontsize=7.5)
    ax.set_yticklabels(["0%", "25%", "50%", "75%", "100%"], fontsize=7.5)
    ax.set_xlabel("Gold split fill rate (102 papers, human-validated)", fontsize=8)
    ax.set_ylabel("Silver split fill rate (500 papers, Sonnet 4.5 reference)", fontsize=8)
    ax.set_aspect("equal")

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_axisbelow(True)
    ax.grid(True, color="#EEEEEE", linewidth=0.6, zorder=0)

    # Combined stats + legend block in the upper-left so the bottom-right
    # quadrant stays clear for the isLiveDataset outlier.
    legend_handles, legend_labels = ax.get_legend_handles_labels()
    stats_text = (
        f"Pearson r = {pearson_r:.3f}\n"
        f"Spearman ρ = {spearman_rho:.3f}\n"
        f"n = 30 fields"
    )
    ax.text(
        0.04, 0.97, stats_text,
        transform=ax.transAxes, fontsize=7.5,
        va="top", ha="left",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="white",
                  edgecolor="#CCCCCC", linewidth=0.6),
    )
    ax.legend(
        handles=legend_handles, labels=legend_labels,
        loc="upper left", frameon=True, framealpha=0.95,
        edgecolor="#CCCCCC", fontsize=7,
        bbox_to_anchor=(0.04, 0.78),
    )

    fig.suptitle(
        "Silver tracks gold (r = 0.85)",
        fontsize=10, fontweight="bold", y=0.99, x=0.05, ha="left",
    )

    plt.subplots_adjust(top=0.91, bottom=0.10, left=0.11, right=0.97)

    out_png = OUT_DIR / f"fig_silver_vs_gold_iter{iteration}.png"
    out_pdf = OUT_DIR / f"fig_silver_vs_gold_iter{iteration}.pdf"
    fig.savefig(out_png, dpi=300, bbox_inches="tight", facecolor="white")
    fig.savefig(out_pdf, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out_png


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--iter", type=int, default=1)
    args = p.parse_args()
    out = render(args.iter)
    print(f"wrote {out.relative_to(ROOT)} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
