#!/usr/bin/env python3
"""
Figure 2: Distribution of categorical field values — 603 datasets combined.
(a) License distribution (excluding unspecified, n=119)
(b) Language distribution (exclude <3 count categories)
(c) Publication year distribution
(d) Data collection types
"""

import json
import re
import sys
from pathlib import Path
from collections import Counter

import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from style import setup_style, save_fig, PALETTE, COLORS, DOUBLE_COL

ROOT = Path(__file__).parent.parent.parent
PROCESSED = ROOT / "data" / "processed"
PAPER_LINKS = ROOT / "data" / "paper_links.json"
SILVER_EXT = ROOT / "silver" / "extractions"


def normalize_license(lic):
    if not lic:
        return None
    l = lic.lower().strip()
    if not l or l in ("null", "none", "not specified", "n/a", "unknown"):
        return None
    if "mit" in l: return "MIT"
    if "apache" in l: return "Apache 2.0"
    if "cc-by-sa" in l or "cc by-sa" in l or "attribution-sharealike" in l: return "CC-BY-SA"
    if "cc-by-nc-sa" in l or "noncommercial-sharealike" in l: return "CC-BY-NC-SA"
    if "cc-by-nc" in l or ("noncommercial" in l and "share" not in l): return "CC-BY-NC"
    if "cc-by" in l or "cc by" in l or "creative commons attribution" in l: return "CC-BY"
    if "cc0" in l or "public domain" in l: return "CC0 / Public Domain"
    if "gpl" in l: return "GPL"
    if "custom" in l or "research" in l or "non-commercial" in l: return "Custom / Research"
    return "Other"


def normalize_language(lang):
    if not lang:
        return None
    l = lang.lower().strip()
    if not l or l in ("null", "none", "not specified", "n/a"):
        return None
    if l in ("en", "en-us", "english"): return "English"
    if "multilingual" in l or "101" in l or "100" in l: return "Multi-language"
    if "," in l or " and " in l or "/" in l: return "Multi-language"
    if l in ("zh", "chinese", "zh-cn"): return "Chinese"
    return "Other"


def extract_year(date_str):
    if not date_str:
        return None
    s = str(date_str).strip()
    m = re.search(r'(20\d{2})', s)
    if m:
        year = int(m.group(1))
        if 2000 <= year <= 2026:
            return year
    return None


def load_all_extractions():
    """Load gold + silver into a single list of extraction dicts."""
    all_ext = []

    with open(PAPER_LINKS) as f:
        paper_links = json.load(f)
    for ds_id in sorted(paper_links.keys()):
        ext_path = PROCESSED / ds_id / "full_pdf_metadata_result.json"
        if ext_path.exists():
            with open(ext_path) as f:
                all_ext.append(json.load(f))

    for ext_path in sorted(SILVER_EXT.glob("*.json")):
        with open(ext_path) as f:
            d = json.load(f)
        all_ext.append(d["extraction"])

    return all_ext


