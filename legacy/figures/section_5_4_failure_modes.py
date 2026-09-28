"""Figure 6 — failure-mode taxonomy across the LLM-extraction error budget.

Reproduces figures/section_5_4_failure_modes.{pdf,svg} from a clean clone.

Inputs (read-only):
  data/annotations/ratings.parquet   raw annotator ratings (10,302 rows)
  data/annotations/iaa.parquet       per-field Krippendorff alpha + Gwet AC1
                                     (used in the §5.4 publisher case study,
                                     not consumed by this script)

Pipeline applied to ratings.parquet:
  1. Canonicalise annotator names (NAME_CANONICAL) and dedup to one row per
     (annotator, paper, field) keeping the latest-phase rating; drops
     10,302 -> 9,595 rows.  Mirrors scripts/annotations/build_gold_iaa.py.
  2. Filter to rating in {2, 3} (Partially Correct or Not Correct):
     1,592 error rows (16.6% of dedup'd ratings).
  3. Normalise failure_mode column per the §5.4 brief:
     Hallucinated -> Hallucination, Wrong -> Wrong Section,
     Partially correct -> Other; null -> "Unspecified".

Output figure spans 30 fields x 7 failure-mode columns:

  Aggregate counts                      Top-3 highlighted cells (red boxes)
  ----------------                      -----------------------------------
  Incomplete            684 (43.0%)     sc:publisher x Wrong Section = 90
  Wrong Section         311 (19.5%)     rai:dataAnnotationAnalysis x
  Other                 173 (10.9%)         Incomplete = 71
  Hallucination         154  (9.7%)     rai:dataCollectionType x
  Granularity Mismatch  130  (8.2%)         Hallucination = 22
  Unspecified           102  (6.4%)
  Format Error           38  (2.4%)

Two-panel layout:
  (a) Per-field stacked horizontal bar (proportions), sorted by total error
      count descending.
  (b) Heatmap fields x failure modes with raw counts annotated; rightmost
      "Total" column gives per-field error counts (dark grey).

Run from repo root: python figures/section_5_4_failure_modes.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
ANNOT = ROOT / "data" / "annotations"
OUT_DIR = ROOT / "figures"

# ── Dedup + normalisation logic (mirrors scripts/annotations/build_gold_iaa.py) ──
NAME_CANONICAL = {
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

# Display order for failure modes — keeps the legend / stack consistent.
MODE_ORDER = [
    "Incomplete", "Wrong Section", "Hallucination",
    "Granularity Mismatch", "Format Error", "Other", "Unspecified",
]

# Tol's Bright palette (colourblind-safe; distinct on greyscale).
# https://personal.sron.nl/~pault/  (Bright qualitative scheme)
TOL_BRIGHT = {
    "Incomplete":           "#4477AA",  # blue
    "Wrong Section":        "#EE6677",  # red
    "Hallucination":        "#228833",  # green
    "Granularity Mismatch": "#CCBB44",  # yellow
    "Format Error":         "#66CCEE",  # cyan
    "Other":                "#AA3377",  # purple
    "Unspecified":          "#BBBBBB",  # grey
}


def load_errors() -> pd.DataFrame:
    df = pd.read_parquet(ANNOT / "ratings.parquet").copy()
    df["annotator"] = df["annotator"].map(lambda n: NAME_CANONICAL.get(n, n))
    df["_p"] = df["phase"].map(PHASE_PRIORITY).fillna(0)
    df = df.sort_values(["annotator", "paper_id", "field_id", "_p"])
    df = df.drop_duplicates(["annotator", "paper_id", "field_id"], keep="last")
    df = df.drop(columns=["_p"])

    err = df[df["rating"].isin([2, 3])].copy()
    err["fm"] = err["failure_mode"].replace(FAILURE_NORM).fillna("Unspecified")
    err.loc[err["fm"] == "`", "fm"] = "Unspecified"
    err.loc[err["fm"].str.startswith("Another link", na=False), "fm"] = "Other"
    return err


def build_matrix(err: pd.DataFrame) -> pd.DataFrame:
    """Return fields × MODE_ORDER count matrix, sorted by row total descending."""
    mat = err.pivot_table(
        index="field_id", columns="fm", values="paper_id",
        aggfunc="count", fill_value=0,
    )
    # Add any missing failure modes as zero columns; keep the canonical order.
    for m in MODE_ORDER:
        if m not in mat.columns:
            mat[m] = 0
    mat = mat[MODE_ORDER]
    mat["_total"] = mat.sum(axis=1)
    mat = mat.sort_values("_total", ascending=False)
    return mat


def panel_a_stacked_bar(ax, mat: pd.DataFrame) -> None:
    """Stacked horizontal bar — proportions per field."""
    fields = mat.index.tolist()
    totals = mat["_total"].values
    counts = mat[MODE_ORDER].values
    proportions = counts / totals[:, None]

    y = np.arange(len(fields))
    left = np.zeros(len(fields))
    for j, mode in enumerate(MODE_ORDER):
        widths = proportions[:, j]
        ax.barh(
            y, widths, left=left, height=0.75,
            color=TOL_BRIGHT[mode], edgecolor="white", linewidth=0.4,
            label=mode,
        )
        left += widths

    ax.set_yticks(y)
    ax.set_yticklabels(fields, fontsize=8)
    ax.invert_yaxis()  # most errors at top
    ax.set_xlim(0, 1.0)
    ax.set_xlabel("Share of errors", fontsize=9)
    ax.set_title("(a) Per-field stacked failure-mode breakdown", fontsize=10, loc="left")
    ax.tick_params(axis="x", labelsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_xticklabels(["0", "25%", "50%", "75%", "100%"])
    # Per-field totals are surfaced as the rightmost "Total" column on panel (b).


def panel_b_heatmap(ax, mat: pd.DataFrame) -> None:
    """Heatmap of raw counts, fields × failure modes, with a Total column."""
    counts = mat[MODE_ORDER].values
    totals = mat["_total"].values.astype(int).reshape(-1, 1)
    # Concatenate the totals as a visually-distinct rightmost column.
    # We render it on the same axes but with its own colour scale so the totals
    # don't blow out the per-mode colour mapping.
    n_modes = len(MODE_ORDER)

    im = ax.imshow(counts, aspect="auto", cmap="Blues", vmin=0,
                   extent=(-0.5, n_modes - 0.5, len(mat) - 0.5, -0.5))
    # Total column rendered as a separate imshow on top of the same axes
    ax.imshow(totals, aspect="auto", cmap="Greys", vmin=0,
              extent=(n_modes - 0.5, n_modes + 0.5, len(mat) - 0.5, -0.5))
    # Vertical separator between modes and totals
    ax.axvline(n_modes - 0.5, color="white", linewidth=2)

    xticks = list(range(n_modes)) + [n_modes]
    xlabels = list(MODE_ORDER) + ["Total"]
    ax.set_xticks(xticks)
    ax.set_xticklabels(xlabels, rotation=35, ha="right", fontsize=8)
    ax.set_yticks(np.arange(len(mat.index)))
    ax.set_yticklabels(mat.index, fontsize=8)
    ax.set_xlim(-0.5, n_modes + 0.5)
    ax.set_ylim(len(mat) - 0.5, -0.5)
    ax.set_title("(b) Field × failure-mode count heatmap", fontsize=10, loc="left")

    # Annotate raw counts; choose text colour for legibility against cell colour.
    vmax = counts.max() if counts.max() > 0 else 1
    for i in range(counts.shape[0]):
        for j in range(counts.shape[1]):
            v = int(counts[i, j])
            if v == 0:
                continue
            colour = "white" if v > 0.55 * vmax else "#222222"
            ax.text(j, i, str(v), ha="center", va="center", fontsize=7, color=colour)
    # Annotate Total column (own colour scale, so use a fixed dark text)
    tmax = totals.max() if totals.max() > 0 else 1
    for i, t in enumerate(totals.flatten()):
        colour = "white" if t > 0.55 * tmax else "#222222"
        ax.text(n_modes, i, str(int(t)), ha="center", va="center",
                fontsize=7, fontweight="bold", color=colour)

    # Highlight the top-3 cells called out in the brief
    top3 = [
        ("sc:publisher", "Wrong Section"),
        ("rai:dataAnnotationAnalysis", "Incomplete"),
        ("rai:dataCollectionType", "Hallucination"),
    ]
    field_to_y = {f: i for i, f in enumerate(mat.index)}
    mode_to_x = {m: j for j, m in enumerate(MODE_ORDER)}
    for f, m in top3:
        if f in field_to_y and m in mode_to_x:
            r = mpatches.Rectangle(
                (mode_to_x[m] - 0.5, field_to_y[f] - 0.5), 1, 1,
                fill=False, edgecolor="#EE6677", linewidth=1.6,
            )
            ax.add_patch(r)

    cbar = plt.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    cbar.ax.tick_params(labelsize=7)
    cbar.set_label("count", fontsize=8)


def main() -> None:
    err = load_errors()
    mat = build_matrix(err)

    n_errors = int(mat["_total"].sum())
    print(f"Building Figure 6 over {n_errors} error cells across {len(mat)} fields")

    fig, axes = plt.subplots(
        1, 2, figsize=(14.5, 9.5),
        gridspec_kw={"width_ratios": [1.0, 1.0], "wspace": 0.45},
    )
    panel_a_stacked_bar(axes[0], mat)
    panel_b_heatmap(axes[1], mat)

    # Single shared legend below the panels
    handles = [
        mpatches.Patch(color=TOL_BRIGHT[m], label=m) for m in MODE_ORDER
    ]
    fig.legend(
        handles=handles, loc="lower center", ncol=len(MODE_ORDER),
        bbox_to_anchor=(0.5, -0.005), frameon=False, fontsize=8,
    )
    fig.suptitle(
        f"Figure 6: Failure-mode taxonomy across {n_errors:,} error cells "
        "(ratings 2 or 3, post-dedup, post-normalisation)",
        fontsize=11, y=1.005,
    )
    fig.tight_layout(rect=[0, 0.03, 1, 0.99])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    svg_path = OUT_DIR / "section_5_4_failure_modes.svg"
    pdf_path = OUT_DIR / "section_5_4_failure_modes.pdf"
    fig.savefig(svg_path, bbox_inches="tight")
    fig.savefig(pdf_path, bbox_inches="tight")
    print(f"saved {svg_path.relative_to(ROOT)}")
    print(f"saved {pdf_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
