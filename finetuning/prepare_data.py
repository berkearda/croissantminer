#!/usr/bin/env python3
"""
6a: Training Data Preparation for Fine-Tuning

Loads Phase 2 annotations + Claude extractions + paper texts,
constructs per-dataset GT JSONs, creates train/test split,
and formats as chat-style JSONL for Qwen fine-tuning.

GT construction rules:
  - Rated Correct (1):           GT = Claude's extraction
  - Rated Partially Correct (2): GT = Claude's extraction (mostly right)
  - Rated Incorrect (3) + correction provided: GT = annotator's correction
  - Rated Incorrect (3) + no correction:       GT = null (unknown)
  - No annotation for field:     GT = Claude's extraction (unverified)

Usage:
  python finetuning/prepare_data.py
  python finetuning/prepare_data.py --annotations /path/to/sheets
  python finetuning/prepare_data.py --test-ratio 0.2
"""

import argparse
import json
import logging
import os
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

import fitz  # PyMuPDF
import openpyxl

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from config import SYSTEM_PROMPT
from validation.validate_extraction import CANONICAL_FIELDS

# ═══════════════════════════════════════════════════════════════════════
# Config
# ═══════════════════════════════════════════════════════════════════════

PAPER_LINKS = ROOT / "data" / "paper_links.json"
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
DEFAULT_ANNOTATION_DIR = Path(os.environ.get("ANNOTATION_SHEETS_DIR", "data/annotations/phase2"))
OUTPUT_DIR = ROOT / "finetuning" / "data"

DROPOUTS = {"annotator", "annotator", "annotator"}
MAX_SEQ_LENGTH = 8192  # tokens (approximate)
SEED = 42

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("prepare_data")

# ═══════════════════════════════════════════════════════════════════════
# PDF helper
# ═══════════════════════════════════════════════════════════════════════


def find_pdf(ds_id: str) -> Path:
    pdf = RAW_DIR / f"{ds_id}.pdf"
    if pdf.exists():
        return pdf
    BENCHMARK_MAP = {
        "CIFAR_30field": "2404.00498v2", "FLORES_30field": "2106.03193v1",
        "MLS_30field": "2012.03411v2", "MMLU_30field": "2009.03300v3",
        "MMMU_30field": "2311.16502v4", "MSCOCO_30field": "1405.0312v3",
        "MathVista_30field": "2310.02255v3", "Visual_Genome_30field": "1602.07332v1",
    }
    if ds_id in BENCHMARK_MAP:
        for base in [RAW_DIR, ROOT / "data"]:
            p = base / f"{BENCHMARK_MAP[ds_id]}.pdf"
            if p.exists():
                return p
    return None


def extract_text(pdf_path: Path, max_chars: int = 200000) -> str:
    doc = fitz.open(pdf_path)
    pages = [page.get_text() for page in doc]
    doc.close()
    text = "\n".join(pages)
    return text[:max_chars]


# ═══════════════════════════════════════════════════════════════════════
# Domain inference (for stratified split)
# ═══════════════════════════════════════════════════════════════════════


def infer_domain(desc: str) -> str:
    if not desc:
        return "other"
    d = desc.lower()
    if any(k in d for k in ["image", "vision", "visual", "video"]):
        return "vision"
    if any(k in d for k in ["code", "programming", "software"]):
        return "code"
    if any(k in d for k in ["math", "arithmetic", "geometry"]):
        return "math"
    if any(k in d for k in ["speech", "audio", "voice"]):
        return "speech"
    if any(k in d for k in ["medical", "clinical", "health"]):
        return "medical"
    if any(k in d for k in ["question answering", "qa", "comprehension"]):
        return "qa"
    if any(k in d for k in ["text", "nlp", "language", "corpus"]):
        return "nlp"
    return "other"


# ═══════════════════════════════════════════════════════════════════════
# Annotation loading
# ═══════════════════════════════════════════════════════════════════════


