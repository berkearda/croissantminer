#!/usr/bin/env python3
"""Figure 3 iteration 3 — FINAL. Slightly bumped fonts to survive 0.7x downscale."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

ROOT = Path("croissantminer")
IAA = ROOT / "data" / "annotations" / "iaa.parquet"
OUT_DIR = Path("/tmp/fig3_iter")
OUT_DIR.mkdir(parents=True, exist_ok=True)


COLORS = {
    "core": "#0072B2",   # Okabe-Ito blue
    "rai":  "#EE7733",   # Tol bright palette orange (clearly orange, colorblind-safe)
}

LABEL_FIX = {
    "sc:name": "name", "sc:description": "description", "sc:url": "url",
    "sc:license": "license", "sc:creator": "creator", "sc:publisher": "publisher",
    "sc:datePublished": "datePublished", "sc:inLanguage": "inLanguage",
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


def _field_group(field_id: str) -> str:
    return "core" if field_id.startswith(("sc:", "cr:")) else "rai"


def render(iteration: int, suffix: str = "") -> Path:
    iaa = pd.read_parquet(IAA)

    iaa["field_group"] = iaa["field_id"].map(_field_group)
    iaa = iaa.sort_values("gwet_ac1", ascending=True).reset_index(drop=True)
    pcts = iaa["gwet_ac1"].to_numpy()
    err_lo = np.clip(pcts - iaa["gwet_ac1_ci_low"].to_numpy(), 0, None)
    err_hi = np.clip(iaa["gwet_ac1_ci_high"].to_numpy() - pcts, 0, None)

    # Final size: 5.4 x 5.2 inches — within 5.0–5.5 height target
    fig, ax_b = plt.subplots(figsize=(5.4, 5.2), dpi=300)
    plt.subplots_adjust(left=0.30, right=0.98, top=0.95, bottom=0.10)

    y_pos = np.arange(len(iaa))
    bar_colors = [COLORS[g] for g in iaa["field_group"]]
    ax_b.barh(
        y_pos, pcts, color=bar_colors, edgecolor="black", linewidth=0.35,
        height=0.76,
        xerr=[err_lo, err_hi],
        error_kw=dict(ecolor="#333333", elinewidth=0.7, capsize=2.0, capthick=0.7),
    )

    ax_b.set_yticks(list(y_pos))
    ax_b.set_yticklabels([LABEL_FIX[f] for f in iaa["field_id"]], fontsize=7.5)
    ax_b.tick_params(axis="y", length=0)
    ax_b.set_ylim(-0.7, len(iaa) - 0.05)

    ax_b.set_xlim(-0.15, 1.18)
    ax_b.set_xlabel("Gwet AC1 (95% CI; 1.0 = perfect agreement)", fontsize=8.5)
    ax_b.set_xticks([0.0, 0.25, 0.5, 0.75, 1.0])
    ax_b.set_xticklabels(["0.00", "0.25", "0.50", "0.75", "1.00"], fontsize=7.5)

    # Landis-Koch landmark BANDS (alpha=0.40 — visible but not dominant)
    band_specs = [
        (-0.20, 0.40, "#FEE2E2", "below fair"),
        (0.40,  0.60, "#FEF3C7", "fair"),
        (0.60,  0.80, "#DBEAFE", "moderate"),
        (0.80,  1.05, "#D1FAE5", "substantial"),
    ]
    for lo, hi, color, _ in band_specs:
        ax_b.axvspan(lo, hi, color=color, alpha=0.40, zorder=0)
    for lo, hi, _, label in band_specs:
        if label == "below fair":
            continue
        ax_b.text((lo + hi) / 2, len(iaa) - 0.20, label,
                  fontsize=6.5, color="#374151", ha="center", va="bottom",
                  style="italic")

    # Direct AC1 labels at end of each bar (after CI cap)
    for i, (val, hi) in enumerate(zip(iaa["gwet_ac1"], iaa["gwet_ac1_ci_high"])):
        is_extreme = val < 0.1 or val > 0.92
        weight = "bold" if is_extreme else "normal"
        ax_b.text(max(hi, val) + 0.012, i, f"{val:.2f}",
                  va="center", ha="left", fontsize=7, fontweight=weight,
                  color="black")

    ax_b.spines["top"].set_visible(False)
    ax_b.spines["right"].set_visible(False)
    ax_b.spines["left"].set_visible(False)
    ax_b.set_axisbelow(True)

    legend_handles = [
        mpatches.Patch(facecolor=COLORS["core"], edgecolor="black",
                       linewidth=0.4, label="Core metadata"),
        mpatches.Patch(facecolor=COLORS["rai"], edgecolor="black",
                       linewidth=0.4, label="RAI metadata"),
    ]
    leg = ax_b.legend(
        handles=legend_handles, loc="lower right",
        frameon=True, framealpha=0.96, edgecolor="#BBBBBB",
        fontsize=7.5, bbox_to_anchor=(0.995, 0.012), title=None,
        handlelength=1.3, handleheight=1.0, borderpad=0.45, labelspacing=0.35,
    )
    leg.get_frame().set_linewidth(0.5)

    name = f"fig3_iter{iteration}{suffix}"
    out_png = OUT_DIR / f"{name}.png"
    out_pdf = OUT_DIR / f"{name}.pdf"
    fig.savefig(out_png, dpi=300, bbox_inches="tight", facecolor="white",
                pad_inches=0.05)
    fig.savefig(out_pdf, bbox_inches="tight", facecolor="white",
                pad_inches=0.05)
    plt.close(fig)
    return out_png


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--iter", type=int, default=3)
    args = p.parse_args()
    out = render(args.iter)
    print(f"wrote {out} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
