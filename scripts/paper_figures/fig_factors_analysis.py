#!/usr/bin/env python3
"""
Figure 5: Factors affecting extraction quality (multi-panel, ref9 style).
(a) Paper length vs composite accuracy (scatter + trend)
(b) Number of non-null GT fields vs accuracy
(c) Performance by domain
(d) Performance by field difficulty tier
"""

import json
import sys
from pathlib import Path
from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from style import setup_style, save_fig, COLORS, PALETTE, DOUBLE_COL

ROOT = Path(__file__).parent.parent.parent
PROCESSED = ROOT / "data" / "processed"
PAPER_LINKS = ROOT / "data" / "paper_links.json"
EVAL_PATH = ROOT / "results" / "eval_16field" / "eval_16field_results.json"
GT_PATH = ROOT / "data" / "groundtruth_30field" / "all_annotations.json"

# Field difficulty tiers (from assignment matrix)
FIELD_TIERS = {
    "HARDEST": ["rai:dataCollection", "rai:dataPreprocessingProtocol", "rai:dataManipulationProtocol",
                "rai:dataBiases", "rai:dataSocialImpact", "rai:dataLimitations",
                "rai:dataReleaseMaintenancePlan", "rai:dataCollectionMissingData", "rai:dataImputationProtocol"],
    "HARD": ["rai:dataAnnotationProtocol", "rai:dataAnnotationAnalysis", "rai:annotatorDemographics",
             "rai:dataCollectionRawData", "rai:dataCollectionTimeframe", "rai:personalSensitiveInformation"],
    "MEDIUM": ["publisher", "rai:dataUseCases", "rai:machineAnnotationTools", "rai:annotationsPerItem",
               "rai:dataAnnotationPlatform", "license", "creator", "datePublished", "rai:dataCollectionType"],
    "EASY": ["name", "description", "url", "inLanguage", "citeAs", "isLiveDataset"],
}


def infer_domain(desc: str) -> str:
    if not desc:
        return "Other"
    d = desc.lower()
    if any(k in d for k in ["image", "vision", "visual", "video", "scene"]):
        return "Vision"
    if any(k in d for k in ["code", "programming", "software", "bug"]):
        return "Code"
    if any(k in d for k in ["math", "arithmetic", "geometry"]):
        return "Math"
    if any(k in d for k in ["speech", "audio", "voice"]):
        return "Speech"
    if any(k in d for k in ["medical", "clinical", "health"]):
        return "Medical"
    if any(k in d for k in ["multimodal", "vqa", "chart"]):
        return "Multimodal"
    if any(k in d for k in ["question answering", "qa", "comprehension"]):
        return "QA"
    if any(k in d for k in ["benchmark", "evaluation", "multitask"]):
        return "NLP Bench."
    if any(k in d for k in ["text", "nlp", "language", "corpus"]):
        return "NLP"
    return "Other"


