#!/usr/bin/env python3
"""
Figure 1: Dataset statistics — 603 datasets (103 gold + 500 silver).
(a) Domain distribution (normalized % side-by-side)
(b) Paper length distribution (gold only — real page counts)
(c) Field coverage histogram (gold vs silver, overlapping)
(d) Fill rate per field (gold vs silver horizontal bars)
"""

import csv
import json
import sys
from pathlib import Path
from collections import Counter

import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from style import setup_style, save_fig, COLORS, DOUBLE_COL

ROOT = Path(__file__).parent.parent.parent
PROCESSED = ROOT / "data" / "processed"
PAPER_LINKS = ROOT / "data" / "paper_links.json"
PAGE_COUNTS = ROOT / "data" / "paper_lengths.csv"
SILVER_EXT = ROOT / "silver" / "extractions"

FIELDS_30 = [
    "name", "description", "url", "license", "creator", "publisher",
    "datePublished", "inLanguage", "citeAs", "isLiveDataset",
    "rai:dataCollection", "rai:dataCollectionType", "rai:dataCollectionMissingData",
    "rai:dataCollectionRawData", "rai:dataCollectionTimeframe",
    "rai:dataImputationProtocol", "rai:dataManipulationProtocol",
    "rai:dataPreprocessingProtocol", "rai:dataAnnotationProtocol",
    "rai:dataAnnotationPlatform", "rai:dataAnnotationAnalysis",
    "rai:annotationsPerItem", "rai:annotatorDemographics",
    "rai:machineAnnotationTools", "rai:dataReleaseMaintenancePlan",
    "rai:personalSensitiveInformation", "rai:dataSocialImpact",
    "rai:dataBiases", "rai:dataLimitations", "rai:dataUseCases",
]
SHORT_NAMES = {f: f.split(":")[-1] if ":" in f else f for f in FIELDS_30}


def infer_domain(desc):
    if not desc:
        return "Uncategorized"
    d = desc.lower()
    if any(k in d for k in ["image", "vision", "visual", "object detection", "segmentation", "photo", "video", "scene"]):
        return "Vision"
    if any(k in d for k in ["code", "programming", "software", "bug", "repository"]):
        return "Code"
    if any(k in d for k in ["math", "arithmetic", "calculation", "geometry", "algebra"]):
        return "Math"
    if any(k in d for k in ["speech", "audio", "voice", "spoken", "asr", "tts"]):
        return "Audio"
    if any(k in d for k in ["medical", "clinical", "health", "biomedical", "radiology"]):
        return "Medical"
    if any(k in d for k in ["multimodal", "multi-modal", "vqa", "chart"]):
        return "Multimodal"
    if any(k in d for k in ["translation", "multilingual", "cross-lingual", "parallel corpus"]):
        return "Translation"
    if any(k in d for k in ["question answering", "reading comprehension", "qa", "commonsense"]):
        return "QA"
    if any(k in d for k in ["benchmark", "evaluation", "multitask", "language understanding"]):
        return "NLP Benchmark"
    if any(k in d for k in ["remote sensing", "satellite", "earth observation", "geospatial"]):
        return "Remote Sensing"
    if any(k in d for k in ["robot", "embodied", "navigation"]):
        return "Robotics"
    if any(k in d for k in ["text", "nlp", "language", "corpus", "sentiment", "ner"]):
        return "NLP"
    return "Uncategorized"