def main():
    setup_style()

    all_ext = load_all_extractions()
    n_total = len(all_ext)
    print(f"  Total extractions: {n_total}")

    fig, axes = plt.subplots(2, 2, figsize=(DOUBLE_COL, 6.0))
    bar_color = COLORS["claude"]

    # ── (a) License distribution (exclude unspecified) ──
    ax = axes[0, 0]
    licenses = []
    for ext in all_ext:
        lic = normalize_license(ext.get("license", ""))
        if lic is not None:
            licenses.append(lic)

    n_with_license = len(licenses)
    lic_counts = Counter(licenses).most_common()
    labels = [l for l, _ in lic_counts]
    pcts = [c / n_with_license * 100 for _, c in lic_counts]

    y_pos = np.arange(len(labels))
    bars = ax.barh(y_pos, pcts, color=PALETTE[:len(labels)], edgecolor="white", linewidth=0.5)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel("Percentage (%)")
    ax.set_title(f"(a) License (n={n_with_license}, {n_with_license/n_total*100:.0f}% of corpus)")
    ax.invert_yaxis()
    for bar, pct, (_, cnt) in zip(bars, pcts, lic_counts):
        ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2,
                f"{pct:.0f}% ({cnt})", va="center", fontsize=7)

    # ── (b) Language distribution (exclude <3 counts) ──
    ax = axes[0, 1]
    languages = []
    for ext in all_ext:
        lang = normalize_language(ext.get("inLanguage", ""))
        if lang is not None:
            languages.append(lang)

    n_with_lang = len(languages)
    lang_counts = Counter(languages).most_common()
    # Filter out categories with <3
    lang_counts = [(l, c) for l, c in lang_counts if c >= 3]
    labels = [l for l, _ in lang_counts]
    pcts = [c / n_with_lang * 100 for _, c in lang_counts]

    y_pos = np.arange(len(labels))
    bars = ax.barh(y_pos, pcts, color=PALETTE[:len(labels)], edgecolor="white", linewidth=0.5)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel("Percentage (%)")
    ax.set_title(f"(b) Language (n={n_with_lang})")
    ax.invert_yaxis()
    for bar, pct, (_, cnt) in zip(bars, pcts, lang_counts):
        ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2,
                f"{pct:.0f}% ({cnt})", va="center", fontsize=7)

    # ── (c) Publication year distribution ──
    ax = axes[1, 0]
    years = []
    for ext in all_ext:
        y = extract_year(ext.get("datePublished", ""))
        if y is not None:
            years.append(y)

    n_with_year = len(years)
    year_counts = Counter(years)
    year_range = range(min(year_counts.keys()), max(year_counts.keys()) + 1)
    year_vals = [year_counts.get(y, 0) for y in year_range]
    year_pcts = [v / n_with_year * 100 for v in year_vals]

    ax.bar(list(year_range), year_pcts, color=bar_color, edgecolor="white", linewidth=0.5)
    ax.set_xlabel("Year")
    ax.set_ylabel("Percentage (%)")
    ax.set_title(f"(c) Publication Year (n={n_with_year})")
    # Only label every other year if too dense
    all_years = list(year_range)
    if len(all_years) > 15:
        tick_years = [y for y in all_years if y % 2 == 0]
        ax.set_xticks(tick_years)
        ax.set_xticklabels([str(y) for y in tick_years], rotation=45, ha="right", fontsize=8)
    else:
        ax.set_xticks(all_years)
        ax.set_xticklabels([str(y) for y in all_years], rotation=45, ha="right", fontsize=8)


    # ── (d) Data collection types ──
    ax = axes[1, 1]
    collection_types = []
    for ext in all_ext:
        ct = ext.get("rai:dataCollectionType", "")
        if ct:
            for t in re.split(r"[,;/]\s*|\s+and\s+", ct):
                t = t.strip()
                if t and len(t) > 2:
                    # Shorten long labels
                    if "user-generated" in t.lower():
                        t = "User-generated content"
                    elif "passive" in t.lower():
                        t = "Passive collection"
                    elif "customer feedback" in t.lower():
                        t = "Customer feedback"
                    elif "self-reporting" in t.lower():
                        t = "Self-reporting"
                    collection_types.append(t)

    ct_counts = Counter(collection_types).most_common(10)
    n_ct = sum(c for _, c in ct_counts)
    labels = [l for l, _ in ct_counts]
    pcts = [c / n_ct * 100 for _, c in ct_counts]

    y_pos = np.arange(len(labels))
    bars = ax.barh(y_pos, pcts, color=PALETTE[:len(labels)], edgecolor="white", linewidth=0.5)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlabel("Percentage (%)")
    ax.set_title("(d) Data Collection Types")
    ax.invert_yaxis()
    for bar, pct, (_, cnt) in zip(bars, pcts, ct_counts):
        ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2,
                f"{pct:.0f}% ({cnt})", va="center", fontsize=7)

    fig.tight_layout()
    save_fig(fig, "fig2_field_value_distribution")


if __name__ == "__main__":
    main()