def load_annotations(annotation_dir: Path) -> dict:
    """Load all Phase 2 annotations.

    Returns:
        {(dataset, field): {"rating": int, "corrected": str|None, "annotator": str}}
        If multiple annotators, uses majority rating. If disagreement, prefer correction.
    """
    # Collect all ratings per (dataset, field) pair
    pair_ratings = defaultdict(list)

    for f in sorted(annotation_dir.glob("Phase2_*.xlsx")):
        aname = f.stem.replace("Phase2_", "").replace("_", " ")
        if f.stem.replace("Phase2_", "") in DROPOUTS:
            continue

        wb = openpyxl.load_workbook(f, read_only=True, data_only=True)
        if "Annotations" not in wb.sheetnames:
            wb.close()
            continue
        ws = wb["Annotations"]

        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row or len(row) < 6 or row[0] is None:
                continue
            dataset = str(row[1]).strip() if row[1] else None
            field = str(row[3]).strip() if len(row) > 3 and row[3] else None
            rating_raw = row[5] if len(row) > 5 else None
            corrected = str(row[7]).strip() if len(row) > 7 and row[7] and str(row[7]).strip() else None

            if not dataset or not field or field == "`":
                continue

            rating_val = None
            if rating_raw:
                r = str(rating_raw).strip()
                if r.startswith("1"): rating_val = 1
                elif r.startswith("2"): rating_val = 2
                elif r.startswith("3"): rating_val = 3

            if rating_val is not None:
                pair_ratings[(dataset, field)].append({
                    "rating": rating_val,
                    "corrected": corrected,
                    "annotator": aname,
                })

        wb.close()

    # Resolve multiple annotators: majority rating, prefer corrections
    resolved = {}
    for (ds, field), ratings in pair_ratings.items():
        if len(ratings) == 1:
            resolved[(ds, field)] = ratings[0]
        else:
            # Majority rating
            rating_counts = Counter(r["rating"] for r in ratings)
            majority_rating = rating_counts.most_common(1)[0][0]

            # If majority says Incorrect, find a correction
            correction = None
            if majority_rating == 3:
                for r in ratings:
                    if r["rating"] == 3 and r["corrected"]:
                        correction = r["corrected"]
                        break

            resolved[(ds, field)] = {
                "rating": majority_rating,
                "corrected": correction,
                "annotator": "majority",
            }

    return resolved


# ═══════════════════════════════════════════════════════════════════════
# GT construction
# ═══════════════════════════════════════════════════════════════════════


def construct_gt(claude_extraction: dict, annotations: dict, ds_id: str) -> dict:
    """Construct ground truth JSON for a dataset.

    Args:
        claude_extraction: Claude's original 30-field extraction
        annotations: resolved annotations {(dataset, field): {...}}
        ds_id: dataset ID

    Returns:
        GT dict with 30 fields
    """
    gt = {}

    for field in sorted(CANONICAL_FIELDS):
        claude_val = claude_extraction.get(field)
        ann = annotations.get((ds_id, field))

        if ann is None:
            # No annotation → use Claude's value (unverified)
            gt[field] = claude_val
        elif ann["rating"] == 1:
            # Correct → Claude's value is the GT
            gt[field] = claude_val
        elif ann["rating"] == 2:
            # Partially Correct → Claude's value (mostly right)
            gt[field] = claude_val
        elif ann["rating"] == 3:
            # Incorrect
            if ann["corrected"]:
                # Has correction → use correction
                gt[field] = ann["corrected"]
            else:
                # No correction → null (unknown GT)
                gt[field] = None

    return gt


# ═══════════════════════════════════════════════════════════════════════
# JSONL formatting
# ═══════════════════════════════════════════════════════════════════════


def format_example(paper_text: str, gt_json: dict) -> dict:
    """Format a single training example as chat-style JSONL."""
    user_content = (
        "Extract metadata from the following academic paper. "
        "Return a JSON object with all 30 Croissant metadata fields.\n\n"
        f"PAPER TEXT:\n{paper_text}"
    )

    assistant_content = json.dumps(gt_json, indent=2, ensure_ascii=False)

    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": assistant_content},
        ]
    }


# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(description="Prepare fine-tuning data")
    parser.add_argument("--annotations", type=Path, default=DEFAULT_ANNOTATION_DIR)
    parser.add_argument("--test-ratio", type=float, default=0.2)
    parser.add_argument("--max-paper-chars", type=int, default=150000,
                        help="Max paper text chars (leave room for prompt/output)")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    random.seed(SEED)

    # Load corpus
    with open(PAPER_LINKS) as f:
        paper_links = json.load(f)
    dataset_ids = sorted(paper_links.keys())
    log.info(f"Corpus: {len(dataset_ids)} datasets")

    # Load annotations
    log.info(f"Loading annotations from {args.annotations}...")
    annotations = load_annotations(args.annotations)
    log.info(f"  Resolved annotation pairs: {len(annotations)}")

    # Build examples
    examples = []
    skipped = 0
    field_null_counts = Counter()
    field_corrected_counts = Counter()
    domains = []

    for ds_id in dataset_ids:
        # Load Claude extraction
        ext_path = PROCESSED_DIR / ds_id / "full_pdf_metadata_result.json"
        if not ext_path.exists():
            skipped += 1
            continue

        with open(ext_path) as f:
            claude_ext = json.load(f)

        # Load paper text
        pdf_path = find_pdf(ds_id)
        if not pdf_path:
            skipped += 1
            continue

        paper_text = extract_text(pdf_path, max_chars=args.max_paper_chars)
        if len(paper_text) < 100:
            skipped += 1
            continue

        # Construct GT
        gt = construct_gt(claude_ext, annotations, ds_id)

        # Track stats
        for field in CANONICAL_FIELDS:
            if gt[field] is None:
                field_null_counts[field] += 1
            if annotations.get((ds_id, field), {}).get("corrected"):
                field_corrected_counts[field] += 1

        domain = infer_domain(claude_ext.get("description", ""))
        domains.append(domain)

        examples.append({
            "ds_id": ds_id,
            "domain": domain,
            "example": format_example(paper_text, gt),
        })

    log.info(f"Built {len(examples)} examples, skipped {skipped}")

    # Stratified train/test split
    domain_groups = defaultdict(list)
    for ex in examples:
        domain_groups[ex["domain"]].append(ex)

    train = []
    test = []
    for domain, group in domain_groups.items():
        random.shuffle(group)
        n_test = max(1, int(len(group) * args.test_ratio))
        test.extend(group[:n_test])
        train.extend(group[n_test:])

    random.shuffle(train)
    random.shuffle(test)

    # Save JSONL
    train_path = OUTPUT_DIR / "train.jsonl"
    test_path = OUTPUT_DIR / "test.jsonl"

    with open(train_path, "w") as f:
        for ex in train:
            f.write(json.dumps(ex["example"], ensure_ascii=False) + "\n")

    with open(test_path, "w") as f:
        for ex in test:
            f.write(json.dumps(ex["example"], ensure_ascii=False) + "\n")

    # Statistics
    log.info(f"\n{'='*60}")
    log.info(f"STATISTICS")
    log.info(f"{'='*60}")
    log.info(f"  Total examples: {len(examples)}")
    log.info(f"  Train: {len(train)}, Test: {len(test)}")
    log.info(f"  Train file: {train_path} ({train_path.stat().st_size // 1024} KB)")
    log.info(f"  Test file: {test_path} ({test_path.stat().st_size // 1024} KB)")

    log.info(f"\n  Domain distribution:")
    for domain, count in Counter(domains).most_common():
        log.info(f"    {domain}: {count}")

    log.info(f"\n  Annotation coverage:")
    annotated_datasets = set(ds for (ds, _) in annotations.keys())
    log.info(f"    Datasets with any annotation: {len(annotated_datasets)}/{len(dataset_ids)}")
    log.info(f"    Total annotated (dataset, field) pairs: {len(annotations)}")
    log.info(f"    Fields with corrections: {sum(field_corrected_counts.values())}")

    log.info(f"\n  Null rate per field (top 5):")
    for field, count in field_null_counts.most_common(5):
        log.info(f"    {field}: {count}/{len(examples)} ({count / len(examples) * 100:.0f}%)")

    # Verify output format
    with open(train_path) as f:
        first = json.loads(f.readline())
    assert "messages" in first
    assert len(first["messages"]) == 3
    assert first["messages"][0]["role"] == "system"
    assert first["messages"][1]["role"] == "user"
    assert first["messages"][2]["role"] == "assistant"
    log.info(f"\n  Format verified: chat-style JSONL ✓")


if __name__ == "__main__":
    main()
