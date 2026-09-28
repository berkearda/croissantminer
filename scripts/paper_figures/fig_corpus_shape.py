#!/usr/bin/env python3
"""A4 — Appendix corpus characteristics (1x2).

After iter2 scored 65/100 (4 equal panels with no money panel and a
"Other = 53%" non-story), this rebuild keeps the two panels that carry
real claims and drops the rest. The two:

  (a) Publication year of the 500 silver papers — the recent-surge story.
      THIS IS THE MONEY PANEL: 312/500 papers from 2024–2026.
  (b) dataCollectionType prevalence (multi-label) — methodology diversity
      story: Software Collection (60%) + Manual / Web Scraping each ~33%.

Page-length and domain mix were dropped. Page length is now a single
number ("median 22 pages") that belongs in the caption. Domain mix has
"Other = 53%" which is a non-story for an appendix.

Output: docs/figure_iterations/A4/fig_corpus_shape_iter<N>.{png,pdf}
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
LENGTHS = ROOT / "data" / "paper_lengths.csv"
SILVER = ROOT / "data" / "analysis" / "silver_paper_metadata.parquet"
SPLIT = ROOT / "data" / "agentic" / "dev_test_split.json"
OUT_DIR = ROOT / "docs" / "figure_iterations" / "A4"
OUT_DIR.mkdir(parents=True, exist_ok=True)

ACCENT = "#0072B2"
RAI_TONE = "#D55E00"
MUTED = "#9CA3AF"


def render(iteration: int) -> Path:
    import json
    split = json.loads(SPLIT.read_text())
    locked_ids = set(split.get("dev", []) + split.get("test", []))
    lengths = pd.read_csv(LENGTHS)
    lengths = lengths[lengths["dataset_id"].isin(locked_ids)].copy()
    n_gold = len(lengths)
    median_pp = int(lengths["num_pages"].median())

    silver = pd.read_parquet(SILVER)
    n_silver = len(silver)

    # ── Panel (a) data: year ─────────────────────────────────────
    years = (silver["datePublished"].dropna().astype(str)
             .str.extract(r"(\d{4})")[0].astype(int))
    yc = years.value_counts().sort_index()
    # Cap year axis at a sensible range — drop pre-2015 outliers (n=5)
    yc = yc[yc.index >= 2015]
    n_in_2024_2026 = int(yc.loc[2024:2026].sum())

    # ── Panel (b) data: dataCollectionType ──────────────────────
    dct = (silver["dataCollectionType"].dropna()
           .str.split(", ").explode().value_counts())
    top_dct = dct.head(8).sort_values()

    # ── Layout ───────────────────────────────────────────────────
    # Saved at NeurIPS \linewidth (5.5"); included with width=\linewidth at 1:1.
    fig, (ax_a, ax_b) = plt.subplots(
        1, 2, figsize=(5.5, 3.4), dpi=300,
        gridspec_kw={"width_ratios": [1.0, 1.1]},
    )

    # ── (a) Publication year ────────────────────────────────────
    bars = ax_a.bar(yc.index, yc.values, color=ACCENT,
                    edgecolor="black", linewidth=0.4, width=0.78)
    # Highlight 2024–2026 with a translucent band; the band itself
    # carries the spatial reference, so a leader arrow is unnecessary.
    ax_a.axvspan(2023.5, 2026.5, color="#FEF3C7", alpha=0.6, zorder=0)
    ax_a.text(
        2016.5, yc.max() * 0.78,
        f"{n_in_2024_2026}/{n_silver} papers\nfrom 2024–2026",
        fontsize=7.5, fontweight="bold", color="#92400E",
        ha="left", va="center",
    )
    # 2026 caveat is in the caption text instead of the figure to keep
    # the panel uncluttered.
    ax_a.set_xlabel("Publication year", fontsize=7.5)
    ax_a.set_ylabel(f"Number of papers (n={n_silver})", fontsize=7.5)
    ax_a.tick_params(axis="both", labelsize=7)
    ax_a.set_xticks([2015, 2019, 2023, 2026])
    ax_a.set_title("(a) Publication year",
                   fontsize=8.5, loc="left", pad=4)

    # ── (b) dataCollectionType ──────────────────────────────────
    pcts_d = top_dct.values / n_silver * 100
    ax_b.barh(range(len(top_dct)), top_dct.values, color=RAI_TONE,
              edgecolor="black", linewidth=0.4, height=0.7)
    ax_b.set_yticks(range(len(top_dct)))
    ax_b.set_yticklabels(top_dct.index, fontsize=7)
    for i, (val, pct) in enumerate(zip(top_dct.values, pcts_d)):
        weight = "bold" if val >= 200 else "normal"
        ax_b.text(val + n_silver * 0.005, i, f"{val} ({pct:.0f}%)",
                  va="center", ha="left", fontsize=6.5, fontweight=weight)
    ax_b.set_xlabel("Papers tagged (multi-label)", fontsize=7.5)
    ax_b.tick_params(axis="x", labelsize=7)
    ax_b.set_xlim(0, n_silver * 0.85)
    ax_b.set_title("(b) dataCollectionType prevalence",
                   fontsize=8.5, loc="left", pad=4)

    for ax in (ax_a, ax_b):
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.set_axisbelow(True)
        ax.grid(True, axis="x" if ax is ax_b else "y",
                color="#EEEEEE", linewidth=0.5, zorder=0)

    fig.suptitle(
        f"Silver corpus: recent ({n_in_2024_2026}/{n_silver} in 2024–2026), software-heavy",
        fontsize=10, fontweight="bold", y=0.97, x=0.04, ha="left",
    )

    plt.subplots_adjust(top=0.83, bottom=0.18, left=0.07, right=0.96,
                        wspace=0.95)

    out_png = OUT_DIR / f"fig_corpus_shape_iter{iteration}.png"
    out_pdf = OUT_DIR / f"fig_corpus_shape_iter{iteration}.pdf"
    fig.savefig(out_png, dpi=300, bbox_inches="tight", facecolor="white")
    fig.savefig(out_pdf, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out_png


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--iter", type=int, default=1)
    args = p.parse_args()
    out = render(args.iter)
    print(f"wrote {out.relative_to(ROOT)} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
