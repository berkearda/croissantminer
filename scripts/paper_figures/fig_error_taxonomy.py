#!/usr/bin/env python3
"""
Figure 6: Error taxonomy analysis.
Stacked bar chart: error types per field category.
Data source: results/error_taxonomy/error_taxonomy.json
"""

import json
import sys
from pathlib import Path
from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from style import setup_style, save_fig, ERROR_COLORS, COLORS, SINGLE_COL

ROOT = Path(__file__).parent.parent.parent
ERROR_PATH = ROOT / "results" / "error_taxonomy" / "error_taxonomy.json"

# Display names for error types
ERROR_DISPLAY = {
    "INCOMPLETE": "Incomplete",
    "ABSENT_IN_SOURCE": "Absent in Source",
    "HALLUCINATION": "Hallucination",
    "GRANULARITY_MISMATCH": "Granularity",
    "WRONG_SECTION": "Wrong Section",
    "FORMAT_ERROR": "Format Error",
}

ERROR_ORDER = ["INCOMPLETE", "ABSENT_IN_SOURCE", "HALLUCINATION",
               "GRANULARITY_MISMATCH", "WRONG_SECTION", "FORMAT_ERROR"]


def main():
    setup_style()

    with open(ERROR_PATH) as f:
        data = json.load(f)

    errors = data["errors"]
    overall = data["error_distribution"]

    # Group errors by field category
    cat_errors = defaultdict(lambda: defaultdict(int))
    for err in errors:
        cat = err["field_category"]
        etype = err["error_type"]
        cat_errors[cat][etype] += 1

    categories = ["constrained", "short_text", "rai"]
    cat_labels = ["Constrained\n(EM)", "Short-text\n(F1)", "RAI\n(Judge)"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(SINGLE_COL * 2, 3.2),
                                    gridspec_kw={"width_ratios": [1.2, 1]})

    # ── Left: Stacked bar per category ──
    x = np.arange(len(categories))
    width = 0.5
    bottom = np.zeros(len(categories))

    for etype in ERROR_ORDER:
        display = ERROR_DISPLAY[etype]
        vals = [cat_errors[cat].get(etype, 0) for cat in categories]
        color = ERROR_COLORS.get(etype, "#999999")
        ax1.bar(x, vals, width, bottom=bottom, label=display, color=color,
                edgecolor="white", linewidth=0.5)
        # Add count labels inside bars (only if > 2)
        for i, v in enumerate(vals):
            if v > 2:
                ax1.text(i, bottom[i] + v / 2, str(v), ha="center", va="center",
                         fontsize=7, fontweight="bold", color="white")
        bottom += vals

    ax1.set_xticks(x)
    ax1.set_xticklabels(cat_labels, fontsize=9)
    ax1.set_ylabel("Number of Errors")
    ax1.set_title("Error Types by Field Category")
    ax1.legend(fontsize=7.5, loc="upper left", ncol=1)

    # ── Right: Overall distribution (horizontal bar) ──
    sorted_errors = [(ERROR_DISPLAY[e], overall.get(e, 0)) for e in ERROR_ORDER if overall.get(e, 0) > 0]
    labels = [l for l, _ in sorted_errors]
    counts = [c for _, c in sorted_errors]
    colors = [ERROR_COLORS.get(e, "#999999") for e in ERROR_ORDER if overall.get(e, 0) > 0]

    bars = ax2.barh(range(len(labels)), counts, color=colors, edgecolor="white", linewidth=0.5)
    ax2.set_yticks(range(len(labels)))
    ax2.set_yticklabels(labels)
    ax2.set_xlabel("Count")
    ax2.set_title("Overall Distribution (n=92)")
    ax2.invert_yaxis()

    total = sum(counts)
    for bar, count in zip(bars, counts):
        pct = count / total * 100
        ax2.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2,
                 f"{count} ({pct:.0f}%)", va="center", fontsize=8)

    fig.tight_layout()
    save_fig(fig, "fig6_error_taxonomy")


if __name__ == "__main__":
    main()