def main():
    setup_style()

    # Load gold
    with open(PAPER_LINKS) as f:
        paper_links = json.load(f)
    gold = {}
    for ds_id in sorted(paper_links.keys()):
        ext_path = PROCESSED / ds_id / "full_pdf_metadata_result.json"
        if ext_path.exists():
            with open(ext_path) as f:
                gold[ds_id] = json.load(f)

    # Load silver
    silver = {}
    for ext_path in sorted(SILVER_EXT.glob("*.json")):
        with open(ext_path) as f:
            d = json.load(f)
        silver[d["dataset_id"]] = d["extraction"]

    n_gold = len(gold)
    n_silver = len(silver)
    print(f"  Gold: {n_gold}, Silver: {n_silver}, Total: {n_gold + n_silver}")

    # Load page counts (gold only)
    page_counts = []
    if PAGE_COUNTS.exists():
        with open(PAGE_COUNTS) as f:
            for row in csv.DictReader(f):
                if row["num_pages"]:
                    page_counts.append(int(row["num_pages"]))

    # Compute stats
    gold_domains = [infer_domain(ext.get("description", "") or "") for ext in gold.values()]
    silver_domains = [infer_domain(ext.get("description", "") or "") for ext in silver.values()]

    gold_field_counts = [sum(1 for v in ext.values() if v is not None and str(v).strip()) for ext in gold.values()]
    silver_field_counts = [sum(1 for v in ext.values() if v is not None and str(v).strip()) for ext in silver.values()]

    gold_color = COLORS["claude"]
    silver_color = COLORS["gold"]

    fig, axes = plt.subplots(2, 2, figsize=(DOUBLE_COL, 6.5))

    # ── (a) Domain distribution — normalized % side by side ──
    ax = axes[0, 0]
    gold_dom_counts = Counter(gold_domains)
    silver_dom_counts = Counter(silver_domains)
    all_doms = sorted(set(list(gold_dom_counts.keys()) + list(silver_dom_counts.keys())),
                      key=lambda d: gold_dom_counts.get(d, 0) + silver_dom_counts.get(d, 0), reverse=True)

    y_pos = np.arange(len(all_doms))
    width = 0.35
    g_pct = [gold_dom_counts.get(d, 0) / n_gold * 100 for d in all_doms]
    s_pct = [silver_dom_counts.get(d, 0) / n_silver * 100 for d in all_doms]

    ax.barh(y_pos - width/2, g_pct, width, label=f"Gold (n={n_gold})",
            color=gold_color, edgecolor="white", linewidth=0.5)
    ax.barh(y_pos + width/2, s_pct, width, label=f"Silver (n={n_silver})",
            color=silver_color, edgecolor="white", linewidth=0.5)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(all_doms, fontsize=8)
    ax.set_xlabel("Percentage of Dataset (%)")
    ax.set_title("(a) Domain Distribution")
    ax.invert_yaxis()
    ax.legend(fontsize=7, loc="lower right")

    # ── (b) Paper length — gold only (real page counts) ──
    ax = axes[0, 1]
    if page_counts:
        bins_pl = [0, 5, 10, 15, 20, 30, 50, 250]
        bin_labels_pl = ["<5", "5-10", "10-15", "15-20", "20-30", "30-50", "50+"]
        hist_pl, _ = np.histogram(page_counts, bins=bins_pl)
        x_pl = np.arange(len(bin_labels_pl))
        bars = ax.bar(x_pl, hist_pl, color=gold_color, edgecolor="white", linewidth=0.5)
        ax.set_xticks(x_pl)
        ax.set_xticklabels(bin_labels_pl)
        ax.set_xlabel("Number of Pages")
        ax.set_ylabel("Number of Papers")
        mean_pages = np.mean(page_counts)
        median_pages = np.median(page_counts)
        ax.axvline(np.interp(mean_pages, [2.5, 7.5, 12.5, 17.5, 25, 40, 150], range(7)),
                   color=COLORS["highlight"], linestyle="--", linewidth=1.2,
                   label=f"Mean = {mean_pages:.0f}p")
        ax.legend(fontsize=8)
        for bar, count in zip(bars, hist_pl):
            if count > 0:
                ax.text(bar.get_x() + bar.get_width()/2, count + 0.5,
                        str(count), ha="center", fontsize=8)
    ax.set_title(f"(b) Paper Length (Gold, n={len(page_counts)})")

    # ── (c) Field coverage — overlapping histograms ──
    ax = axes[1, 0]
    bins_fc = np.arange(5, 31)
    ax.hist(gold_field_counts, bins=bins_fc, alpha=0.85, color=gold_color,
            edgecolor="white", linewidth=0.5, label=f"Gold (mean={np.mean(gold_field_counts):.1f})")
    ax.hist(silver_field_counts, bins=bins_fc, alpha=0.55, color=silver_color,
            edgecolor="white", linewidth=0.5, label=f"Silver (mean={np.mean(silver_field_counts):.1f})")
    ax.axvline(np.mean(gold_field_counts), color=gold_color, linestyle="--", linewidth=1.2)
    ax.axvline(np.mean(silver_field_counts), color=silver_color, linestyle="--", linewidth=1.2)
    ax.set_xlabel("Non-null Fields (out of 30)")
    ax.set_ylabel("Count")
    ax.set_title("(c) Field Coverage per Dataset")
    ax.legend(fontsize=7)

    # ── (d) Fill rate — 10 General fields only (full 30 in fig_silver_comparison) ──
    ax = axes[1, 1]
    GENERAL_10 = FIELDS_30[:10]
    GENERAL_LABELS = ["name", "description", "url", "license", "creator",
                      "publisher", "datePublished", "inLanguage", "citeAs", "isLiveDataset"]
    gold_fill = []
    silver_fill = []
    for f in GENERAL_10:
        gf = sum(1 for ext in gold.values() if ext.get(f) is not None and str(ext.get(f, "")).strip()) / n_gold * 100
        sf = sum(1 for ext in silver.values() if ext.get(f) is not None and str(ext.get(f, "")).strip()) / n_silver * 100
        gold_fill.append(gf)
        silver_fill.append(sf)

    y_f = np.arange(len(GENERAL_10))
    width_f = 0.35
    ax.barh(y_f - width_f/2, gold_fill, width_f, label="Gold", color=gold_color,
            edgecolor="white", linewidth=0.5)
    ax.barh(y_f + width_f/2, silver_fill, width_f, label="Silver", color=silver_color,
            edgecolor="white", linewidth=0.5)
    ax.set_yticks(y_f)
    ax.set_yticklabels(GENERAL_LABELS, fontsize=9)
    ax.set_xlabel("Fill Rate (%)")
    ax.set_title("(d) General Field Fill Rate (Blue=Gold, Orange=Silver)")
    ax.invert_yaxis()
    ax.set_xlim(0, 110)

    fig.tight_layout()
    save_fig(fig, "fig1_dataset_stats")


if __name__ == "__main__":
    main()
