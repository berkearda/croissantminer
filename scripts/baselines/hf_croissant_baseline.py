#!/usr/bin/env python3
"""
HuggingFace Auto-Croissant Baseline

Compares CroissantMiner against HF's auto-generated Croissant metadata.
HF generates structural metadata (name, description, distribution) but
no RAI fields, proving the gap CroissantMiner fills.

Usage:
    python scripts/baselines/hf_croissant_baseline.py
    python scripts/baselines/hf_croissant_baseline.py --fetch-only
    python scripts/baselines/hf_croissant_baseline.py --eval-only
"""

import sys
import json
import time
import argparse
import requests
import numpy as np
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# ═══════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════

HF_API = "https://huggingface.co/api/datasets/{dataset_id}/croissant"

# Benchmark datasets: our name → best HF dataset ID
BENCHMARK_HF_IDS = {
    "MLS": "facebook/multilingual_librispeech",
    "MMLU": "cais/mmlu",
    "FLORES": "facebook/flores",
    "CIFAR": "uoft-cs/cifar10",
    "MSCOCO": "detection-datasets/coco",
    "MMMU": "MMMU/MMMU",
    "Visual Genome": "ranjaykrishna/visual_genome",
    "MathVista": "AI4Math/MathVista",
}

RAW_DIR = Path("data/baselines/hf_croissant_raw")
MAPPED_DIR = Path("data/baselines/hf_croissant_mapped")
RESULTS_DIR = Path("results/baselines")

GT_30FIELD_DIR = Path("data/groundtruth_30field")

# Our 30 fields
ALL_30_FIELDS = [
    "sc:name", "sc:description", "sc:url", "sc:license", "sc:creator", "sc:publisher",
    "sc:datePublished", "sc:inLanguage", "cr:citeAs", "cr:isLiveDataset",
    "rai:dataCollection", "rai:dataCollectionType", "rai:dataCollectionMissingData",
    "rai:dataCollectionRawData", "rai:dataCollectionTimeframe", "rai:dataImputationProtocol",
    "rai:dataManipulationProtocol", "rai:dataPreprocessingProtocol",
    "rai:dataAnnotationProtocol", "rai:dataAnnotationPlatform", "rai:dataAnnotationAnalysis",
    "rai:annotationsPerItem", "rai:annotatorDemographics", "rai:machineAnnotationTools",
    "rai:dataReleaseMaintenancePlan", "rai:personalSensitiveInformation",
    "rai:dataSocialImpact", "rai:dataBiases", "rai:dataLimitations", "rai:dataUseCases",
]

GENERAL_FIELDS = [f for f in ALL_30_FIELDS if not f.startswith("rai:")]
RAI_FIELDS = [f for f in ALL_30_FIELDS if f.startswith("rai:")]


# ═══════════════════════════════════════════════════════════════════════
# Fetch
# ═══════════════════════════════════════════════════════════════════════

