"""Figure (annotation results) — refreshed for §3.3.

Replaces the legacy fig3_annotation_results figure (which read raw
per-annotator spreadsheets) with one that derives every number from the
canonical post-dedup sources.

Inputs:
  data/annotations/ratings.parquet  9,595 deduplicated ratings across 22
                                    annotators (post canonicalize_and_dedup
                                    from scripts/annotations/build_gold_iaa.py)
  data/annotations/iaa.parquet      30-field Krippendorff alpha + Gwet AC1
                                    + raw pairwise agreement (1,000 boot)

Headline numbers reproduced from these files:
  total dedup'd ratings = 9,595   (annotators = 22, fields = 30, papers = 102)
  rating 1 (Correct)          = 8,003   (83.4%)
  rating 2 (Partially Correct) =   848   (  8.8%)
  rating 3 (Not Correct)       =   744   (  7.8%)
  failure_mode budget (rating in 2,3) = 1,592 cells, of which Incomplete = 684
  IAA Krippendorff alpha range = [-0.32, 0.66]; Gwet AC1 range = [-0.09, 0.96]

Layout:
  (a) Per-field rating composition, sorted by % Correct descending.
  (b) Failure-mode composition over the 1,592 error cells (single horiz bar).
  (c) Per-field Gwet AC1 with 95% CI bars (alpha is unstable on near-unanimous
      fields; AC1 is the readable headline metric).
  (d) Aggregate rating distribution and the gold-method distribution side by
      side, anchoring the §3.3 claim that the gold cells are well-validated.

Outputs:
  results/figures/fig_annotation_results.{pdf,png}
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.paper_figures.style import (  # noqa: E402
    COLORS, DOUBLE_COL, save_fig, setup_style,
)

ANNOT = ROOT / "data" / "annotations"
RATINGS_FP = ANNOT / "ratings.parquet"
IAA_FP = ANNOT / "iaa.parquet"
GOLD_FP = ANNOT / "gold.parquet"


# Canonical dedup logic (mirrors scripts/annotations/build_gold_iaa.py)
NAME_C = {
    "annotator": "A06", "A06": "A06",
    "annotator": "A09",
    "A09": "A09",
    "annotator": "A03",
    "annotator": "annotator",
    "annotator": "A02",
    "A02": "A02",
}
PHASE_PRIORITY = {
    "phase2": 1, "redistribution": 2, "round3": 3,
    "final_sweep_208": 4, "final_sweep_28": 4,
    "dataCollectionType_pass": 4, "orphan_topup": 5,
}
FAILURE_NORM = {
    "Hallucinated": "Hallucination",
    "Wrong": "Wrong Section",
    "Partially correct": "Other",
}
MODE_ORDER = ["Incomplete", "Wrong Section", "Hallucination",
              "Granularity Mismatch", "Format Error", "Other", "Unspecified"]
MODE_COLOURS = {
    "Incomplete":           COLORS["claude"],
    "Wrong Section":        COLORS["highlight"],
    "Hallucination":        COLORS["green"],
    "Granularity Mismatch": COLORS["gold"],
    "Format Error":         COLORS["teal"],
    "Other":                COLORS["purple"],
    "Unspecified":          "#BBBBBB",
}
RATING_COLOURS = {
    1: COLORS["claude"],   # Correct
    2: COLORS["gold"],     # Partially correct
    3: COLORS["highlight"],  # Not correct
}
RATING_LABEL = {1: "Correct", 2: "Partially Correct", 3: "Not Correct"}


def canon_dedup(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["annotator"] = df["annotator"].map(lambda n: NAME_C.get(n, n))
    df["_p"] = df["phase"].map(PHASE_PRIORITY).fillna(0)
    df = df.sort_values(["annotator", "paper_id", "field_id", "_p"])
    df = df.drop_duplicates(["annotator", "paper_id", "field_id"], keep="last")
    return df.drop(columns=["_p"])


def normalise_failure_mode(s: pd.Series) -> pd.Series:
    out = s.replace(FAILURE_NORM).fillna("Unspecified")
    out = out.where(out != "`", "Unspecified")
    out = out.where(~out.str.startswith("Another link", na=False), "Other")
    return out


def panel_a(ax, ratings: pd.DataFrame) -> None:
    """Per-field rating composition, sorted by % Correct descending."""
    pivot = (
        ratings.groupby(["field_id", "rating"]).size()
        .unstack("rating", fill_value=0)
    )
    for r in [1, 2, 3]:
        if r not in pivot.columns:
            pivot[r] = 0
    pivot = pivot[[1, 2, 3]]
    totals = pivot.sum(axis=1)
    pct = pivot.div(totals, axis=0) * 100
    pct = pct.sort_values(1, ascending=True)  # Correct% ascending → flip below

    y = np.arange(len(pct))
    left = np.zeros(len(pct))
    for r in [1, 2, 3]:
        ax.barh(y, pct[r].values, left=left, height=0.7,
                color=RATING_COLOURS[r], edgecolor="white", linewidth=0.3,
                label=RATING_LABEL[r])
        left = left + pct[r].values

    ax.set_yticks(y)
    ax.set_yticklabels(pct.index, fontsize=7)
    ax.set_xlim(0, 100)
    ax.set_xlabel("Share of ratings (%)", fontsize=9)
    ax.invert_yaxis()
    ax.set_title("(a) Per-field rating composition (sorted by % Correct)",
                 fontsize=10, loc="left")
    ax.legend(loc="lower right", fontsize=7, frameon=False, ncol=3,
              bbox_to_anchor=(1.0, -0.08))


def panel_b(ax, ratings: pd.DataFrame) -> None:
    """Failure-mode composition over the 1,592 error cells."""
    err = ratings[ratings["rating"].isin([2, 3])].copy()
    err["fm"] = normalise_failure_mode(err["failure_mode"])
    counts = err["fm"].value_counts().reindex(MODE_ORDER, fill_value=0)
    total = int(counts.sum())

    left = 0
    for mode in MODE_ORDER:
        n = int(counts[mode])
        if n == 0:
            continue
        ax.barh([0], [n], left=left, height=0.6,
                color=MODE_COLOURS[mode], edgecolor="white", linewidth=0.5,
                label=f"{mode} ({n})")
        # In-bar count if there's room
        if n / total > 0.04:
            ax.text(left + n / 2, 0, str(n), ha="center", va="center",
                    fontsize=7, color="white" if mode in {"Incomplete", "Wrong Section",
                                                           "Hallucination", "Other"} else "#222")
        left += n

    ax.set_yticks([])
    ax.set_xlim(0, total)
    ax.set_xlabel(f"Error cells (n = {total:,})", fontsize=9)
    ax.spines[["left"]].set_visible(False)
    ax.set_title("(b) Failure-mode composition (rating $\\in \\{2, 3\\}$)",
                 fontsize=10, loc="left")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.45),
              fontsize=7, ncol=4, frameon=False)


def panel_c(ax, iaa: pd.DataFrame) -> None:
    """Per-field Gwet AC1 with 95% CI."""
    df = iaa.sort_values("gwet_ac1", ascending=True).copy()
    y = np.arange(len(df))
    ac1 = df["gwet_ac1"].values
    lo = df["gwet_ac1_ci_low"].values
    hi = df["gwet_ac1_ci_high"].values
    err = np.array([ac1 - lo, hi - ac1])

    # Color by sign of AC1 (negative = serious disagreement)
    colours = [COLORS["highlight"] if v < 0 else COLORS["claude"] for v in ac1]
    ax.barh(y, ac1, height=0.7, color=colours, edgecolor="white", linewidth=0.3)
    ax.errorbar(ac1, y, xerr=err, fmt="none",
                ecolor="#444444", elinewidth=0.6, capsize=2)
    ax.axvline(0, color="#888", linewidth=0.6)

    ax.set_yticks(y)
    ax.set_yticklabels(df["field_id"], fontsize=7)
    ax.set_xlabel("Gwet's AC$_1$ (95% CI)", fontsize=9)
    ax.set_xlim(-0.4, 1.0)
    ax.invert_yaxis()
    ax.set_title("(c) Per-field inter-annotator agreement (Gwet AC$_1$)",
                 fontsize=10, loc="left")


def panel_d(ax, ratings: pd.DataFrame) -> None:
    """Aggregate rating dist + gold-method dist, side-by-side bars."""
    # Aggregate rating dist
    counts = ratings["rating"].value_counts().sort_index()
    total = int(counts.sum())
    rating_pct = (counts / total * 100).reindex([1, 2, 3])

    # Gold-method dist (post-adjudication)
    gold = pd.read_parquet(GOLD_FP)
    method_dist = gold["gold_method"].value_counts()
    method_order = ["unanimous_3of3", "majority_2of3", "unanimous_4of4",
                    "majority_3of4", "adjudicated"]
    method_dist = method_dist.reindex(method_order, fill_value=0)

    # Two stacked-style bars on the same axes
    bar_w = 0.35
    x = np.array([0, 1])
    ax.bar(x[0] - bar_w / 2 + np.arange(3) * bar_w / 3 - bar_w / 3,
           rating_pct.values, width=bar_w / 3 - 0.01,
           color=[RATING_COLOURS[r] for r in [1, 2, 3]],
           edgecolor="white", linewidth=0.4)
    for i, (r, v) in enumerate(rating_pct.items()):
        ax.text(x[0] + (i - 1) * bar_w / 3, v + 1.5, f"{v:.1f}%",
                ha="center", fontsize=7)

    method_pct = method_dist / method_dist.sum() * 100
    method_palette = [COLORS["claude"], COLORS["green"], COLORS["teal"],
                      COLORS["gold"], COLORS["highlight"]]
    for i, (m, v) in enumerate(method_pct.items()):
        ax.bar(x[1] + (i - 2) * bar_w / 5, v, width=bar_w / 5 - 0.01,
               color=method_palette[i], edgecolor="white", linewidth=0.4,
               label=m)
    for i, (m, v) in enumerate(method_pct.items()):
        ax.text(x[1] + (i - 2) * bar_w / 5, v + 1.5, f"{v:.0f}%",
                ha="center", fontsize=7)

    ax.set_xticks(x)
    ax.set_xticklabels([f"Ratings\n(n = {total:,})",
                        f"Gold method\n(n = {int(method_dist.sum()):,} cells)"],
                       fontsize=8)
    ax.set_ylabel("Share (%)", fontsize=9)
    ax.set_ylim(0, 105)
    ax.set_title("(d) Aggregate ratings and gold-consensus method",
                 fontsize=10, loc="left")
    # Legend for the gold-method bars only (the rating bar is self-explanatory via colour)
    ax.legend(fontsize=7, loc="upper center", bbox_to_anchor=(0.7, -0.08),
              ncol=2, frameon=False)


def main() -> None:
    setup_style()
    ratings = canon_dedup(pd.read_parquet(RATINGS_FP))
    iaa = pd.read_parquet(IAA_FP)
    print(f"ratings: {len(ratings):,} | annotators: {ratings['annotator'].nunique()} | "
          f"correct%: {100*(ratings['rating']==1).mean():.1f}")

    fig, axes = plt.subplots(2, 2, figsize=(DOUBLE_COL, 10),
                             gridspec_kw={"height_ratios": [1.4, 1.0],
                                          "hspace": 0.6, "wspace": 0.35})
    panel_a(axes[0, 0], ratings)
    panel_c(axes[0, 1], iaa)
    panel_b(axes[1, 0], ratings)
    panel_d(axes[1, 1], ratings)

    fig.suptitle(
        f"Annotation pipeline output — 22 annotators, {len(ratings):,} deduplicated ratings, "
        f"{100*(ratings['rating']==1).mean():.1f}% rated Correct",
        fontsize=11, y=1.0,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.98])
    save_fig(fig, "fig_annotation_results")


if __name__ == "__main__":
    main()
