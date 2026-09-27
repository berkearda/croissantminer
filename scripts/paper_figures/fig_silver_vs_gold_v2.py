"""Appendix figure — silver corpus tracks gold corpus on field-level fill rates.

Replaces the legacy fig_silver_comparison and lives in the appendix between
the Per-Field Results and Annotator Demographics sections.

Inputs:
  data/analysis/coverage.parquet        18,060 rows; gold + silver populated
                                        flags after the locked null rule.

Headline numbers reproduced from this file:
  per-field fill-rate Pearson r (gold vs silver) = 0.846  (n = 30 fields)
  per-field fill-rate Spearman rho               = 0.809
  largest gold-vs-silver gaps:
    isLiveDataset          gold 100.0%, silver  7.8%   (gap +92.2pp)
    citeAs                 gold  99.0%, silver 61.0%   (gap +38.0pp)
    rai:dataReleaseMaintenancePlan  gap +20.7pp

Panels:
  (a) Per-field fill-rate scatter, gold vs silver, with the y = x diagonal
      and the Pearson correlation in the legend.
  (b) Per-field fill rate side-by-side, sorted by gold rate descending; the
      reader can locate any field on the scatter via this panel.

Outputs:
  results/figures/fig_silver_vs_gold.{pdf,png}
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.paper_figures.style import (  # noqa: E402
    COLORS, DOUBLE_COL, save_fig, setup_style,
)


COVERAGE_FP = ROOT / "data" / "analysis" / "coverage.parquet"

GOLD_COLOUR = COLORS["claude"]
SILVER_COLOUR = COLORS["gpt"]


def load_rates() -> pd.DataFrame:
    cov = pd.read_parquet(COVERAGE_FP)
    by = (
        cov.groupby(["field_id", "split"])["populated"]
        .mean()
        .unstack("split")
    )
    by["group"] = cov.groupby("field_id")["field_group"].first()
    by["gap"] = by["gold"] - by["silver"]
    return by.reset_index()


def panel_a(ax, rates: pd.DataFrame) -> None:
    g = rates["gold"].values * 100
    s = rates["silver"].values * 100
    r, _ = pearsonr(g, s)
    rho, _ = spearmanr(g, s)

    # Colour by field group so the reader can see whether discordance
    # is core- or RAI-concentrated.
    core_mask = rates["group"] == "core"
    rai_mask = ~core_mask
    ax.scatter(g[core_mask], s[core_mask], color=GOLD_COLOUR, s=40,
               edgecolor="white", linewidth=0.5, label="core field", zorder=3)
    ax.scatter(g[rai_mask], s[rai_mask], color=COLORS["purple"], s=40,
               edgecolor="white", linewidth=0.5, label="RAI field", zorder=3)
    ax.plot([0, 100], [0, 100], color="#888", linestyle="--",
            linewidth=0.6, zorder=1, label="$y = x$")

    # Annotate the three largest discordances. Use generous, non-colliding
    # offsets — labels go to fixed anchor positions in the empty quadrants
    # (upper-left and lower-right of the y = x diagonal).
    rates_sorted = rates.assign(abs_gap=rates["gap"].abs()).sort_values("abs_gap", ascending=False)
    top = rates_sorted.head(3).reset_index(drop=True)
    # Anchor positions in axes coords (chosen to lie in the off-diagonal whitespace).
    anchors_axes = [(0.55, 0.05), (0.05, 0.55), (0.05, 0.35)]
    for i, row in top.iterrows():
        ax.annotate(row["field_id"],
                    xy=(row["gold"] * 100, row["silver"] * 100),
                    xytext=anchors_axes[i], textcoords="axes fraction",
                    fontsize=6.5, color="#444", ha="left", va="center",
                    arrowprops=dict(arrowstyle="-", color="#aaa", linewidth=0.4,
                                    shrinkA=0, shrinkB=2))

    ax.set_xlim(-2, 105)
    ax.set_ylim(-2, 105)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("Gold fill rate (%)", fontsize=9)
    ax.set_ylabel("Silver fill rate (%)", fontsize=9)
    ax.set_title(f"(a) Gold vs. silver fill rate per field\n"
                 f"(Pearson $r$ = {r:.2f}, Spearman $\\rho$ = {rho:.2f}, $n$ = 30)",
                 fontsize=10, loc="left")
    ax.legend(loc="upper left", fontsize=8, frameon=False)


def panel_b(ax, rates: pd.DataFrame) -> None:
    df = rates.sort_values("gold", ascending=True)
    n = len(df)
    y = np.arange(n)
    bar_h = 0.4

    ax.barh(y - bar_h / 2, df["gold"] * 100, height=bar_h,
            color=GOLD_COLOUR, edgecolor="white", linewidth=0.4, label="gold")
    ax.barh(y + bar_h / 2, df["silver"] * 100, height=bar_h,
            color=SILVER_COLOUR, edgecolor="white", linewidth=0.4, label="silver")

    ax.set_yticks(y)
    ax.set_yticklabels(df["field_id"], fontsize=7)
    for tick, group in zip(ax.get_yticklabels(), df["group"]):
        tick.set_color("#222" if group == "core" else COLORS["purple"])
    ax.set_xlim(0, 100)
    ax.set_xlabel("Fill rate (%)", fontsize=9)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xticklabels(["0%", "25%", "50%", "75%", "100%"])
    ax.invert_yaxis()
    ax.set_title("(b) Side-by-side fill rate, sorted by gold rate",
                 fontsize=10, loc="left")
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0),
              fontsize=8, frameon=False)


def main() -> None:
    setup_style()
    rates = load_rates()
    print(f"loaded {len(rates)} fields")

    fig, axes = plt.subplots(1, 2, figsize=(DOUBLE_COL + 1.0, 8),
                             gridspec_kw={"width_ratios": [1.0, 1.0],
                                          "wspace": 0.55})
    panel_a(axes[0], rates)
    panel_b(axes[1], rates)
    fig.tight_layout()
    save_fig(fig, "fig_silver_vs_gold")


if __name__ == "__main__":
    main()
