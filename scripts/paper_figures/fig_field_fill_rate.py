#!/usr/bin/env python3
"""A1 — Per-field fill-rate ranking across the 30 Croissant fields.

Figure for §3.5 (main paper). Replaces old Fig 1 + Fig 2 per the
2026-04-30 (PM, late) §3 figure restructure decision.

Claim: Fill-rate varies dramatically across the 30 Croissant fields,
spanning from 100% (universal: name, description, dataUseCases) down to
2.5% (rai:dataImputationProtocol). The gap is largest WITHIN the RAI
group, not between core and RAI.

Data: data/analysis/coverage.parquet (18,060 rows, 602 papers × 30 fields).

Output: docs/figure_iterations/A1/fig_field_fill_rate_iter<N>.png + .pdf
"""

from __future__ import annotations

import argparse
from pathlib import Path

import math

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd


def wilson_ci(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    """Two-sided Wilson 95% CI for a binomial proportion, returned in [0, 100]."""
    if n == 0:
        return 0.0, 0.0
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, (centre - half) * 100), min(100.0, (centre + half) * 100)

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data" / "analysis" / "coverage.parquet"
OUT_DIR = ROOT / "docs" / "figure_iterations" / "A1"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# Paper-wide color map (Okabe-Ito accessible palette)
COLORS = {
    "core": "#0072B2",  # blue
    "rai":  "#D55E00",  # vermillion
}
HATCHES = {
    "core": "",
    "rai":  "//",
}

# Friendlier field labels for the figure (drop sc:/cr:/rai: prefix where safe)
LABEL_FIX = {
    "name": "name",
    "description": "description",
    "url": "url",
    "license": "license",
    "creator": "creator",
    "publisher": "publisher",
    "datePublished": "datePublished",
    "inLanguage": "inLanguage",
    "citeAs": "citeAs",
    "isLiveDataset": "isLiveDataset",
    "rai:dataCollection": "dataCollection",
    "rai:dataCollectionType": "dataCollectionType",
    "rai:dataCollectionMissingData": "dataCollectionMissingData",
    "rai:dataCollectionRawData": "dataCollectionRawData",
    "rai:dataCollectionTimeframe": "dataCollectionTimeframe",
    "rai:dataImputationProtocol": "dataImputationProtocol",
    "rai:dataManipulationProtocol": "dataManipulationProtocol",
    "rai:dataPreprocessingProtocol": "dataPreprocessingProtocol",
    "rai:dataAnnotationProtocol": "dataAnnotationProtocol",
    "rai:dataAnnotationPlatform": "dataAnnotationPlatform",
    "rai:dataAnnotationAnalysis": "dataAnnotationAnalysis",
    "rai:annotationsPerItem": "annotationsPerItem",
    "rai:annotatorDemographics": "annotatorDemographics",
    "rai:machineAnnotationTools": "machineAnnotationTools",
    "rai:dataReleaseMaintenancePlan": "dataReleaseMaintenancePlan",
    "rai:personalSensitiveInformation": "personalSensitiveInformation",
    "rai:dataSocialImpact": "dataSocialImpact",
    "rai:dataBiases": "dataBiases",
    "rai:dataLimitations": "dataLimitations",
    "rai:dataUseCases": "dataUseCases",
}


