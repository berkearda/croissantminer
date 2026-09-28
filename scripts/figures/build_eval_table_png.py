#!/usr/bin/env python3
"""Render a single PNG table summarising current evaluation results.

Reads results/v5_scoring_test88/*.json (composite mean + 95% CI per system,
restricted to the held-out 88-paper test split), groups by architecture
family, sorts within family by composite score, and emits a colour-banded
matplotlib table to:
    results/figures/eval_table_test88_<YYYY-MM-DD>.png

Notes for the reader (rendered in the figure):
  * sonnet-4-5 single-call is the gold-seed reference (not a baseline).
  * Specialist (Paul) and ReAct (Ahmetcan) are still in dev-tuning;
    their test-88 numbers are pending and intentionally not shown.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

ROOT = Path(__file__).resolve().parents[2]
SCORE_DIR = ROOT / "results" / "v5_scoring_test88"
OUT_DIR = ROOT / "results" / "figures"

# (category, display_name, file_stem, note)
LINEUP = [
    # ── Frontier API, single-call ──
    ("Frontier (single-call)", "Claude Sonnet 4.5 *gold-seed*", "claude_sonnet_4_5", "gold-seed"),
    ("Frontier (single-call)", "Claude Sonnet 4.6",            "claude_sonnet_4_6", ""),
    ("Frontier (single-call)", "Claude Opus 4.7",              "claude_opus_4_7",   ""),
    ("Frontier (single-call)", "GPT-5.4 (full)",               "gpt5_4_full",       ""),
    ("Frontier (single-call)", "GPT-5.4 mini",                 "gpt5_4_mini",       ""),
    ("Frontier (single-call)", "Gemini 3.1 Pro",               "gemini_3_1_pro",    ""),
    ("Frontier (single-call)", "Gemini 2.5 Flash",             "gemini_2_5_flash",  ""),
    ("Frontier (single-call)", "DeepSeek V3.2",                "deepseek_v3_2",     ""),
    # ── Open-weight, single-call ──
    ("Open-weight (single-call)", "Qwen 3.6 35B-A3B",  "qwen3_6_35b_a3b", ""),
    ("Open-weight (single-call)", "Mistral Small 4",   "mistral_small_4", ""),
    ("Open-weight (single-call)", "GLM 5.1",           "glm_5_1",         ""),
    ("Open-weight (single-call)", "Llama 4 Scout",     "llama4_scout",    ""),
    # ── Agentic V2 (full-paper specialist + critique) ──
    ("Agentic V2", "V2 × Sonnet 4.5 *gold-seed*",   "agentic_v2_sonnet_4_5",     "gold-seed"),
    ("Agentic V2", "V2 × Sonnet 4.6 [v4 frozen]",   "agentic_v2_sonnet_4_6_v4",  "frozen"),
    ("Agentic V2", "V2 × GPT-5.4 (full) [v1]",      "agentic_v2_gpt5_4_full",    ""),
    ("Agentic V2", "V2 × Gemini 3.1 Pro [v1]",      "agentic_v2_gemini_3_1_pro", ""),
    # ── Agentic LEV (locator-extractor) ──
    ("Agentic LEV", "LEV × Sonnet 4.5 *gold-seed*", "agentic_lev_sonnet_4_5",     "gold-seed"),
    ("Agentic LEV", "LEV × GPT-5.4 (full) [v1]",    "agentic_lev_gpt5_4_full",    ""),
    ("Agentic LEV", "LEV × Gemini 3.1 Pro [v1]",    "agentic_lev_gemini_3_1_pro", ""),
]

CATEGORY_COLOURS = {
    "Frontier (single-call)":      "#fde2e4",
    "Open-weight (single-call)":   "#e2eafc",
    "Agentic V2":                  "#d8f3dc",
    "Agentic LEV":                 "#fff1c1",
}


def load_row(stem: str) -> dict | None:
    fp = SCORE_DIR / f"{stem}.json"
    if not fp.exists():
        return None
    d = json.loads(fp.read_text())
    if d.get("composite_mean") is None:
        return None
    n = d.get("n_papers_scored")
    # Skip incomplete test-88 runs to avoid apples-to-oranges (anything < 88).
    if n is None or n < 88:
        return None
    return {
        "n": n,
        "mean": d["composite_mean"],
        "lo": d["composite_ci"]["ci_lo"],
        "hi": d["composite_ci"]["ci_hi"],
    }


def build_rows():
    by_cat: dict[str, list] = {}
    for cat, label, stem, note in LINEUP:
        s = load_row(stem)
        if s is None:
            continue
        by_cat.setdefault(cat, []).append((label, note, s))
    # sort within category by composite mean desc
    for k in by_cat:
        by_cat[k].sort(key=lambda r: -r[2]["mean"])
    # preserve LINEUP category order
    ordered = []
    for cat in dict.fromkeys([c for c, _, _, _ in LINEUP]):
        if cat in by_cat:
            ordered.append((cat, by_cat[cat]))
    return ordered


def render(ordered, out_path: Path):
    n_rows = sum(len(rows) for _, rows in ordered) + len(ordered)  # +1 banner per cat
    fig_h = 0.40 * n_rows + 2.6  # extra room for title + footer
    fig, ax = plt.subplots(figsize=(11.5, fig_h))
    ax.set_axis_off()

    headers = ["System", "n", "Composite mean", "95% CI", "Note"]
    col_x = [0.02, 0.54, 0.66, 0.79, 0.93]
    col_align = ["left", "center", "center", "center", "left"]

    # Title
    title = f"CroissantMiner — test-88 evaluation snapshot ({date.today().isoformat()})"
    fig.suptitle(title, fontsize=14, fontweight="bold", y=0.985)
    subtitle = ("Composite = equal-weighted mean over 30 fields  ·  Tier 1 (10): exact-match / token-F1  ·  "
                "Tier 2 (20): token-F1 fallback (judge ensemble pending)\n"
                "95% CI = paper-level cluster bootstrap, 2,000 replicates.   *gold-seed* rows reference Sonnet 4.5 "
                "and are inflated; not part of the baseline lineup.")
    fig.text(0.5, 0.945, subtitle, fontsize=8.5, ha="center", va="top", color="#333")

    # reserve top/bottom for title + footer
    top, bot = 0.90, 0.08
    y = top
    row_h = (top - bot) / (n_rows + 1)

    # column headers
    for x, h, a in zip(col_x, headers, col_align):
        ax.text(x, y, h, transform=ax.transAxes, fontsize=10, fontweight="bold", ha=a, va="center")
    y -= row_h
    ax.plot([0.0, 1.0], [y + row_h * 0.4, y + row_h * 0.4],
            transform=ax.transAxes, color="#333", lw=1.0)

    for cat, rows in ordered:
        # category banner row
        rect = Rectangle((0.0, y - row_h * 0.15), 1.0, row_h * 0.95,
                         transform=ax.transAxes, facecolor=CATEGORY_COLOURS[cat],
                         edgecolor="none", zorder=0)
        ax.add_patch(rect)
        ax.text(col_x[0], y, cat, transform=ax.transAxes, fontsize=10.5,
                fontweight="bold", ha="left", va="center", color="#222")
        y -= row_h
        for label, note, s in rows:
            cells = [
                label,
                f"{s['n']}",
                f"{s['mean']:.3f}",
                f"[{s['lo']:.3f}, {s['hi']:.3f}]",
                note,
            ]
            for x, txt, a in zip(col_x, cells, col_align):
                ax.text(x, y, txt, transform=ax.transAxes, fontsize=9.5, ha=a, va="center")
            y -= row_h

    # footer
    foot = ("All rows are the held-out 88-paper test split (n=88 / 2,630 cells). The 14-paper dev split is reserved for "
            "tuning and excluded from this table.\n"
            "Specialist (Paul, multi-agent) and ReAct (Ahmetcan) are still in dev-tuning; their frozen test-88 runs are "
            "pending and intentionally not shown here.\n"
            "Final headline numbers will use the GPT-5.4 + Gemini-3.1-Pro + Llama-3.3-70B judge ensemble (T-021); "
            "Tier-2 currently uses token-F1 fallback until the ensemble lands.")
    fig.text(0.5, 0.025, foot, fontsize=8.0, ha="center", va="bottom", color="#555")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=180, bbox_inches="tight", facecolor="white")
    print(f"wrote {out_path}")


def main():
    ordered = build_rows()
    if not ordered:
        print("no rows loaded — check results/v5_scoring/", file=sys.stderr)
        sys.exit(1)
    out = OUT_DIR / f"eval_table_test88_{date.today().isoformat()}.png"
    render(ordered, out)


if __name__ == "__main__":
    main()
