#!/usr/bin/env python3
"""
Figure 4: Radar chart comparing models across field groups (ref8 style).
Axes: field groups (name, license, language, dates, citation, RAI fields...)
Lines: Claude, GPT-4o-mini, HF Auto-Croissant
"""

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from style import setup_style, save_fig, METHODS, SINGLE_COL

ROOT = Path(__file__).parent.parent.parent
EVAL_PATH = ROOT / "results" / "eval_16field" / "eval_16field_results.json"


# Group fields into meaningful categories for radar axes
FIELD_GROUPS = {
    "Name":          ["sc:name"],
    "Description":   ["sc:description"],
    "URL":           ["sc:url"],
    "License":       ["sc:license"],
    "Creator":       ["sc:creator"],
    "Publisher":     ["sc:publisher"],
    "Date":          ["sc:datePublished"],
    "Language":      ["sc:inLanguage"],
    "Citation":      ["cr:citeAs"],
    "Live?":         ["cr:isLiveDataset"],
    "Collection":    ["rai:dataCollection"],
    "Coll. Type":    ["rai:dataCollectionType"],
    "Annotation":    ["rai:dataAnnotationProtocol"],
    "Biases":        ["rai:dataBiases"],
    "PII":           ["rai:personalSensitiveInformation"],
}


def main():
    setup_style()

    with open(EVAL_PATH) as f:
        results = json.load(f)

    summaries = results["summaries"]

    # Compute per-group scores for each method
    group_labels = list(FIELD_GROUPS.keys())
    method_scores = {}

    for method_name, method_info in METHODS.items():
        if method_name not in summaries:
            continue
        per_field = summaries[method_name].get("per_field", {})
        scores = []
        for group, fields in FIELD_GROUPS.items():
            group_vals = [per_field.get(f, 0) for f in fields]
            scores.append(np.mean(group_vals) if group_vals else 0)
        method_scores[method_name] = scores

    # Radar chart
    N = len(group_labels)
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    angles += angles[:1]  # Close the polygon

    fig, ax = plt.subplots(figsize=(SINGLE_COL, SINGLE_COL), subplot_kw=dict(polar=True))

    for method_name, scores in method_scores.items():
        info = METHODS[method_name]
        values = scores + scores[:1]  # Close
        ax.plot(angles, values, "o-", color=info["color"], label=info["label"],
                linewidth=1.8, markersize=4, zorder=3)
        ax.fill(angles, values, alpha=0.08, color=info["color"])

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(group_labels, fontsize=7.5)
    ax.set_ylim(0, 1.05)
    ax.set_yticks([0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(["0.25", "0.50", "0.75", "1.00"], fontsize=7, color="gray")
    ax.set_rlabel_position(30)

    # Grid styling
    ax.spines["polar"].set_visible(False)
    ax.grid(True, color="gray", alpha=0.3, linewidth=0.5)

    ax.legend(loc="upper right", bbox_to_anchor=(1.35, 1.15), fontsize=8)

    fig.tight_layout()
    save_fig(fig, "fig4_radar_chart")


if __name__ == "__main__":
    main()
