#!/usr/bin/env python3
"""
Figure: Silver dataset validation — gold vs silver quality comparison.
(a) Fill rate per field (gold vs silver side by side)
(b) Null rate comparison scatter (each dot = one field)
(c) Domain distribution comparison (normalized)
(d) Description length CDF (gold vs silver)
"""

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
SILVER_EXT = ROOT / "silver" / "extractions"
SILVER_MANIFEST = ROOT / "silver" / "data" / "final_500_manifest.json"

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
        return "Other"
    d = desc.lower()
    if any(k in d for k in ["image", "vision", "visual", "object detection", "segmentation", "photo", "video", "scene"]):
        return "Vision"
    if any(k in d for k in ["code", "programming", "software"]):
        return "Code"
    if any(k in d for k in ["math", "arithmetic"]):
        return "Math"
    if any(k in d for k in ["speech", "audio", "voice", "spoken"]):
        return "Audio"
    if any(k in d for k in ["medical", "clinical", "health", "biomedical"]):
        return "Medical"
    if any(k in d for k in ["multimodal", "multi-modal", "vqa"]):
        return "Multimodal"
    if any(k in d for k in ["text", "nlp", "language", "corpus", "sentiment"]):
        return "NLP"
    return "Other"


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
    print(f"  Gold: {n_gold}, Silver: {n_silver}")

    # Compute fill rates
    gold_fill = {}
    silver_fill = {}
    for f in FIELDS_30:
        g_non_null = sum(1 for ext in gold.values() if ext.get(f) is not None and str(ext.get(f, "")).strip())
        gold_fill[f] = g_non_null / n_gold * 100
        s_non_null = sum(1 for ext in silver.values() if ext.get(f) is not None and str(ext.get(f, "")).strip())
        silver_fill[f] = s_non_null / n_silver * 100

    gold_color = COLORS["claude"]
    silver_color = COLORS["gold"]

    fig, axes = plt.subplots(2, 2, figsize=(DOUBLE_COL, 6.5))

    # ── (a) Fill rate per field ──
    ax = axes[0, 0]
    y_pos = np.arange(len(FIELDS_30))
    width = 0.35
    g_vals = [gold_fill[f] for f in FIELDS_30]
    s_vals = [silver_fill[f] for f in FIELDS_30]

    ax.barh(y_pos - width/2, g_vals, width, label=f"Gold (n={n_gold})",
            color=gold_color, edgecolor="white", linewidth=0.3)
    ax.barh(y_pos + width/2, s_vals, width, label=f"Silver (n={n_silver})",
            color=silver_color, edgecolor="white", linewidth=0.3)
    ax.set_yticks(y_pos)
    ax.set_yticklabels([SHORT_NAMES[f] for f in FIELDS_30], fontsize=5.5)
    ax.set_xlabel("Fill Rate (%)")
    ax.invert_yaxis()
    ax.set_xlim(0, 105)
    ax.set_title("(a) Fill Rate per Field (Blue=Gold, Orange=Silver)")

    # Separator lines between general and RAI
    ax.axhline(9.5, color="gray", linestyle=":", linewidth=0.5)

    # ── (b) Fill rate scatter (gold vs silver per field) ──
    ax = axes[0, 1]
    ax.scatter(g_vals, s_vals, c=COLORS["purple"], s=25, zorder=5, edgecolors="white", linewidth=0.5)
    ax.plot([0, 100], [0, 100], "k--", linewidth=0.8, alpha=0.4, label="y = x")

    # Abbreviated names consistent with fig3
    ABBREV = {
        "name": "name", "description": "description", "url": "url",
        "license": "license", "creator": "creator", "publisher": "publisher",
        "datePublished": "datePublished", "inLanguage": "inLanguage",
        "citeAs": "citeAs", "isLiveDataset": "isLiveDataset",
        "dataCollection": "Collection", "dataCollectionType": "CollType",
        "dataCollectionMissingData": "MissingData", "dataCollectionRawData": "RawData",
        "dataCollectionTimeframe": "Timeframe", "dataImputationProtocol": "Imputation",
        "dataManipulationProtocol": "Manipulation", "dataPreprocessingProtocol": "Preprocessing",
        "dataAnnotationProtocol": "AnnProtocol", "dataAnnotationPlatform": "AnnPlatform",
        "dataAnnotationAnalysis": "AnnAnalysis", "annotationsPerItem": "AnnPerItem",
        "annotatorDemographics": "AnnDemog.", "machineAnnotationTools": "MachineAnn",
        "dataReleaseMaintenancePlan": "ReleasePlan", "personalSensitiveInformation": "PSI",
        "dataSocialImpact": "SocialImpact", "dataBiases": "Biases",
        "dataLimitations": "Limitations", "dataUseCases": "UseCases",
    }

    # Label only outliers where |gold - silver| > 25 percentage points
    for i, f in enumerate(FIELDS_30):
        if abs(g_vals[i] - s_vals[i]) > 25:
            short = ABBREV.get(SHORT_NAMES[f], SHORT_NAMES[f])
            ax.annotate(short, (g_vals[i], s_vals[i]),
                       fontsize=7, fontweight="bold",
                       xytext=(8, -5), textcoords="offset points",
                       arrowprops=dict(arrowstyle="-", color="0.5", lw=0.5))

    ax.set_xlabel("Gold Fill Rate (%)")
    ax.set_ylabel("Silver Fill Rate (%)")
    ax.set_title("(b) Gold vs Silver Fill Rate")
    ax.set_xlim(-5, 105)
    ax.set_ylim(-5, 105)
    ax.legend(fontsize=7)

    # Correlation
    corr = np.corrcoef(g_vals, s_vals)[0, 1]
    ax.text(5, 92, f"r = {corr:.2f}", fontsize=8, color=COLORS["purple"])

    # Overall fill rates
    gold_mean = np.mean(g_vals)
    silver_mean = np.mean(s_vals)
    ax.text(5, 83, f"Gold mean: {gold_mean:.1f}%\nSilver mean: {silver_mean:.1f}%",
            fontsize=7, color="gray")

    # ── (c) Domain distribution (normalized, side by side) ──
    ax = axes[1, 0]
    gold_domains = Counter(infer_domain((ext.get("description") or "")) for ext in gold.values())
    silver_domains = Counter(infer_domain((ext.get("description") or "")) for ext in silver.values())
    all_doms = sorted(set(list(gold_domains.keys()) + list(silver_domains.keys())),
                      key=lambda d: gold_domains.get(d, 0) + silver_domains.get(d, 0), reverse=True)

    y_dom = np.arange(len(all_doms))
    g_pct = [gold_domains.get(d, 0) / n_gold * 100 for d in all_doms]
    s_pct = [silver_domains.get(d, 0) / n_silver * 100 for d in all_doms]
    width_d = 0.35

    ax.barh(y_dom - width_d/2, g_pct, width_d, label="Gold", color=gold_color,
            edgecolor="white", linewidth=0.5)
    ax.barh(y_dom + width_d/2, s_pct, width_d, label="Silver", color=silver_color,
            edgecolor="white", linewidth=0.5)
    ax.set_yticks(y_dom)
    ax.set_yticklabels(all_doms, fontsize=8)
    ax.set_xlabel("Percentage of Dataset (%)")
    ax.set_title("(c) Domain Distribution (Normalized)")
    ax.invert_yaxis()
    ax.legend(fontsize=7)

    # ── (d) Description length CDF ──
    ax = axes[1, 1]
    g_lens = sorted([len((ext.get("description") or "").split()) for ext in gold.values()])
    s_lens = sorted([len((ext.get("description") or "").split()) for ext in silver.values()])

    g_cdf = np.arange(1, len(g_lens) + 1) / len(g_lens) * 100
    s_cdf = np.arange(1, len(s_lens) + 1) / len(s_lens) * 100

    ax.plot(g_lens, g_cdf, color=gold_color, linewidth=1.5, label=f"Gold (n={n_gold})")
    ax.plot(s_lens, s_cdf, color=silver_color, linewidth=1.5, label=f"Silver (n={n_silver})")
    ax.set_xlabel("Description Length (words)")
    ax.set_ylabel("Cumulative %")
    ax.set_title("(d) Description Length CDF")
    ax.legend(fontsize=7)
    ax.set_xlim(0, 150)

    fig.tight_layout()
    save_fig(fig, "fig_silver_comparison")


if __name__ == "__main__":
    main()
