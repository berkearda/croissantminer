#!/usr/bin/env python3
"""
Prepare instruction-tuning data for Qwen 2.5 7B LoRA fine-tuning.

Loads extracted metadata + ground truth, pairs with paper text, and outputs
ChatML and Alpaca format JSONL files for training.

Sources (in priority order):
  1. 30-field ground truth (8 benchmark datasets) — gold labels
  2. Pilot annotations (5 pilot datasets) — human-verified extractions
  3. Model extractions (remaining ~100 datasets) — silver labels from Claude

Usage:
    python scripts/prepare_finetuning_data.py
    python scripts/prepare_finetuning_data.py --max-tokens 8192
    python scripts/prepare_finetuning_data.py --gold-only  # only GT examples
"""

import sys
import json
import re
import argparse
import hashlib
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE, MAX_PDF_CHARS

# ═══════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════

PROCESSED_DIR = Path("data/processed")
GT_30FIELD_DIR = Path("data/groundtruth_30field")
RAW_DIR = Path("data/raw")
PAPER_LINKS_FILE = Path("data/paper_links.json")
OUTPUT_BASE = Path("data/finetuning")

BENCHMARK_PDF_MAP = {
    "2012.03411v2": "MLS",
    "2009.03300v3": "MMLU",
    "2106.03193v1": "FLORES",
    "2404.00498v2": "CIFAR",
    "1405.0312v3": "MSCOCO",
    "2311.16502v4": "MMMU",
    "1602.07332v1": "Visual Genome",
    "2310.02255v3": "MathVista",
}

# Reverse: dataset name -> PDF ID
BENCHMARK_NAME_TO_PDF = {v: k for k, v in BENCHMARK_PDF_MAP.items()}

# Domain categories (from prep_annotation_pilot.py structure)
DOMAIN_MAP = {
    # Benchmarks (8)
    "MLS_30field": "speech", "FLORES_30field": "nlp", "CIFAR_30field": "vision",
    "Visual_Genome_30field": "vision", "MSCOCO_30field": "vision",
    "MMLU_30field": "nlp", "MMMU_30field": "multimodal", "MathVista_30field": "multimodal",
    # NLP
    "Rowan_hellaswag": "nlp", "tau_commonsense_qa": "nlp", "allenai_openbookqa": "nlp",
    "lukaemon_bbh": "nlp", "eriktks_conll2003": "nlp", "google_IFEval": "nlp",
    "ceval_ceval-exam": "nlp", "EleutherAI_lambada_openai": "nlp",
    "allenai_winogrande": "nlp", "allenai_math_qa": "nlp",
    "openai_gsm8k": "nlp", "rajpurkar_squad": "nlp", "google_boolq": "nlp",
    "allenai_ai2_arc": "nlp", "truthfulqa_truthful_qa": "nlp",
    # Vision
    "lmms-lab_ChartQA": "vision", "lmms-lab_DocVQA": "vision",
    "lmms-lab_textvqa": "vision", "lmms-lab_POPE": "vision",
    "lmms-lab_ScienceQA": "vision", "uoft-cs_cifar100": "vision",
    "tanganke_eurosat": "vision", "russellyq_VQA": "vision",
    # Code
    "openai_openai_humaneval": "code", "google-research-datasets_mbpp": "code",
    "bigcode_bigcodebench": "code", "deepmind_code_contests": "code",
    "princeton-nlp_SWE-bench": "code",
    # Multimodal
    "Lin-Chen_MMStar": "multimodal", "OpenGVLab_MVBench": "multimodal",
    "lmms-lab_Video-MME": "multimodal", "Idavidrein_gpqa": "multimodal",
    "m-a-p_SuperGPQA": "multimodal",
    # Specialized
    "google_fleurs": "speech", "Cnam-LMSSC_vibravox": "speech",
    "ibrahimhamamci_CT-RATE": "medical", "locuslab_TOFU": "nlp",
    "hiyouga_geometry3k": "multimodal", "IGNF_PASTIS-HD": "vision",
    "callanwu_WebWalkerQA": "nlp", "common-canvas_commoncatalog-cc-by": "vision",
    "MohamedRashad_arabic-books": "nlp",
}