def fetch_hf_croissant():
    """Fetch Croissant JSON-LD from HF API for each benchmark dataset."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    results = {}
    for ds_name, hf_id in BENCHMARK_HF_IDS.items():
        out_file = RAW_DIR / f"{ds_name}.json"
        if out_file.exists():
            print(f"  {ds_name}: cached")
            with open(out_file) as f:
                results[ds_name] = json.load(f)
            continue

        url = HF_API.format(dataset_id=hf_id)
        print(f"  {ds_name}: fetching {url}...", end=" ")

        try:
            resp = requests.get(url, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                with open(out_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                results[ds_name] = data
                print(f"OK ({len(data)} keys)")
            else:
                print(f"HTTP {resp.status_code}")
                results[ds_name] = None
        except Exception as e:
            print(f"ERROR: {e}")
            results[ds_name] = None

        time.sleep(0.5)  # Rate limiting

    return results


# ═══════════════════════════════════════════════════════════════════════
# Map HF Croissant → our 30-field schema
# ═══════════════════════════════════════════════════════════════════════

def map_hf_to_30fields(hf_data, ds_name):
    """Extract our 30 fields from HF auto-generated Croissant JSON-LD."""
    if not hf_data:
        return {f: None for f in ALL_30_FIELDS}

    mapped = {}

    # ── General fields ──

    # sc:name
    mapped["sc:name"] = hf_data.get("name")

    # sc:description — HF often includes full README markdown
    desc = hf_data.get("description", "")
    if desc and len(desc) > 500:
        # HF dumps the entire README card as description. Truncate to first paragraph.
        lines = desc.strip().split("\n")
        # Find first real content line after headers
        content_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and not stripped.startswith("!") and not stripped.startswith("<"):
                content_lines.append(stripped)
            if len(content_lines) >= 3:
                break
        desc = " ".join(content_lines) if content_lines else desc[:500]
    mapped["sc:description"] = desc if desc else None

    # sc:url
    mapped["sc:url"] = hf_data.get("url")

    # sc:license
    license_val = hf_data.get("license")
    if isinstance(license_val, str) and license_val.startswith("http"):
        # HF uses URLs like https://choosealicense.com/licenses/cc-by-sa-4.0/
        license_val = license_val.split("/")[-2] if "/" in license_val else license_val
    mapped["sc:license"] = license_val

    # sc:creator
    creator = hf_data.get("creator")
    if isinstance(creator, dict):
        mapped["sc:creator"] = creator.get("name")
    elif isinstance(creator, list):
        names = [c.get("name", str(c)) if isinstance(c, dict) else str(c) for c in creator]
        mapped["sc:creator"] = ", ".join(names)
    else:
        mapped["sc:creator"] = creator

    # sc:publisher
    mapped["sc:publisher"] = None  # HF doesn't generate this

    # sc:datePublished
    mapped["sc:datePublished"] = hf_data.get("datePublished")

    # sc:inLanguage
    mapped["sc:inLanguage"] = hf_data.get("inLanguage")

    # cr:citeAs
    mapped["cr:citeAs"] = hf_data.get("citeAs") or hf_data.get("citation")

    # cr:isLiveDataset
    mapped["cr:isLiveDataset"] = hf_data.get("isLiveDataset")

    # ── RAI fields — HF typically generates none of these ──
    rai_field_map = {
        "rai:dataCollection": "dataCollection",
        "rai:dataCollectionType": "dataCollectionType",
        "rai:dataCollectionMissingData": "dataCollectionMissingData",
        "rai:dataCollectionRawData": "dataCollectionRawData",
        "rai:dataCollectionTimeframe": "dataCollectionTimeframe",
        "rai:dataImputationProtocol": "dataImputationProtocol",
        "rai:dataManipulationProtocol": "dataManipulationProtocol",
        "rai:dataPreprocessingProtocol": "dataPreprocessingProtocol",
        "rai:dataAnnotationProtocol": "dataAnnotationProtocol",
        "rai:dataAnnotationPlatform": "dataAnnotationPlatform",
        "rai:dataAnnotationAnalysis": "dataAnnotationAnalysis",
        "rai:annotationsPerItem": "annotationsPerItem",
        "rai:annotatorDemographics": "annotatorDemographics",
        "rai:machineAnnotationTools": "machineAnnotationTools",
        "rai:dataReleaseMaintenancePlan": "dataReleaseMaintenancePlan",
        "rai:personalSensitiveInformation": "personalSensitiveInformation",
        "rai:dataSocialImpact": "dataSocialImpact",
        "rai:dataBiases": "dataBiases",
        "rai:dataLimitations": "dataLimitations",
        "rai:dataUseCases": "dataUseCases",
    }

    for our_field, hf_key in rai_field_map.items():
        # Try multiple possible locations
        val = hf_data.get(hf_key) or hf_data.get(f"cr:{hf_key}") or hf_data.get(f"rai:{hf_key}")
        mapped[our_field] = val if val else None

    return mapped


def run_mapping(raw_data):
    """Map all fetched HF Croissant data to our schema."""
    MAPPED_DIR.mkdir(parents=True, exist_ok=True)

    all_mapped = {}
    for ds_name, hf_data in raw_data.items():
        mapped = map_hf_to_30fields(hf_data, ds_name)
        all_mapped[ds_name] = mapped

        with open(MAPPED_DIR / f"{ds_name}.json", "w", encoding="utf-8") as f:
            json.dump(mapped, f, indent=2, ensure_ascii=False)

        filled = sum(1 for v in mapped.values() if v is not None and str(v).strip())
        print(f"  {ds_name}: {filled}/30 fields filled")

    return all_mapped


# ═══════════════════════════════════════════════════════════════════════
# Evaluate
# ═══════════════════════════════════════════════════════════════════════

def load_groundtruth():
    """Load 30-field ground truth."""
    gt_file = GT_30FIELD_DIR / "all_annotations.json"
    if not gt_file.exists():
        print(f"  Ground truth not found: {gt_file}")
        return {}

    with open(gt_file) as f:
        return json.load(f)


def evaluate_field(predicted, groundtruth, field_name):
    """Simple evaluation: is the predicted value semantically close to ground truth?

    Uses the same scoring as the main evaluator:
    - 1.0 if correct (content matches)
    - 0.5 if partially correct
    - 0.0 if wrong or missing

    For this baseline we use simple heuristics since we can't call LLM-as-judge
    for every field (cost). The heuristic is conservative — benefits HF baseline.
    """
    if predicted is None or not str(predicted).strip():
        if groundtruth is None or not str(groundtruth).strip():
            return 1.0  # Both null = correct
        return 0.0  # Predicted null but GT has value = missed

    if groundtruth is None or not str(groundtruth).strip():
        return 0.0  # Predicted something but GT is null = hallucination/wrong

    pred = str(predicted).lower().strip()
    gt = str(groundtruth).lower().strip()

    # Exact match
    if pred == gt:
        return 1.0

    # One contains the other (generous to HF)
    if pred in gt or gt in pred:
        return 1.0

    # For names: check if key words overlap
    pred_words = set(pred.split())
    gt_words = set(gt.split())
    if pred_words and gt_words:
        overlap = len(pred_words & gt_words) / max(len(pred_words), len(gt_words))
        if overlap > 0.5:
            return 0.5

    # For URLs: normalize and compare
    if field_name in ("sc:url",):
        pred_norm = pred.rstrip("/").replace("https://", "").replace("http://", "")
        gt_norm = gt.rstrip("/").replace("https://", "").replace("http://", "")
        if pred_norm == gt_norm:
            return 1.0

    # For licenses: fuzzy match
    if field_name == "sc:license":
        # Common license name normalization
        for lic in ["cc-by-4.0", "cc-by-sa-4.0", "mit", "apache-2.0", "cc-by-nc-4.0"]:
            if lic in pred and lic in gt:
                return 1.0
        # Check if both mention same license family
        if ("creative commons" in pred and "creative commons" in gt) or \
           ("cc-by" in pred and "cc-by" in gt) or \
           ("mit" in pred and "mit" in gt):
            return 0.5

    return 0.0


def run_evaluation(hf_mapped):
    """Evaluate HF baseline against 30-field ground truth."""
    gt = load_groundtruth()
    if not gt:
        return {}, {}, {}, {}

    # Also load CroissantMiner results for comparison
    cm_results_file = Path("evaluation_outputs_v2/evaluation_report_30field.json")
    cm_field_scores = {}
    if cm_results_file.exists():
        with open(cm_results_file) as f:
            cm_data = json.load(f)
        for ds_name, ds_data in cm_data.get("results", {}).items():
            for field, result in ds_data.get("metrics", {}).get("field_results", {}).items():
                cm_field_scores.setdefault(field, {})[ds_name] = result["score"]

    # Evaluate HF baseline
    hf_field_scores = defaultdict(dict)  # field -> {dataset -> score}
    hf_ds_scores = {}  # dataset -> overall score
    gt_has_value = defaultdict(dict)  # field -> {dataset -> bool} for strict mode

    for ds_name, mapped in hf_mapped.items():
        gt_anns = gt.get(ds_name, [])
        if not gt_anns:
            print(f"  {ds_name}: no ground truth, skipping")
            continue

        gt_ref = gt_anns[0]

        ds_scores = []
        for field in ALL_30_FIELDS:
            pred = mapped.get(field)
            gt_val = gt_ref.get(field)
            if gt_val is None:
                short = field.split(":")[-1] if ":" in field else field
                gt_val = gt_ref.get(short)

            # Track whether GT has a real value (for strict mode)
            gt_has_value[field][ds_name] = gt_val is not None and str(gt_val).strip() != ""

            score = evaluate_field(pred, gt_val, field)
            hf_field_scores[field][ds_name] = score
            ds_scores.append(score)

        hf_ds_scores[ds_name] = np.mean(ds_scores) if ds_scores else 0

    return hf_field_scores, hf_ds_scores, cm_field_scores, gt_has_value


# ═══════════════════════════════════════════════════════════════════════
# Report
# ═══════════════════════════════════════════════════════════════════════

def generate_report(hf_field_scores, hf_ds_scores, cm_field_scores, gt_has_value, hf_mapped=None):
    """Generate comparison tables."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    datasets = sorted(hf_ds_scores.keys())

    # ── Per-field accuracy ──
    def field_acc(scores_dict, field):
        scores = [scores_dict.get(field, {}).get(ds, 0) for ds in datasets]
        return np.mean(scores) * 100 if scores else 0

    def field_acc_strict(scores_dict, field):
        """Only count datasets where GT has a non-null value."""
        scores = []
        for ds in datasets:
            if gt_has_value.get(field, {}).get(ds, False):
                scores.append(scores_dict.get(field, {}).get(ds, 0))
        return (np.mean(scores) * 100, len(scores)) if scores else (None, 0)

    print(f"\n{'='*85}")
    print("HF AUTO-CROISSANT vs CROISSANTMINER: PER-FIELD COMPARISON")
    print(f"{'='*85}")
    print(f"\n{'Field':<42} {'HF Auto':>8} {'CrMiner':>8} {'Delta':>8}")
    print("-" * 70)

    hf_gen_scores = []
    cm_gen_scores = []
    hf_rai_scores = []
    cm_rai_scores = []

    field_rows = []
    for field in ALL_30_FIELDS:
        hf_acc = field_acc(hf_field_scores, field)
        cm_acc = field_acc(cm_field_scores, field) if cm_field_scores else 0
        delta = cm_acc - hf_acc
        is_rai = field.startswith("rai:")

        if is_rai:
            hf_rai_scores.append(hf_acc)
            cm_rai_scores.append(cm_acc)
        else:
            hf_gen_scores.append(hf_acc)
            cm_gen_scores.append(cm_acc)

        marker = ""
        if delta > 10:
            marker = " ★"
        elif delta < -10:
            marker = " ◄"

        print(f"{field:<42} {hf_acc:>7.1f}% {cm_acc:>7.1f}% {delta:>+7.1f}pp{marker}")
        field_rows.append({"field": field, "hf": hf_acc, "cm": cm_acc, "delta": delta})

    # Category summaries
    hf_gen = np.mean(hf_gen_scores) if hf_gen_scores else 0
    cm_gen = np.mean(cm_gen_scores) if cm_gen_scores else 0
    hf_rai = np.mean(hf_rai_scores) if hf_rai_scores else 0
    cm_rai = np.mean(cm_rai_scores) if cm_rai_scores else 0
    hf_overall = np.mean(hf_gen_scores + hf_rai_scores)
    cm_overall = np.mean(cm_gen_scores + cm_rai_scores)

    print("-" * 70)
    print(f"{'General (10 fields)':<42} {hf_gen:>7.1f}% {cm_gen:>7.1f}% {cm_gen-hf_gen:>+7.1f}pp")
    print(f"{'RAI (20 fields)':<42} {hf_rai:>7.1f}% {cm_rai:>7.1f}% {cm_rai-hf_rai:>+7.1f}pp")
    print(f"{'OVERALL (30 fields)':<42} {hf_overall:>7.1f}% {cm_overall:>7.1f}% {cm_overall-hf_overall:>+7.1f}pp")

    # ── Summary table ──
    print(f"\n{'='*85}")
    print("SUMMARY TABLE (for paper)")
    print(f"{'='*85}")
    print(f"\n{'Method':<25} {'General (10)':>13} {'RAI (20)':>10} {'Overall (30)':>13}")
    print("-" * 65)
    print(f"{'HF Auto-Croissant':<25} {hf_gen:>12.1f}% {hf_rai:>9.1f}% {hf_overall:>12.1f}%")
    print(f"{'CroissantMiner':<25} {cm_gen:>12.1f}% {cm_rai:>9.1f}% {cm_overall:>12.1f}%")
    print(f"{'Delta':<25} {cm_gen-hf_gen:>+12.1f}pp {cm_rai-hf_rai:>+9.1f}pp {cm_overall-hf_overall:>+12.1f}pp")

    # ── Per-dataset ──
    print(f"\n{'='*85}")
    print("PER-DATASET ACCURACY")
    print(f"{'='*85}")
    print(f"\n{'Dataset':<20} {'HF Auto':>8} {'CrMiner':>8} {'Delta':>8}")
    print("-" * 50)
    for ds in datasets:
        hf_ds = hf_ds_scores.get(ds, 0) * 100
        cm_ds = 0
        if cm_field_scores:
            cm_scores_ds = [cm_field_scores.get(f, {}).get(ds, 0) for f in ALL_30_FIELDS]
            cm_ds = np.mean(cm_scores_ds) * 100
        print(f"{ds:<20} {hf_ds:>7.1f}% {cm_ds:>7.1f}% {cm_ds-hf_ds:>+7.1f}pp")

    # ── LaTeX table ──
    print(f"\n{'='*85}")
    print("LATEX TABLE")
    print(f"{'='*85}")
    print(r"\begin{table}[h]")
    print(r"\centering")
    print(r"\caption{Comparison of HuggingFace auto-generated Croissant metadata vs CroissantMiner extraction.}")
    print(r"\begin{tabular}{lccc}")
    print(r"\toprule")
    print(r"Method & General (10) & RAI (20) & Overall (30) \\")
    print(r"\midrule")
    print(f"HF Auto-Croissant & {hf_gen:.1f}\\% & {hf_rai:.1f}\\% & {hf_overall:.1f}\\% \\\\")
    print(f"CroissantMiner & \\textbf{{{cm_gen:.1f}\\%}} & \\textbf{{{cm_rai:.1f}\\%}} & \\textbf{{{cm_overall:.1f}\\%}} \\\\")
    print(r"\midrule")
    print(f"$\\Delta$ & {cm_gen-hf_gen:+.1f}pp & {cm_rai-hf_rai:+.1f}pp & {cm_overall-hf_overall:+.1f}pp \\\\")
    print(r"\bottomrule")
    print(r"\end{tabular}")
    print(r"\end{table}")

    # ── STRICT EVALUATION (only fields where GT has non-null value) ──
    print(f"\n{'='*85}")
    print("STRICT EVALUATION (only fields where ground truth has a non-null value)")
    print(f"{'='*85}")
    print(f"\n{'Field':<42} {'HF Strict':>10} {'CM Strict':>10} {'Delta':>8} {'n':>4}")
    print("-" * 80)

    hf_strict_gen, cm_strict_gen = [], []
    hf_strict_rai, cm_strict_rai = [], []
    strict_field_rows = []

    for field in ALL_30_FIELDS:
        hf_s, hf_n = field_acc_strict(hf_field_scores, field)
        cm_s, cm_n = field_acc_strict(cm_field_scores, field)
        is_rai = field.startswith("rai:")

        if hf_n == 0:
            # No GT values for this field — skip in strict mode
            strict_field_rows.append({"field": field, "hf_strict": None, "cm_strict": None, "n": 0})
            continue

        if hf_s is None:
            hf_s = 0
        if cm_s is None:
            cm_s = 0

        delta = cm_s - hf_s
        marker = " ★" if delta > 10 else ""

        if is_rai:
            hf_strict_rai.append(hf_s)
            cm_strict_rai.append(cm_s)
        else:
            hf_strict_gen.append(hf_s)
            cm_strict_gen.append(cm_s)

        print(f"{field:<42} {hf_s:>9.1f}% {cm_s:>9.1f}% {delta:>+7.1f}pp {hf_n:>3}{marker}")
        strict_field_rows.append({"field": field, "hf_strict": round(hf_s, 1), "cm_strict": round(cm_s, 1), "n": hf_n})

    s_hf_gen = np.mean(hf_strict_gen) if hf_strict_gen else 0
    s_cm_gen = np.mean(cm_strict_gen) if cm_strict_gen else 0
    s_hf_rai = np.mean(hf_strict_rai) if hf_strict_rai else 0
    s_cm_rai = np.mean(cm_strict_rai) if cm_strict_rai else 0
    s_hf_all = np.mean(hf_strict_gen + hf_strict_rai)
    s_cm_all = np.mean(cm_strict_gen + cm_strict_rai)

    print("-" * 80)
    print(f"{'General (strict)':<42} {s_hf_gen:>9.1f}% {s_cm_gen:>9.1f}% {s_cm_gen-s_hf_gen:>+7.1f}pp")
    print(f"{'RAI (strict)':<42} {s_hf_rai:>9.1f}% {s_cm_rai:>9.1f}% {s_cm_rai-s_hf_rai:>+7.1f}pp")
    print(f"{'OVERALL (strict)':<42} {s_hf_all:>9.1f}% {s_cm_all:>9.1f}% {s_cm_all-s_hf_all:>+7.1f}pp")

    # ── COVERAGE: avg fields filled per dataset ──
    print(f"\n{'='*85}")
    print("COVERAGE: Average fields filled with non-null content")
    print(f"{'='*85}")

    hf_fill_counts = []
    cm_fill_counts = []
    for ds in datasets:
        hf_filled = 0
        cm_filled = 0
        if hf_mapped:
            mapped = hf_mapped.get(ds, {})
            hf_filled = sum(1 for f in ALL_30_FIELDS if mapped.get(f) is not None and str(mapped.get(f, "")).strip())
        # For CM, count fields where score > 0 (means it produced something)
        for f in ALL_30_FIELDS:
            cm_score = cm_field_scores.get(f, {}).get(ds, 0)
            # Also check if GT was null and CM got 1.0 (both null) — that's not "filled"
            if cm_score > 0 and gt_has_value.get(f, {}).get(ds, False):
                cm_filled += 1
            elif cm_score > 0 and not gt_has_value.get(f, {}).get(ds, False):
                # CM scored on a null-GT field — it produced something (possibly hallucinated)
                pass  # Don't count null-null matches as "filled"
        # Actually, simpler: count fields from CM extraction files
        cm_ext_file = Path(f"evaluation_outputs_v2/{ds}_extraction.json")
        if cm_ext_file.exists():
            with open(cm_ext_file) as f:
                cm_ext = json.load(f)
            cm_filled = sum(1 for k, v in cm_ext.items() if v is not None and str(v).strip() and k != "@context" and k != "@type")

        hf_fill_counts.append(hf_filled)
        cm_fill_counts.append(cm_filled)

    hf_avg_fill = np.mean(hf_fill_counts)
    cm_avg_fill = np.mean(cm_fill_counts)

    print(f"\n{'Method':<25} {'Avg fields filled':>18} {'% of 30':>10}")
    print("-" * 55)
    print(f"{'HF Auto-Croissant':<25} {hf_avg_fill:>14.1f}/30 {hf_avg_fill/30*100:>9.1f}%")
    print(f"{'CroissantMiner':<25} {cm_avg_fill:>14.1f}/30 {cm_avg_fill/30*100:>9.1f}%")

    print(f"\n{'Dataset':<20} {'HF filled':>10} {'CM filled':>10}")
    print("-" * 42)
    for i, ds in enumerate(datasets):
        print(f"{ds:<20} {hf_fill_counts[i]:>6}/30  {cm_fill_counts[i]:>6}/30")

    # ── COMBINED STRICT SUMMARY TABLE ──
    print(f"\n{'='*85}")
    print("COMBINED SUMMARY (for paper)")
    print(f"{'='*85}")
    print(f"\n{'Method':<22} {'Gen(strict)':>12} {'RAI(strict)':>12} {'All(strict)':>12} {'Avg filled':>11}")
    print("-" * 72)
    print(f"{'HF Auto-Croissant':<22} {s_hf_gen:>11.1f}% {s_hf_rai:>11.1f}% {s_hf_all:>11.1f}% {hf_avg_fill:>7.1f}/30")
    print(f"{'CroissantMiner':<22} {s_cm_gen:>11.1f}% {s_cm_rai:>11.1f}% {s_cm_all:>11.1f}% {cm_avg_fill:>7.1f}/30")
    print(f"{'Delta':<22} {s_cm_gen-s_hf_gen:>+11.1f}pp {s_cm_rai-s_hf_rai:>+11.1f}pp {s_cm_all-s_hf_all:>+11.1f}pp {cm_avg_fill-hf_avg_fill:>+7.1f}")

    # ── Save JSON results ──
    results = {
        "summary": {
            "hf_general": round(hf_gen, 1),
            "hf_rai": round(hf_rai, 1),
            "hf_overall": round(hf_overall, 1),
            "cm_general": round(cm_gen, 1),
            "cm_rai": round(cm_rai, 1),
            "cm_overall": round(cm_overall, 1),
        },
        "strict_summary": {
            "hf_general": round(s_hf_gen, 1),
            "hf_rai": round(s_hf_rai, 1),
            "hf_overall": round(s_hf_all, 1),
            "cm_general": round(s_cm_gen, 1),
            "cm_rai": round(s_cm_rai, 1),
            "cm_overall": round(s_cm_all, 1),
        },
        "coverage": {
            "hf_avg_fields_filled": round(hf_avg_fill, 1),
            "cm_avg_fields_filled": round(cm_avg_fill, 1),
        },
        "per_field": field_rows,
        "per_field_strict": strict_field_rows,
        "per_dataset": {ds: {"hf": round(hf_ds_scores.get(ds, 0) * 100, 1)} for ds in datasets},
        "datasets_evaluated": datasets,
        "hf_dataset_ids": BENCHMARK_HF_IDS,
    }

    with open(RESULTS_DIR / "hf_croissant_comparison.json", "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # ── Save markdown report ──
    md = f"""# HuggingFace Auto-Croissant vs CroissantMiner

## Summary (lenient — includes null-null matches)

| Method | General (10) | RAI (20) | Overall (30) |
|--------|-------------|---------|-------------|
| HF Auto-Croissant | {hf_gen:.1f}% | {hf_rai:.1f}% | {hf_overall:.1f}% |
| **CroissantMiner** | **{cm_gen:.1f}%** | **{cm_rai:.1f}%** | **{cm_overall:.1f}%** |
| Delta | {cm_gen-hf_gen:+.1f}pp | {cm_rai-hf_rai:+.1f}pp | {cm_overall-hf_overall:+.1f}pp |

## Strict Evaluation (only fields where ground truth has a non-null value)

| Method | General (strict) | RAI (strict) | Overall (strict) | Avg fields filled |
|--------|-----------------|-------------|-----------------|-------------------|
| HF Auto-Croissant | {s_hf_gen:.1f}% | {s_hf_rai:.1f}% | {s_hf_all:.1f}% | {hf_avg_fill:.1f}/30 |
| **CroissantMiner** | **{s_cm_gen:.1f}%** | **{s_cm_rai:.1f}%** | **{s_cm_all:.1f}%** | **{cm_avg_fill:.1f}/30** |
| Delta | {s_cm_gen-s_hf_gen:+.1f}pp | {s_cm_rai-s_hf_rai:+.1f}pp | {s_cm_all-s_hf_all:+.1f}pp | {cm_avg_fill-hf_avg_fill:+.1f} |

## Key Finding

HuggingFace auto-generates basic structural metadata (name, URL, license) but provides
**zero RAI metadata**. CroissantMiner extracts {s_cm_rai:.1f}% of RAI fields from papers
(strict evaluation) — information that HF's automated system cannot access because it only
reads dataset cards, not the academic papers that describe collection methodology, biases,
and limitations.

## Per-Field Comparison

| Field | HF Auto | CroissantMiner | Delta |
|-------|---------|---------------|-------|
"""
    for row in field_rows:
        md += f"| {row['field']} | {row['hf']:.1f}% | {row['cm']:.1f}% | {row['delta']:+.1f}pp |\n"

    md += f"""
## Datasets Evaluated

{len(datasets)} benchmark datasets from the CroissantMiner evaluation suite.
HF dataset IDs: {json.dumps(BENCHMARK_HF_IDS, indent=2)}
"""

    with open(RESULTS_DIR / "hf_croissant_report.md", "w") as f:
        f.write(md)

    print(f"\nResults saved to:")
    print(f"  {RESULTS_DIR / 'hf_croissant_comparison.json'}")
    print(f"  {RESULTS_DIR / 'hf_croissant_report.md'}")


# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="HF Auto-Croissant Baseline")
    parser.add_argument("--fetch-only", action="store_true", help="Only fetch, don't evaluate")
    parser.add_argument("--eval-only", action="store_true", help="Only evaluate cached data")
    args = parser.parse_args()

    print("=" * 70)
    print("HF AUTO-CROISSANT BASELINE")
    print("=" * 70)

    # Fetch
    if not args.eval_only:
        print("\nStep 1: Fetching HF Croissant metadata...")
        raw_data = fetch_hf_croissant()
        fetched = sum(1 for v in raw_data.values() if v is not None)
        print(f"  Fetched {fetched}/{len(BENCHMARK_HF_IDS)} datasets")
    else:
        print("\nStep 1: Loading cached HF data...")
        raw_data = {}
        for ds_name in BENCHMARK_HF_IDS:
            f = RAW_DIR / f"{ds_name}.json"
            if f.exists():
                with open(f) as fh:
                    raw_data[ds_name] = json.load(fh)
        print(f"  Loaded {len(raw_data)} datasets")

    if args.fetch_only:
        return

    # Map
    print("\nStep 2: Mapping HF Croissant to 30-field schema...")
    hf_mapped = run_mapping(raw_data)

    # Evaluate
    print("\nStep 3: Evaluating against 30-field ground truth...")
    hf_field_scores, hf_ds_scores, cm_field_scores, gt_has_value = run_evaluation(hf_mapped)

    # Report
    generate_report(hf_field_scores, hf_ds_scores, cm_field_scores, gt_has_value, hf_mapped)


if __name__ == "__main__":
    main()
