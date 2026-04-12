"""
Global style settings for CroissantMiner NeurIPS paper figures.

Usage:
    from style import setup_style, COLORS, save_fig, SINGLE_COL, DOUBLE_COL
    setup_style()
"""

import matplotlib as mpl
import matplotlib.pyplot as plt
from pathlib import Path

# ── Dimensions ──
SINGLE_COL = 5.5   # inches
DOUBLE_COL = 11.0  # inches (full width, two-column layout)
DPI = 300

# ── Colorblind-friendly palette (Wong 2011 + NeurIPS conventions) ──
COLORS = {
    "claude":     "#4472C4",  # Blue
    "gpt":        "#ED7D31",  # Orange
    "hf":         "#A5A5A5",  # Gray
    "highlight":  "#E15759",  # Red accent
    "green":      "#59A14F",  # Green
    "purple":     "#B07AA1",  # Purple
    "teal":       "#76B7B2",  # Teal
    "gold":       "#F28E2B",  # Gold
    "pink":       "#FF9DA7",  # Pink
    "brown":      "#9C755F",  # Brown
}

# Ordered palette for bar charts etc.
PALETTE = [
    COLORS["claude"], COLORS["gpt"], COLORS["hf"],
    COLORS["green"], COLORS["purple"], COLORS["teal"],
    COLORS["gold"], COLORS["pink"], COLORS["brown"],
    COLORS["highlight"],
]

# Error type colors (consistent across figures)
ERROR_COLORS = {
    "Incomplete":           "#4472C4",
    "Absent in Source":     "#A5A5A5",
    "ABSENT_IN_SOURCE":     "#A5A5A5",
    "Hallucination":        "#E15759",
    "HALLUCINATION":        "#E15759",
    "INCOMPLETE":           "#4472C4",
    "Granularity Mismatch": "#F28E2B",
    "GRANULARITY_MISMATCH": "#F28E2B",
    "Wrong Section":        "#B07AA1",
    "WRONG_SECTION":        "#B07AA1",
    "Format Error":         "#76B7B2",
    "FORMAT_ERROR":         "#76B7B2",
}

# Method display names and colors
METHODS = {
    "Claude Sonnet 4.5":  {"color": COLORS["claude"], "marker": "o", "label": "Claude Sonnet 4.5"},
    "GPT-4o-mini":        {"color": COLORS["gpt"],    "marker": "s", "label": "GPT-4o-mini"},
    "HF Auto-Croissant":  {"color": COLORS["hf"],     "marker": "^", "label": "HF Auto-Croissant"},
}

FIGURE_DIR = Path(__file__).parent.parent.parent / "results" / "figures"


def setup_style():
    """Apply NeurIPS-style rcParams."""
    mpl.rcParams.update({
        # Font
        "font.family": "serif",
        "font.serif": ["Times New Roman", "DejaVu Serif", "Times"],
        "font.size": 10,
        "mathtext.fontset": "stix",
        # Axes
        "axes.labelsize": 10,
        "axes.titlesize": 11,
        "axes.titleweight": "bold",
        "axes.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        # Ticks
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "xtick.major.width": 0.8,
        "ytick.major.width": 0.8,
        # Legend
        "legend.fontsize": 9,
        "legend.frameon": True,
        "legend.framealpha": 0.9,
        "legend.edgecolor": "0.8",
        # Figure
        "figure.dpi": 150,
        "savefig.dpi": DPI,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.05,
        # Grid
        "axes.grid": False,
        "grid.alpha": 0.3,
    })


def save_fig(fig, name: str):
    """Save figure as PDF + PNG to results/figures/."""
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURE_DIR / f"{name}.pdf")
    fig.savefig(FIGURE_DIR / f"{name}.png")
    print(f"  Saved: {name}.pdf, {name}.png")
    plt.close(fig)