# 30 official Croissant fields
ALL_30_FIELDS = [
    "name", "description", "url", "license", "creator", "publisher",
    "datePublished", "inLanguage", "citeAs", "isLiveDataset",
    "rai:dataCollection", "rai:dataCollectionType", "rai:dataCollectionMissingData",
    "rai:dataCollectionRawData", "rai:dataCollectionTimeframe", "rai:dataImputationProtocol",
    "rai:dataManipulationProtocol", "rai:dataPreprocessingProtocol",
    "rai:dataAnnotationProtocol", "rai:dataAnnotationPlatform", "rai:dataAnnotationAnalysis",
    "rai:annotationsPerItem", "rai:annotatorDemographics", "rai:machineAnnotationTools",
    "rai:dataReleaseMaintenancePlan", "rai:personalSensitiveInformation",
    "rai:dataSocialImpact", "rai:dataBiases", "rai:dataLimitations", "rai:dataUseCases",
]

# Simplified user instruction (shorter than the full template for training)
TRAINING_USER_TEMPLATE = """Extract Croissant metadata from this paper in JSON format. Return all 30 fields (10 general + 20 RAI). Use null for fields not found in the paper.

PAPER TEXT:
{paper_text}"""


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English text."""
    return len(text) // 4


def truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Truncate text to approximately max_tokens."""
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text
    return text[:max_chars]


def load_paper_text(dataset_id: str) -> str:
    """Load and clean paper text for a dataset."""
    from pdf.reader import extract_text_from_pdf
    from pdf.processor import clean_text

    # Try benchmark PDF mapping first
    pdf_id = BENCHMARK_NAME_TO_PDF.get(dataset_id)
    if pdf_id:
        pdf_path = RAW_DIR / f"{pdf_id}.pdf"
    else:
        pdf_path = RAW_DIR / f"{dataset_id}.pdf"

    if not pdf_path.exists():
        return None

    raw_text = extract_text_from_pdf(pdf_path)
    return clean_text(raw_text)


def load_ground_truth():
    """Load 30-field ground truth for benchmark datasets."""
    gt_file = GT_30FIELD_DIR / "all_annotations.json"
    if not gt_file.exists():
        return {}

    with open(gt_file) as f:
        all_gt = json.load(f)

    # Convert GT annotations to clean extraction format
    gt_extractions = {}
    for ds_name, annotations in all_gt.items():
        if not annotations:
            continue

        # Merge annotations: for each field, take the first non-null value
        merged = {}
        for field in ALL_30_FIELDS:
            for ann in annotations:
                # Try with and without sc:/cr: prefix
                for key in [field, f"sc:{field}", f"cr:{field}"]:
                    val = ann.get(key)
                    if val is not None and str(val).strip():
                        # Strip sc:/cr: prefix for output
                        merged[field] = val
                        break
                if field in merged:
                    break

        # Fill missing as null
        for field in ALL_30_FIELDS:
            if field not in merged:
                merged[field] = None

        gt_extractions[ds_name] = merged

    return gt_extractions


def load_model_extractions():
    """Load model extraction results from data/processed/."""
    extractions = {}

    for dataset_dir in sorted(PROCESSED_DIR.iterdir()):
        if not dataset_dir.is_dir():
            continue

        result_file = dataset_dir / "full_pdf_metadata_result.json"
        if not result_file.exists():
            continue

        with open(result_file) as f:
            data = json.load(f)

        # Normalize field names (remove sc:/cr: prefixes if present)
        normalized = {}
        for field in ALL_30_FIELDS:
            for key in [field, f"sc:{field}", f"cr:{field}"]:
                if key in data:
                    normalized[field] = data[key]
                    break
            if field not in normalized:
                normalized[field] = None

        extractions[dataset_dir.name] = normalized

    return extractions


