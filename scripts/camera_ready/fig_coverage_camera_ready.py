"""Figures 7 and 8 of the paper (appendix F), rebuilt on the camera-ready coverage.

Input: results/camera_ready/coverage_camera_ready.parquet (coverage_camera_ready.py:
one "missing" rule, the scorer's, for gold and silver; current human gold).
The code that drew the printed May versions is not in the repo; this script
matches their layout (colours, bars with Wilson 95% CIs, direct labels, legend,
shaded under-diagonal area) and adds nothing new.

  fig1_field_fill_rates.pdf  per-field documentation rate over all 602 papers
  fig_silver_vs_gold.pdf     per-field rate, gold (102) vs silver (500)

Writes to results/camera_ready/figures/; with --apply also to paper/overleaf/figures/.
Decision: decisions.md 2026-09-26 (T-103).
"""
import math
import shutil
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "results" / "camera_ready" / "coverage_camera_ready.parquet"
OUT = ROOT / "results" / "camera_ready" / "figures"
OVERLEAF_FIGS = ROOT / "paper" / "overleaf" / "figures"
COLORS = {"core": "#0072B2", "rai": "#EE7733"}
LABELS = {"core": "Core metadata", "rai": "RAI metadata"}
plt.rcParams.update({"font.family": "DejaVu Sans", "pdf.fonttype": 3})


def wilson_ci(k, n, z=1.959963984540054):
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, (centre - half) * 100), min(100.0, (centre + half) * 100)


def short(fid):
    return fid.split(":", 1)[-1]


def fig_fill_rates(cov):
    fill = cov.groupby(["field_id", "field_group"]).populated.agg(k="sum", n="count").reset_index()
    fill["pct"] = 100 * fill.k / fill.n
    ci = [wilson_ci(int(r.k), int(r.n)) for r in fill.itertuples()]
    fill["lo"], fill["hi"] = [c[0] for c in ci], [c[1] for c in ci]
    fill = fill.sort_values("pct", kind="stable").reset_index(drop=True)
    n_papers = cov.paper_id.nunique()

    fig, ax = plt.subplots(figsize=(5.4, 4.9))
    y = np.arange(len(fill))
    ax.barh(y, fill.pct, color=[COLORS[g] for g in fill.field_group], edgecolor="black", linewidth=0.5,
            height=0.78, xerr=[(fill.pct - fill.lo).clip(lower=0), (fill.hi - fill.pct).clip(lower=0)],
            error_kw=dict(ecolor="#222222", elinewidth=0.7, capsize=2.0, capthick=0.7))
    ax.set_yticks(y)
    ax.set_yticklabels([short(f) for f in fill.field_id], fontsize=8)
    ax.tick_params(axis="y", length=0)
    ax.set_xlim(0, 112)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xticklabels(["0%", "25%", "50%", "75%", "100%"], fontsize=8)
    ax.set_xlabel(f"Documentation rate (% of {n_papers} papers with a non-null value)", fontsize=9)
    bold = set(range(2)) | set(range(len(fill) - 4, len(fill)))      # two lowest and four highest
    for i, r in fill.iterrows():
        ax.text(r.hi + 1.4, i, f"{r.pct:.1f}%", va="center", ha="left", fontsize=7.5,
                fontweight="bold" if i in bold else "normal")
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.set_axisbelow(True)
    ax.xaxis.grid(True, color="#DFDFDF", linewidth=0.6)
    ax.legend(handles=[mpatches.Patch(facecolor=COLORS[g], edgecolor="black", label=LABELS[g]) for g in COLORS],
              loc="lower right", bbox_to_anchor=(0.99, 0.18), fontsize=8, frameon=True, edgecolor="#CCCCCC")
    low = fill.iloc[0]
    assert low.field_id == "rai:dataImputationProtocol", low.field_id
    ax.annotate(f"imputation is documented\nin only {low.pct:.1f}% of papers",
                xy=(low.hi + 9, 0), xytext=(40, 1.5), fontsize=7.5, color="#222222", ha="left", va="center",
                arrowprops=dict(arrowstyle="->", color="#666666", lw=0.7, connectionstyle="arc3,rad=0.15"))
    fig.tight_layout()
    return fig, fill


