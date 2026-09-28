#!/usr/bin/env python3
"""Figure 5 — Failure-mode taxonomy across error cells (§5.4).

Single-panel heatmap of (30 fields × 7 failure-modes) cell counts. Score
target ≥ 90 / 100 on FIGURE_SCORECARD.md. Replaces the prior two-panel
version (stacked bars + heatmap) which scored ≈ 60.

Story: Incomplete extraction is the dominant failure mode (43% of all
error cells); it concentrates on a small set of RAI fields. The unique
counter-pattern is `sc:publisher`, where Wrong Section dominates because
annotators disagree about whether to mark arXiv vs. the venue vs. the
authors' lab.

Output: docs/figure_iterations/A5/fig_failure_modes_iter<N>.{png,pdf}
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
RATINGS = ROOT / "data" / "annotations" / "ratings.parquet"
OUT_DIR = ROOT / "docs" / "figure_iterations" / "A5"
OUT_DIR.mkdir(parents=True, exist_ok=True)

NORM = {
    "Hallucinated": "Hallucination",
    "Wrong": "Other",
    "Partially correct": "Other",
    "Another link provided (seems unrelated to me)": "Other",
}

# Order columns by aggregate prevalence (most common first → leftmost)
FAILURE_ORDER = [
    "Incomplete", "Wrong Section", "Other", "Hallucination",
    "Granularity Mismatch", "Unspecified", "Format Error",
]

LABEL_FIX = {
    "sc:name": "name", "sc:description": "description", "sc:url": "url",
    "sc:license": "license", "sc:creator": "creator",
    "sc:publisher": "publisher", "sc:datePublished": "datePublished",
    "sc:inLanguage": "inLanguage",
    "cr:citeAs": "citeAs", "cr:isLiveDataset": "isLiveDataset",
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
    r = pd.read_parquet(RATINGS)
    err = r[r["rating"].isin([2, 3])].copy()
    err["failure_mode"] = err["failure_mode"].fillna("Unspecified").replace(NORM)
    # Dedup per (paper, field, annotator); keep the worse rating
    err = err.sort_values("rating").drop_duplicates(["paper_id", "field_id", "annotator"])
    n_err = len(err)

    # Pivot to field × failure_mode count matrix
    mat = (err.groupby(["field_id", "failure_mode"]).size()
              .unstack("failure_mode", fill_value=0))
    # Ensure column order
    for col in FAILURE_ORDER:
        if col not in mat.columns:
            mat[col] = 0
    mat = mat[FAILURE_ORDER]
    # Sort fields by total error count descending. With imshow default
    # origin='upper', row 0 is the TOP, so we want row 0 = highest total.
    mat["__total"] = mat.sum(axis=1)
    mat = mat.sort_values("__total", ascending=False)
    totals = mat.pop("__total")

    n_fields = len(mat)
    incomplete_share = mat["Incomplete"].sum() / n_err

    # ── Layout ────────────────────────────────────────────────────
    # Saved at NeurIPS \linewidth (5.5"); included with width=\linewidth at 1:1.
    fig, ax = plt.subplots(figsize=(5.5, 5.5), dpi=300)

    # Heatmap — Blues sequential gives a clean dark/light split for text
    # contrast: white-on-dark above the threshold, dark-on-light below.
    cmap = plt.get_cmap("Blues").copy()
    vmax = mat.values.max()
    im = ax.imshow(mat.values, cmap=cmap, aspect="auto",
                   vmin=0, vmax=vmax, interpolation="nearest")

    # Cell counts as text. Threshold tuned so mid-range cells stay readable.
    threshold = vmax * 0.45
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            v = mat.values[i, j]
            if v == 0:
                continue
            color = "white" if v > threshold else "#1F2937"
            weight = "bold" if v >= 40 else "normal"
            ax.text(j, i, f"{v}", ha="center", va="center",
                    fontsize=5.5, color=color, fontweight=weight)

    # Tick labels
    ax.set_xticks(range(len(FAILURE_ORDER)))
    ax.set_xticklabels(FAILURE_ORDER, fontsize=6.5, rotation=30,
                       ha="right", rotation_mode="anchor")
    ax.set_yticks(range(n_fields))
    ax.set_yticklabels([LABEL_FIX[f] for f in mat.index], fontsize=6.5)
    ax.tick_params(axis="both", length=0)

    # Right-side total column (separate from heatmap to avoid colormap mix).
    # Header sits ABOVE row 0 in axes coords (y = -0.7).
    total_x = len(FAILURE_ORDER) + 0.6
    for i, val in enumerate(totals):
        ax.text(total_x, i, f"{val}",
                fontsize=6.5, fontweight="bold",
                ha="left", va="center", color="#1F2937")
    ax.text(total_x, -0.7, "total",
            fontsize=7, fontweight="bold",
            ha="left", va="center", color="#1F2937", style="italic")

    # Outline the headline cells
    callouts = [
        ("sc:publisher",                   "Wrong Section"),
        ("rai:dataAnnotationAnalysis",     "Incomplete"),
        ("rai:dataPreprocessingProtocol",  "Incomplete"),
    ]
    for field, fm in callouts:
        if field not in mat.index:
            continue
        i = list(mat.index).index(field)
        j = FAILURE_ORDER.index(fm)
        ax.add_patch(mpatches.Rectangle(
            (j - 0.5, i - 0.5), 1, 1,
            fill=False, edgecolor="#DC2626", linewidth=1.6,
        ))

    # Adjust x-axis right limit to expose the totals column
    ax.set_xlim(-0.5, len(FAILURE_ORDER) + 1.6)

    # No spines
    for s in ("top", "right", "left", "bottom"):
        ax.spines[s].set_visible(False)

    # Colorbar on the right
    cax = fig.add_axes([0.93, 0.18, 0.018, 0.45])
    cb = fig.colorbar(im, cax=cax)
    cb.set_label("error cells per (field, mode)", fontsize=7)
    cb.ax.tick_params(labelsize=6.5)

    fig.suptitle(
        f"Incomplete extraction dominates "
        f"({incomplete_share:.0%} of {n_err:,} error cells)",
        fontsize=10, fontweight="bold", y=0.985, x=0.04, ha="left",
    )

    plt.subplots_adjust(top=0.93, bottom=0.13, left=0.30, right=0.92)

    out_png = OUT_DIR / f"fig_failure_modes_iter{iteration}.png"
    out_pdf = OUT_DIR / f"fig_failure_modes_iter{iteration}.pdf"
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