def build_examples(max_tokens: int, gold_only: bool = False):
    """Build instruction-tuning examples."""
    print("Loading data sources...")

    gt = load_ground_truth()
    print(f"  Ground truth: {len(gt)} datasets (30-field)")

    model_extractions = load_model_extractions()
    print(f"  Model extractions: {len(model_extractions)} datasets")

    paper_links = {}
    if PAPER_LINKS_FILE.exists():
        with open(PAPER_LINKS_FILE) as f:
            paper_links = json.load(f)

    examples = []
    stats = {
        "gold_gt": 0,
        "silver_model": 0,
        "skipped_no_pdf": 0,
        "domains": defaultdict(int),
        "input_tokens": [],
        "output_tokens": [],
    }

    # Priority 1: Ground truth examples (8 benchmark datasets)
    for ds_name, gt_extraction in gt.items():
        pdf_id = BENCHMARK_NAME_TO_PDF.get(ds_name)
        if not pdf_id:
            continue

        paper_text = load_paper_text(ds_name)
        if not paper_text:
            stats["skipped_no_pdf"] += 1
            continue

        paper_text = truncate_to_tokens(paper_text, max_tokens)

        # Build the output JSON
        output_json = json.dumps(gt_extraction, indent=2, ensure_ascii=False)

        domain = DOMAIN_MAP.get(f"{ds_name}_30field", "other")
        stats["domains"][domain] += 1
        stats["gold_gt"] += 1

        user_content = TRAINING_USER_TEMPLATE.format(paper_text=paper_text)
        stats["input_tokens"].append(estimate_tokens(SYSTEM_PROMPT) + estimate_tokens(user_content))
        stats["output_tokens"].append(estimate_tokens(output_json))

        examples.append({
            "dataset_id": ds_name,
            "source": "ground_truth",
            "domain": domain,
            "system": SYSTEM_PROMPT,
            "user": user_content,
            "assistant": output_json,
        })

    if gold_only:
        print(f"  --gold-only: using only {len(examples)} ground truth examples")
        return examples, stats

    # Priority 2: Model extraction examples (remaining datasets with PDFs)
    for dataset_id, extraction in model_extractions.items():
        # Skip benchmark datasets (already have GT)
        if dataset_id in BENCHMARK_PDF_MAP:
            continue

        paper_text = load_paper_text(dataset_id)
        if not paper_text:
            stats["skipped_no_pdf"] += 1
            continue

        paper_text = truncate_to_tokens(paper_text, max_tokens)
        output_json = json.dumps(extraction, indent=2, ensure_ascii=False)

        domain = DOMAIN_MAP.get(dataset_id, "other")
        stats["domains"][domain] += 1
        stats["silver_model"] += 1

        user_content = TRAINING_USER_TEMPLATE.format(paper_text=paper_text)
        stats["input_tokens"].append(estimate_tokens(SYSTEM_PROMPT) + estimate_tokens(user_content))
        stats["output_tokens"].append(estimate_tokens(output_json))

        examples.append({
            "dataset_id": dataset_id,
            "source": "model_extraction",
            "domain": domain,
            "system": SYSTEM_PROMPT,
            "user": user_content,
            "assistant": output_json,
        })

    return examples, stats


def split_data(examples, seed=42):
    """Split 80/10/10 with domain stratification."""
    import random
    rng = random.Random(seed)

    # Group by domain
    by_domain = defaultdict(list)
    for ex in examples:
        by_domain[ex["domain"]].append(ex)

    train, val, test = [], [], []

    for domain, domain_examples in by_domain.items():
        rng.shuffle(domain_examples)
        n = len(domain_examples)
        n_val = max(1, round(n * 0.1))
        n_test = max(1, round(n * 0.1))
        n_train = n - n_val - n_test

        if n < 3:
            # Too few — put all in train
            train.extend(domain_examples)
        else:
            train.extend(domain_examples[:n_train])
            val.extend(domain_examples[n_train:n_train + n_val])
            test.extend(domain_examples[n_train + n_val:])

    rng.shuffle(train)
    rng.shuffle(val)
    rng.shuffle(test)

    return train, val, test


def to_chatml(example):
    """Convert to ChatML format."""
    return {
        "messages": [
            {"role": "system", "content": example["system"]},
            {"role": "user", "content": example["user"]},
            {"role": "assistant", "content": example["assistant"]},
        ]
    }


def to_alpaca(example):
    """Convert to Alpaca format."""
    return {
        "instruction": example["system"],
        "input": example["user"],
        "output": example["assistant"],
    }


def sanitize_text(text):
    """Remove surrogate characters that can't be encoded to UTF-8."""
    if isinstance(text, str):
        return text.encode("utf-8", errors="replace").decode("utf-8")
    elif isinstance(text, dict):
        return {k: sanitize_text(v) for k, v in text.items()}
    elif isinstance(text, list):
        return [sanitize_text(v) for v in text]
    return text