def render(iteration: int) -> Path:
    df = pd.read_parquet(DATA)
    fill = (df.groupby(["field_id", "field_group"])["populated"]
              .agg(k="sum", n="count").reset_index())
    fill["pct"] = (fill["k"] / fill["n"] * 100).round(1)
    ci = fill.apply(lambda r: wilson_ci(int(r["k"]), int(r["n"])), axis=1)
    fill["ci_lo"] = [c[0] for c in ci]
    fill["ci_hi"] = [c[1] for c in ci]
    fill = fill.sort_values("pct", ascending=True)  # asc → top of plot is highest
    n_papers = df["paper_id"].nunique()

    # Saved at NeurIPS \linewidth (5.5"); include with width=\linewidth at 1:1.
    fig, ax = plt.subplots(figsize=(5.5, 6.5), dpi=300)
    y_pos = range(len(fill))
    bar_colors = [COLORS[g] for g in fill["field_group"]]
    bar_hatches = [HATCHES[g] for g in fill["field_group"]]

    import numpy as np
    pcts = fill["pct"].to_numpy()
    err_lo = np.clip(pcts - fill["ci_lo"].to_numpy(), 0, None)
    err_hi = np.clip(fill["ci_hi"].to_numpy() - pcts, 0, None)

    bars = ax.barh(
        y_pos, pcts,
        color=bar_colors, edgecolor="black", linewidth=0.4,
        height=0.78,
        xerr=[err_lo, err_hi],
        error_kw=dict(ecolor="#333333", elinewidth=0.7, capsize=2.0, capthick=0.7),
    )
    # Apply hatches per-bar (set_hatch on each)
    for bar, hatch in zip(bars, bar_hatches):
        bar.set_hatch(hatch)

    # Y-axis: field names
    ax.set_yticks(list(y_pos))
    ax.set_yticklabels([LABEL_FIX[f] for f in fill["field_id"]], fontsize=7.5)
    ax.tick_params(axis="y", length=0)

    # X-axis: percentage — extend xlim to leave dedicated label gutter
    ax.set_xlim(0, 118)
    ax.set_xlabel("Documentation rate (% of papers with non-null gold)", fontsize=8.5)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xticklabels(["0%", "25%", "50%", "75%", "100%"], fontsize=7.5)

    # Direct labels: % at end of each bar (placed past the upper CI cap)
    for i, (pct, ci_hi, group) in enumerate(zip(
            fill["pct"], fill["ci_hi"], fill["field_group"])):
        is_surprise = (pct >= 99 and i >= len(fill) - 4) or pct < 6
        weight = "bold" if is_surprise else "normal"
        ax.text(
            ci_hi + 1.4, i, f"{pct:.1f}%",
            va="center", ha="left", fontsize=7, fontweight=weight,
            color="black",
        )

    # Strip top, right, left spines (Cruz #2: no boxes)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)

    # Light vertical reference gridlines behind bars
    ax.set_axisbelow(True)
    ax.xaxis.grid(True, color="#E5E5E5", linewidth=0.6, zorder=0)

    fig.suptitle(
        "Field documentation rates span 100% → 2.5%",
        fontsize=10.5, fontweight="bold", y=0.985, x=0.04, ha="left",
    )

    # Legend — placed in the empty bottom-right quadrant (low fill-rate fields
    # have short bars there), well clear of x-axis tick labels.
    legend_handles = [
        mpatches.Patch(facecolor=COLORS["core"], edgecolor="black",
                       label="core (sc:/cr: prefix)"),
        mpatches.Patch(facecolor=COLORS["rai"], edgecolor="black",
                       hatch="//", label="RAI (rai: prefix)"),
    ]
    ax.legend(
        handles=legend_handles, loc="lower right",
        frameon=True, framealpha=0.95, edgecolor="#CCCCCC",
        fontsize=7.5, bbox_to_anchor=(0.99, 0.02),
    )

    # Annotation: only the bottom extreme — there is room to the right of the
    # 2.5% bar. The top "100%" story is already carried by bold direct labels.
    bottom_idx = 0
    ax.annotate(
        "RAI's deepest hole:\nimputation discussed\nin only 2.5% of papers",
        xy=(3.5, bottom_idx),
        xytext=(45, bottom_idx + 3.0),
        fontsize=7, color="#222",
        arrowprops=dict(arrowstyle="->", color="#666", lw=0.7,
                        connectionstyle="arc3,rad=-0.15"),
        ha="left", va="center",
    )

    plt.subplots_adjust(left=0.30, right=0.98, top=0.92, bottom=0.06)

    out_png = OUT_DIR / f"fig_field_fill_rate_iter{iteration}.png"
    out_pdf = OUT_DIR / f"fig_field_fill_rate_iter{iteration}.pdf"
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
