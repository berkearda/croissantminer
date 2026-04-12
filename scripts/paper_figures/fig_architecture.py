#!/usr/bin/env python3
"""
Figure: CroissantMiner pipeline architecture diagram (ref7/ref10 style).
Uses matplotlib patches for a clean, publication-quality diagram.
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

sys.path.insert(0, str(Path(__file__).parent))
from style import setup_style, save_fig, COLORS, DOUBLE_COL


def rounded_box(ax, xy, w, h, text, color, text_color="white",
                fontsize=9, fontweight="bold", alpha=0.95, subtext=None):
    """Draw a rounded rectangle with centered text."""
    x, y = xy
    box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.12",
                         facecolor=color, edgecolor="white", linewidth=1.5, alpha=alpha)
    ax.add_patch(box)
    if subtext:
        ax.text(x + w / 2, y + h * 0.62, text, ha="center", va="center",
                fontsize=fontsize, fontweight=fontweight, color=text_color)
        ax.text(x + w / 2, y + h * 0.28, subtext, ha="center", va="center",
                fontsize=fontsize - 2, color=text_color, alpha=0.85)
    else:
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
                fontsize=fontsize, fontweight=fontweight, color=text_color)


def arrow(ax, start, end, color="#555555"):
    """Draw an arrow between two points."""
    ax.annotate("", xy=end, xytext=start,
                arrowprops=dict(arrowstyle="-|>", color=color, lw=1.8,
                                connectionstyle="arc3,rad=0"))


def main():
    setup_style()
    fig, ax = plt.subplots(figsize=(DOUBLE_COL, 3.2))
    ax.set_xlim(-0.5, 11.5)
    ax.set_ylim(-0.3, 3.8)
    ax.axis("off")

    # Color scheme
    input_color = "#4472C4"      # Blue
    process_color = "#59A14F"    # Green
    output_color = "#ED7D31"     # Orange
    eval_color = "#B07AA1"       # Purple
    light_bg = "#F0F4F8"

    # ══════════════════════════════════════════════
    # Stage backgrounds
    # ══════════════════════════════════════════════
    bg_input = FancyBboxPatch((-0.3, -0.1), 3.1, 3.7, boxstyle="round,pad=0.15",
                              facecolor=input_color, alpha=0.06, edgecolor=input_color,
                              linewidth=1, linestyle="--")
    ax.add_patch(bg_input)
    ax.text(1.2, 3.45, "Input Sources", ha="center", fontsize=9, fontweight="bold",
            color=input_color, alpha=0.8)

    bg_proc = FancyBboxPatch((3.5, -0.1), 3.8, 3.7, boxstyle="round,pad=0.15",
                             facecolor=process_color, alpha=0.06, edgecolor=process_color,
                             linewidth=1, linestyle="--")
    ax.add_patch(bg_proc)
    ax.text(5.4, 3.45, "CroissantMiner", ha="center", fontsize=9, fontweight="bold",
            color=process_color, alpha=0.8)

    bg_out = FancyBboxPatch((8.0, -0.1), 3.3, 3.7, boxstyle="round,pad=0.15",
                            facecolor=output_color, alpha=0.06, edgecolor=output_color,
                            linewidth=1, linestyle="--")
    ax.add_patch(bg_out)
    ax.text(9.65, 3.45, "Output & Validation", ha="center", fontsize=9, fontweight="bold",
            color=output_color, alpha=0.8)

    # ══════════════════════════════════════════════
    # INPUT BOXES
    # ══════════════════════════════════════════════
    bw, bh = 2.4, 0.7

    rounded_box(ax, (0, 2.2), bw, bh, "Academic Paper", input_color,
                subtext="PDF  (full text)")
    rounded_box(ax, (0, 1.1), bw, bh, "Dataset Card", input_color,
                subtext="HuggingFace / GitHub", alpha=0.75)
    rounded_box(ax, (0, 0.0), bw, bh, "Croissant Schema", input_color,
                subtext="30 field definitions", alpha=0.6)

    # ══════════════════════════════════════════════
    # PROCESSING BOXES
    # ══════════════════════════════════════════════
    pw, ph = 3.2, 0.7

    rounded_box(ax, (3.8, 2.2), pw, ph, "Structured Prompt", process_color,
                subtext="10 General + 20 RAI fields")
    rounded_box(ax, (3.8, 1.1), pw, ph, "LLM API Call", process_color,
                subtext="Claude Sonnet 4.5  |  single pass")
    rounded_box(ax, (3.8, 0.0), pw, ph, "JSON Parser", process_color,
                subtext="schema validation + cleanup", alpha=0.75)

    # ══════════════════════════════════════════════
    # OUTPUT BOXES
    # ══════════════════════════════════════════════
    ow, oh = 2.8, 0.7

    rounded_box(ax, (8.3, 2.2), ow, oh, "Croissant JSON-LD", output_color,
                subtext="valid metadata file")
    rounded_box(ax, (8.3, 1.1), ow, oh, "Spec Validation", output_color,
                subtext="mlcroissant  (8/8 valid)", alpha=0.8)
    rounded_box(ax, (8.3, 0.0), ow, oh, "Human Evaluation", eval_color,
                subtext="23 annotators  ×  103 datasets")

    # ══════════════════════════════════════════════
    # ARROWS
    # ══════════════════════════════════════════════
    # Input → Processing
    arrow(ax, (2.4, 2.55), (3.8, 2.55))
    arrow(ax, (2.4, 1.45), (3.8, 1.45))
    arrow(ax, (2.4, 0.35), (3.8, 0.35))

    # Processing vertical flow
    arrow(ax, (5.4, 2.2), (5.4, 1.85))
    arrow(ax, (5.4, 1.1), (5.4, 0.75))

    # Processing → Output
    arrow(ax, (7.0, 0.35), (8.3, 0.65))
    arrow(ax, (7.0, 0.35), (8.3, 2.35))

    # Output vertical flow
    arrow(ax, (9.7, 2.2), (9.7, 1.85))
    arrow(ax, (9.7, 1.1), (9.7, 0.75))

    # ══════════════════════════════════════════════
    # Key stats annotation
    # ══════════════════════════════════════════════
    stats_text = "$0.13/dataset   •   42s avg   •   30 fields"
    ax.text(5.4, -0.2, stats_text, ha="center", va="top",
            fontsize=8, color="#666666", style="italic")

    fig.tight_layout(pad=0.3)
    save_fig(fig, "fig_architecture")


if __name__ == "__main__":
    main()