def save_jsonl(data, path, formatter):
    """Save list of examples as JSONL with given formatter."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for item in data:
            formatted = sanitize_text(formatter(item))
            f.write(json.dumps(formatted, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Prepare fine-tuning data for CroissantMiner")
    parser.add_argument("--max-tokens", type=int, default=4096,
                        help="Max tokens for paper text truncation (default: 4096)")
    parser.add_argument("--gold-only", action="store_true",
                        help="Only use ground truth examples (no model extractions)")
    args = parser.parse_args()

    print("=" * 70)
    print("PREPARE FINE-TUNING DATA")
    print(f"Max tokens: {args.max_tokens}")
    print("=" * 70)

    # Build examples
    examples, stats = build_examples(args.max_tokens, args.gold_only)

    if not examples:
        print("No examples generated!")
        return

    # Split
    train, val, test = split_data(examples)

    # Save ChatML format
    chatml_dir = OUTPUT_BASE / "chatml"
    save_jsonl(train, chatml_dir / "train.jsonl", to_chatml)
    save_jsonl(val, chatml_dir / "val.jsonl", to_chatml)
    save_jsonl(test, chatml_dir / "test.jsonl", to_chatml)

    # Save Alpaca format
    alpaca_dir = OUTPUT_BASE / "alpaca"
    save_jsonl(train, alpaca_dir / "train.jsonl", to_alpaca)
    save_jsonl(val, alpaca_dir / "val.jsonl", to_alpaca)
    save_jsonl(test, alpaca_dir / "test.jsonl", to_alpaca)

    # Save metadata
    import numpy as np
    input_toks = np.array(stats["input_tokens"])
    output_toks = np.array(stats["output_tokens"])
    total_toks = input_toks + output_toks

    metadata = {
        "max_tokens": args.max_tokens,
        "gold_only": args.gold_only,
        "total_examples": len(examples),
        "split": {"train": len(train), "val": len(val), "test": len(test)},
        "sources": {"ground_truth": stats["gold_gt"], "model_extraction": stats["silver_model"]},
        "domains": dict(stats["domains"]),
        "skipped_no_pdf": stats["skipped_no_pdf"],
        "token_stats": {
            "input": {"mean": float(np.mean(input_toks)), "min": int(np.min(input_toks)),
                      "max": int(np.max(input_toks)), "p50": float(np.median(input_toks)),
                      "p95": float(np.percentile(input_toks, 95))},
            "output": {"mean": float(np.mean(output_toks)), "min": int(np.min(output_toks)),
                       "max": int(np.max(output_toks)), "p50": float(np.median(output_toks)),
                       "p95": float(np.percentile(output_toks, 95))},
            "total": {"mean": float(np.mean(total_toks)), "min": int(np.min(total_toks)),
                      "max": int(np.max(total_toks)), "p50": float(np.median(total_toks)),
                      "p95": float(np.percentile(total_toks, 95))},
        },
    }

    with open(OUTPUT_BASE / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    # Print report
    print(f"\n{'='*70}")
    print("STATISTICS")
    print(f"{'='*70}")
    print(f"\n  Total examples:     {len(examples)}")
    print(f"  Split:              train={len(train)}, val={len(val)}, test={len(test)}")
    print(f"\n  Sources:")
    print(f"    Ground truth:     {stats['gold_gt']} (gold labels)")
    print(f"    Model extraction: {stats['silver_model']} (silver labels)")
    print(f"    Skipped (no PDF): {stats['skipped_no_pdf']}")
    print(f"\n  Domain distribution:")
    for domain, count in sorted(stats["domains"].items(), key=lambda x: -x[1]):
        print(f"    {domain:<15} {count:>4} ({count/len(examples)*100:.0f}%)")
    print(f"\n  Token statistics:")
    print(f"    {'':>12} {'Mean':>8} {'Min':>8} {'Max':>8} {'P50':>8} {'P95':>8}")
    for part in ["input", "output", "total"]:
        s = metadata["token_stats"][part]
        print(f"    {part:<12} {s['mean']:>8.0f} {s['min']:>8} {s['max']:>8} {s['p50']:>8.0f} {s['p95']:>8.0f}")

    print(f"\n  Output directories:")
    print(f"    ChatML: {chatml_dir}/")
    print(f"    Alpaca: {alpaca_dir}/")
    print(f"    Metadata: {OUTPUT_BASE / 'metadata.json'}")


if __name__ == "__main__":
    main()