def fig_silver_vs_gold(cov):
    fr = cov.groupby(["split", "field_id", "field_group"]).populated.mean().mul(100).reset_index()
    g = fr[fr.split == "gold"].set_index("field_id")
    s = fr[fr.split == "silver"].set_index("field_id")
    m = g[["field_group"]].assign(gold=g.populated, silver=s.populated.reindex(g.index)).reset_index()

    fig, ax = plt.subplots(figsize=(5.2, 5.1))
    ax.fill_between([0, 100], [0, 0], [0, 100], color="#EDEDED", zorder=0, linewidth=0)
    ax.plot([0, 100], [0, 100], color="#999999", linestyle="--", linewidth=0.8, zorder=1)
    for grp in ("core", "rai"):
        sub = m[m.field_group == grp]
        ax.scatter(sub.gold, sub.silver, s=15 + 1.9 * sub.gold, c=COLORS[grp], marker="o" if grp == "core" else "s",
                   edgecolor="black", linewidth=0.6, alpha=0.9, zorder=3, label=f"{LABELS[grp]} ({len(sub)})")
    live = m.set_index("field_id").loc["isLiveDataset"]
    ax.annotate('isLiveDataset\n(silver abstains unless\npaper says "live")', xy=(live.gold - 1.5, live.silver + 0.5),
                xytext=(45, 17), fontsize=8, color="#222222", ha="left", va="center",
                arrowprops=dict(arrowstyle="-", color="#555555", lw=0.7))
    ax.text(103, 3, "silver under-emits", fontsize=8, style="italic", color="#555555", ha="right", va="center")
    ax.set_xlim(-3, 105)
    ax.set_ylim(-3, 105)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.tick_params(labelsize=9)
    ax.set_xlabel("Gold split fill rate (%)", fontsize=10)
    ax.set_ylabel("Silver split fill rate (%)", fontsize=10)
    ax.set_aspect("equal")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.legend(loc="upper left", fontsize=8.5, frameon=False, markerscale=0.8)
    fig.tight_layout()
    return fig, m, pearsonr(m.gold, m.silver), spearmanr(m.gold, m.silver)


def main(apply):
    cov = pd.read_parquet(DATA)
    OUT.mkdir(parents=True, exist_ok=True)
    fig, fill = fig_fill_rates(cov)
    fig.savefig(OUT / "fig1_field_fill_rates.pdf", bbox_inches="tight", facecolor="white")
    fig.savefig(OUT / "fig1_field_fill_rates.png", dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    fig, m, pr, sr = fig_silver_vs_gold(cov)
    fig.savefig(OUT / "fig_silver_vs_gold.pdf", bbox_inches="tight", facecolor="white")
    fig.savefig(OUT / "fig_silver_vs_gold.png", dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("fill rates, lowest:", fill.head(3)[["field_id", "pct"]].round(1).values.tolist())
    print("fill rates, highest:", fill.tail(4)[["field_id", "pct"]].round(1).values.tolist())
    live = m.set_index("field_id").loc["isLiveDataset"]
    print(f"silver vs gold: Pearson r = {pr[0]:.3f} (p = {pr[1]:.1e}), Spearman rho = {sr.correlation:.3f} "
          f"(p = {sr.pvalue:.1e}); isLiveDataset gold {live.gold:.1f}% silver {live.silver:.1f}%")
    if apply:
        for name in ("fig1_field_fill_rates.pdf", "fig_silver_vs_gold.pdf"):
            shutil.copy(OUT / name, OVERLEAF_FIGS / name)
        print("copied both PDFs to", OVERLEAF_FIGS)


if __name__ == "__main__":
    main("--apply" in sys.argv)
