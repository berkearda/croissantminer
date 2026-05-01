"""Appendix figure — corpus characteristics that didn't make the §3 main figures.

Two panels: paper length distribution (gold corpus) and the dataCollectionType
mix (gold vs silver). The two panels that the original Fig 1 / Fig 2 also
visualised but that don't carry information at this corpus mix---language
distribution (95% English; one-tall-bar) and publication-year distribution
(silver datePublished is 488/500 null)---are intentionally dropped per the
brief's "informative or out" rule.

Inputs:
  data/paper_lengths.csv                          103 rows; PDF page counts
                                                  for the gold corpus
  data/annotations/gold.parquet                   102 papers x 30 fields
                                                  (rai:dataCollectionType)
  data/analysis/silver_paper_metadata.parquet     500 rows; silver per-paper
                                                  metadata, including
                                                  dataCollectionType

Headline numbers reproduced from these files:
  PDF page counts (gold)         mean = 33.7, median = 22, range [5, 249]
  > 30 pages                                                = 33 / 103
  dataCollectionType "Software Collection" rank-1 in silver = 302 / 500
  dataCollectionType "Manual Human Curator" rank-1 in gold  = 65 / 102

Outputs:
  results/figures/fig_corpus_characteristics.{pdf,png}
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.paper_figures.style import (  # noqa: E402
    COLORS, DOUBLE_COL, save_fig, setup_style,
)

PAGE_FP = ROOT / "data" / "paper_lengths.csv"
GOLD_FP = ROOT / "data" / "annotations" / "gold.parquet"
SILVER_META_FP = ROOT / "data" / "analysis" / "silver_paper_metadata.parquet"

GOLD_COLOUR = COLORS["claude"]
SILVER_COLOUR = COLORS["gpt"]


def panel_a_page_lengths(ax) -> None:
    df = pd.read_csv(PAGE_FP)
    pages = df["num_pages"].dropna().astype(int)
    bins = [0, 10, 15, 20, 25, 30, 40, 50, 75, 100, 250]
    labels = ["1-10", "11-15", "16-20", "21-25", "26-30",
              "31-40", "41-50", "51-75", "76-100", "100+"]
    bucketed = pd.cut(pages, bins=bins, labels=labels, include_lowest=True)
    counts = bucketed.value_counts().reindex(labels, fill_value=0)

    x = np.arange(len(labels))
    ax.bar(x, counts.values, color=GOLD_COLOUR, edgecolor="white", linewidth=0.4)
    for xi, c in enumerate(counts.values):
        if c > 0:
            ax.text(xi, c + 0.5, str(int(c)), ha="center", fontsize=7, color="#333")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=8)
    ax.set_xlabel("PDF pages", fontsize=9)
    ax.set_ylabel("Papers", fontsize=9)
    ax.set_title(f"(a) Paper length distribution\n(gold corpus, n = {len(pages)}; "
                 f"median = {int(pages.median())}, mean = {pages.mean():.1f})",
                 fontsize=10, loc="left")
    # Annotate the median bin with a guide line
    median_val = int(pages.median())
    median_bin = pd.cut([median_val], bins=bins, labels=labels, include_lowest=True)[0]
    ax.axvline(labels.index(str(median_bin)), color="#888",
               linestyle=":", linewidth=0.6, zorder=0)


def panel_b_collection_type(ax) -> None:
    # Gold side
    gold = pd.read_parquet(GOLD_FP)
    gct = gold[gold["field_id"] == "rai:dataCollectionType"]["gold_value"].dropna()
    gold_counts = (
        gct.astype(str).str.split(",").explode().str.strip()
        .pipe(lambda s: s[s != ""])
        .value_counts()
    )

    # Silver side
    silver = pd.read_parquet(SILVER_META_FP)
    sct = silver["dataCollectionType"].dropna()
    silver_counts = (
        sct.astype(str).str.split(",").explode().str.strip()
        .pipe(lambda s: s[s != ""])
        .value_counts()
    )

    # Take the union of top-N
    top_n = 10
    union = list(dict.fromkeys(
        list(gold_counts.head(top_n).index) + list(silver_counts.head(top_n).index)
    ))
    df = pd.DataFrame({
        "gold": gold_counts.reindex(union, fill_value=0).values,
        "silver": silver_counts.reindex(union, fill_value=0).values,
    }, index=union)

    n_gold = 102  # gold papers
    n_silver = 500  # silver papers
    df["gold_pct"] = df["gold"] / n_gold * 100
    df["silver_pct"] = df["silver"] / n_silver * 100
    df = df.sort_values("silver_pct", ascending=True)

    y = np.arange(len(df))
    bar_h = 0.4
    ax.barh(y - bar_h / 2, df["gold_pct"], height=bar_h,
            color=GOLD_COLOUR, edgecolor="white", linewidth=0.4,
            label=f"gold (n = {n_gold})")
    ax.barh(y + bar_h / 2, df["silver_pct"], height=bar_h,
            color=SILVER_COLOUR, edgecolor="white", linewidth=0.4,
            label=f"silver (n = {n_silver})")

    ax.set_yticks(y)
    ax.set_yticklabels(df.index, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("Share of papers reporting (%)", fontsize=9)
    ax.set_xlim(0, max(df["gold_pct"].max(), df["silver_pct"].max()) * 1.15)
    ax.set_title("(b) rai:dataCollectionType mix\n"
                 "(multi-label; values may sum to > 100%)",
                 fontsize=10, loc="left")
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0),
              fontsize=8, frameon=False)


def main() -> None:
    setup_style()
    fig, axes = plt.subplots(1, 2, figsize=(DOUBLE_COL, 6),
                             gridspec_kw={"width_ratios": [1.0, 1.2],
                                          "wspace": 0.40})
    panel_a_page_lengths(axes[0])
    panel_b_collection_type(axes[1])
    fig.tight_layout()
    save_fig(fig, "fig_corpus_characteristics")


if __name__ == "__main__":
    main()
