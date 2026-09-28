#!/usr/bin/env python3
"""Figure 5 v2 — Failure-mode taxonomy, side-by-side Core vs RAI.

Two-panel horizontal stacked bar chart. Left panel: 10 sc:/cr: Core
fields, sorted by total error count desc. Right panel: 20 rai: fields,
same sort. Panels share the x-axis range and a single legend at the
bottom of the figure.

Story: errors concentrate on RAI fields (large RAI bars dominate),
while Core stays small except for sc:publisher.

Output: docs/figure_iterations/A5/fig_failure_modes_v2_iter<N>.{png,pdf}
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
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

FAILURE_ORDER = [
    "Incomplete", "Wrong Section", "Hallucination",
    "Granularity Mismatch", "Format Error", "Other", "Unspecified",
]

# Palette matched to the published reference (section_5_4_failure_modes.pdf):
# coral / blue / green / mustard / cyan / magenta / light gray.
PALETTE = {
    "Incomplete":           "#E45756",  # coral / pink-red
    "Wrong Section":        "#4C78A8",  # blue
    "Hallucination":        "#54A24B",  # green
    "Granularity Mismatch": "#DCB94A",  # mustard / gold
    "Format Error":         "#72B7DA",  # cyan / light blue
    "Other":                "#B279A2",  # magenta / purple
    "Unspecified":          "#BAB0AC",  # light gray
}

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

CORE_FIELDS = [
    "sc:name", "sc:description", "sc:url", "sc:license", "sc:creator",
    "sc:publisher", "sc:datePublished", "sc:inLanguage",
    "cr:citeAs", "cr:isLiveDataset",
]


def render(iteration: int, final: bool = False) -> Path:
    r = pd.read_parquet(RATINGS)
    err = r[r["rating"].isin([2, 3])].copy()
    err["failure_mode"] = err["failure_mode"].fillna("Unspecified").replace(NORM)
    # Dedup per (paper, field, annotator); keep the worse rating
    err = err.sort_values("rating").drop_duplicates(["paper_id", "field_id", "annotator"])

    mat = (err.groupby(["field_id", "failure_mode"]).size()
              .unstack("failure_mode", fill_value=0))
    for col in FAILURE_ORDER:
        if col not in mat.columns:
            mat[col] = 0
    mat = mat[FAILURE_ORDER]
    mat["__total"] = mat.sum(axis=1)

    core_mat = mat.loc[mat.index.isin(CORE_FIELDS)].sort_values("__total", ascending=False)
    rai_mat = mat.loc[mat.index.str.startswith("rai:")].sort_values("__total", ascending=False)
    core_totals = core_mat.pop("__total")
    rai_totals = rai_mat.pop("__total")

    n_core = len(core_mat)
    n_rai = len(rai_mat)

    # ── Layout ────────────────────────────────────────────────────
    # Two side-by-side panels. Use height_ratios proportional to row
    # counts so each row gets the same vertical pitch across panels.
    fig = plt.figure(figsize=(11.0, 5.2), dpi=300)
    gs = fig.add_gridspec(
        nrows=2, ncols=2,
        width_ratios=[1.0, 1.30],
        height_ratios=[n_core, n_rai - n_core],
        hspace=0.0, wspace=0.28,
    )
    # Core panel occupies top-left only (so its rows match RAI pitch);
    # RAI panel spans the full height of the right column.
    ax_core = fig.add_subplot(gs[0, 0])
    ax_rai = fig.add_subplot(gs[:, 1])
    # Hide the bottom-left cell
    ax_blank = fig.add_subplot(gs[1, 0])
    ax_blank.set_visible(False)

    bar_height = 0.78

    def draw_block(ax, mat_block, totals_block, attach_legend: bool):
        n = len(mat_block)
        y_positions = np.arange(n, dtype=float)
        left = np.zeros(n)
        for fm in FAILURE_ORDER:
            vals = mat_block[fm].values
            ax.barh(
                y_positions, vals, left=left, height=bar_height,
                color=PALETTE[fm], edgecolor="white", linewidth=0.4,
                label=fm if attach_legend else None,
            )
            left = left + vals
        # Totals on the right
        for y, total in zip(y_positions, totals_block):
            ax.text(total + 4.0, y, f"{int(total)}",
                    fontsize=6.8, fontweight="bold",
                    ha="left", va="center", color="#1F2937")
        return y_positions

    core_y = draw_block(ax_core, core_mat, core_totals, attach_legend=True)
    rai_y = draw_block(ax_rai, rai_mat, rai_totals, attach_legend=False)

    # ── Per-axis cosmetics ────────────────────────────────────────
    # Independent x-limits per panel: Core needs to fit publisher (~167);
    # RAI maxes out near 100 so a tighter 120 cap removes empty whitespace.
    core_xlim = core_totals.max() * 1.10 + 12
    rai_xlim = 120

    for ax, mat_block, y_pos, title, xlim, xtick_step in (
        (ax_core, core_mat, core_y, f"Core ({n_core})", core_xlim, 50),
        (ax_rai, rai_mat, rai_y, f"RAI ({n_rai})", rai_xlim, 30),
    ):
        ax.set_yticks(y_pos)
        ax.set_yticklabels([LABEL_FIX[f] for f in mat_block.index], fontsize=7.2)
        ax.tick_params(axis="y", length=0, pad=2)
        ax.set_xlim(0, xlim)
        ax.tick_params(axis="x", labelsize=7)
        ax.xaxis.set_major_locator(plt.MultipleLocator(xtick_step))
        ax.set_axisbelow(True)
        ax.grid(axis="x", color="#E5E7EB", linewidth=0.5, zorder=0)
        ax.invert_yaxis()
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
        ax.spines["bottom"].set_color("#9CA3AF")
        ax.spines["bottom"].set_linewidth(0.6)
        ax.set_title(title, fontsize=9.0, fontweight="bold",
                     color="#1F2937", loc="left", pad=4)

    # Pin Core panel rows to the top: set ylim to match a full-height
    # range so the bars sit flush with the title (with invert_yaxis,
    # ylim goes from n_core-0.5 (bottom) to -0.5 (top)).
    ax_core.set_ylim(n_core - 0.5, -0.5)
    ax_rai.set_ylim(n_rai - 0.5, -0.5)

    # X label only on the bottom-most axis of each column visually.
    ax_core.set_xlabel("Errors per field", fontsize=8)
    ax_rai.set_xlabel("Errors per field", fontsize=8)

    # ── Shared legend at bottom ───────────────────────────────────
    handles, labels = ax_core.get_legend_handles_labels()
    seen = set()
    uniq = []
    for h, l in zip(handles, labels):
        if l not in seen:
            uniq.append((h, l))
            seen.add(l)
    handles, labels = zip(*uniq)
    fig.legend(
        handles, labels,
        loc="lower center", bbox_to_anchor=(0.5, 0.0),
        ncol=7, fontsize=8.0, frameon=False,
        handlelength=1.2, handleheight=1.0, columnspacing=1.6,
        handletextpad=0.5,
    )

    fig.subplots_adjust(top=0.93, bottom=0.13, left=0.08, right=0.97)

    suffix = "FINAL" if final else f"iter{iteration}"
    out_png = OUT_DIR / f"fig_failure_modes_v2_{suffix}.png"
    out_pdf = OUT_DIR / f"fig_failure_modes_v2_{suffix}.pdf"
    fig.savefig(out_png, dpi=300, bbox_inches="tight", facecolor="white")
    fig.savefig(out_pdf, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out_png


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--iter", type=int, default=1)
    p.add_argument("--final", action="store_true")
    args = p.parse_args()
    out = render(args.iter, final=args.final)
    print(f"wrote {out.relative_to(ROOT)} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