def main():
    setup_style()

    with open(EVAL_PATH) as f:
        eval_results = json.load(f)

    claude = eval_results["summaries"].get("Claude Sonnet 4.5", {})
    per_dataset = claude.get("per_dataset", {})
    per_field = claude.get("per_field", {})

    # Load GT for field counts
    gt = {}
    if GT_PATH.exists():
        with open(GT_PATH) as f:
            gt = json.load(f)

    # Load extractions for paper lengths
    with open(PAPER_LINKS) as f:
        paper_links = json.load(f)

    fig, axes = plt.subplots(1, 4, figsize=(DOUBLE_COL, 2.8))

    # ── (a) Description length vs accuracy (proxy for paper complexity) ──
    ax = axes[0]
    ds_lengths = []
    ds_scores = []
    for ds, score in per_dataset.items():
        ext_path = PROCESSED / ds / "full_pdf_metadata_result.json" if (PROCESSED / ds).exists() else None
        # Try to match dataset name to processed dir
        for ds_dir in PROCESSED.iterdir():
            if ds.lower().replace(" ", "_") in ds_dir.name.lower():
                ext_path = ds_dir / "full_pdf_metadata_result.json"
                break
        if ext_path and ext_path.exists():
            with open(ext_path) as f:
                ext = json.load(f)
            desc = ext.get("description", "") or ""
            length = len(desc.split())
            ds_lengths.append(length)
            ds_scores.append(score * 100)

    if ds_lengths:
        ax.scatter(ds_lengths, ds_scores, c=COLORS["claude"], alpha=0.7, s=40, edgecolors="white", linewidth=0.5)
        z = np.polyfit(ds_lengths, ds_scores, 1)
        p = np.poly1d(z)
        x_line = np.linspace(min(ds_lengths), max(ds_lengths), 50)
        ax.plot(x_line, p(x_line), "--", color=COLORS["highlight"], linewidth=1.5)
    ax.set_xlabel("Description Length (words)")
    ax.set_ylabel("Composite Score (%)")
    ax.set_title("(a) Paper Complexity", fontsize=10)

    # ── (b) Number of GT fields vs accuracy ──
    ax = axes[1]
    gt_counts = []
    gt_scores = []
    for ds, score in per_dataset.items():
        if ds in gt:
            entry = gt[ds][0] if isinstance(gt[ds], list) else gt[ds]
            non_null = sum(1 for v in entry.values()
                          if v is not None and str(v).strip()
                          and str(v).strip().lower() not in ("unknown", "n/a", "null"))
            gt_counts.append(non_null)
            gt_scores.append(score * 100)

    if gt_counts:
        ax.scatter(gt_counts, gt_scores, c=COLORS["green"], alpha=0.7, s=40, edgecolors="white", linewidth=0.5)
        z = np.polyfit(gt_counts, gt_scores, 1)
        p = np.poly1d(z)
        x_line = np.linspace(min(gt_counts), max(gt_counts), 50)
        ax.plot(x_line, p(x_line), "--", color=COLORS["highlight"], linewidth=1.5)
    ax.set_xlabel("Non-null GT Fields")
    ax.set_ylabel("Composite Score (%)")
    ax.set_title("(b) GT Density", fontsize=10)

    # ── (c) Performance by domain ──
    ax = axes[2]
    domain_scores = defaultdict(list)
    for ds, score in per_dataset.items():
        # Find extraction to get description
        for ds_dir in PROCESSED.iterdir():
            if ds.lower().replace(" ", "_") in ds_dir.name.lower():
                ext_path = ds_dir / "full_pdf_metadata_result.json"
                if ext_path.exists():
                    with open(ext_path) as f:
                        ext = json.load(f)
                    domain = infer_domain(ext.get("description", ""))
                    domain_scores[domain].append(score * 100)
                break

    if domain_scores:
        sorted_domains = sorted(domain_scores.items(), key=lambda x: np.mean(x[1]), reverse=True)
        labels = [d for d, _ in sorted_domains]
        means = [np.mean(s) for _, s in sorted_domains]
        ax.barh(range(len(labels)), means, color=PALETTE[:len(labels)], edgecolor="white", linewidth=0.5)
        ax.set_yticks(range(len(labels)))
        ax.set_yticklabels(labels, fontsize=8)
        ax.set_xlabel("Composite Score (%)")
        ax.invert_yaxis()
    ax.set_title("(c) By Domain", fontsize=10)

    # ── (d) Performance by field difficulty tier ──
    ax = axes[3]
    tier_scores = {}
    tier_order = ["EASY", "MEDIUM", "HARD", "HARDEST"]
    tier_colors = [COLORS["green"], COLORS["gold"], COLORS["gpt"], COLORS["highlight"]]

    for tier, fields in FIELD_TIERS.items():
        scores = []
        for f in fields:
            # Try prefixed names
            for prefix in ["sc:", "cr:", "rai:", ""]:
                key = prefix + f if not f.startswith("rai:") else f
                if key in per_field:
                    scores.append(per_field[key])
                    break
        tier_scores[tier] = np.mean(scores) * 100 if scores else 0

    x = range(len(tier_order))
    vals = [tier_scores.get(t, 0) for t in tier_order]
    ax.bar(x, vals, color=tier_colors, edgecolor="white", linewidth=0.5, width=0.6)
    ax.set_xticks(x)
    ax.set_xticklabels(tier_order, fontsize=8)
    ax.set_ylabel("Avg Score (%)")
    ax.set_title("(d) By Difficulty", fontsize=10)
    for i, v in enumerate(vals):
        if v > 0:
            ax.text(i, v + 1, f"{v:.0f}%", ha="center", fontsize=8)

    fig.tight_layout()
    save_fig(fig, "fig5_factors_analysis")


if __name__ == "__main__":
    main()
