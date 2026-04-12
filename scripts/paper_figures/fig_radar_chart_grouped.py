#!/usr/bin/env python3
"""
Figure 4b: Radar chart with field CATEGORY grouping (ref8 style).
7 category axes instead of 15 individual fields.
Saves alongside the original as fig4b.
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

# Grouped field categories
FIELD_CATEGORIES = {
    "Identity\n(name, url, citeAs)": ["sc:name", "sc:url", "cr:citeAs"],
    "Metadata\n(license, date, pub,\nlang, isLive)": ["sc:license", "sc:datePublished", "sc:publisher", "sc:inLanguage", "cr:isLiveDataset"],
    "Short-text\n(creator, desc)": ["sc:creator", "sc:description"],
    "Collection\n(method, type,\nmissing)": ["rai:dataCollection", "rai:dataCollectionType", "rai:dataCollectionMissingData"],
    "Annotation\n(protocol, biases)": ["rai:dataAnnotationProtocol", "rai:dataBiases"],
    "PII": ["rai:personalSensitiveInformation"],
}


def main():
    setup_style()

    with open(EVAL_PATH) as f:
        results = json.load(f)

    summaries = results["summaries"]
    group_labels = list(FIELD_CATEGORIES.keys())
    method_scores = {}

    for method_name, method_info in METHODS.items():
        if method_name not in summaries:
            continue
        per_field = summaries[method_name].get("per_field", {})
        scores = []
        for group, fields in FIELD_CATEGORIES.items():
            vals = [per_field.get(f, 0) for f in fields]
            scores.append(np.mean(vals) if vals else 0)
        method_scores[method_name] = scores

    N = len(group_labels)
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(SINGLE_COL, SINGLE_COL), subplot_kw=dict(polar=True))

    for method_name, scores in method_scores.items():
        info = METHODS[method_name]
        values = scores + scores[:1]
        ax.plot(angles, values, "o-", color=info["color"], label=info["label"],
                linewidth=2.0, markersize=5, zorder=3)
        ax.fill(angles, values, alpha=0.10, color=info["color"])

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(group_labels, fontsize=7, linespacing=1.1)
    ax.set_ylim(0, 1.05)
    ax.set_yticks([0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(["", "0.50", "", "1.00"], fontsize=7, color="gray")
    ax.set_rlabel_position(60)

    ax.spines["polar"].set_visible(False)
    ax.grid(True, color="gray", alpha=0.3, linewidth=0.5)
    ax.legend(loc="upper right", bbox_to_anchor=(1.4, 1.15), fontsize=8)

    fig.tight_layout()
    save_fig(fig, "fig4b_radar_chart_grouped")


if __name__ == "__main__":
    main()
