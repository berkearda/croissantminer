#!/usr/bin/env python3
"""
Source Ablation: Paper-only vs Card-only vs Combined.

Tests whether metadata is better extracted from the academic paper,
the HuggingFace dataset card, or both combined.

Usage:
    python scripts/run_source_ablation.py
    python scripts/run_source_ablation.py --extract-only
    python scripts/run_source_ablation.py --eval-only
"""

import sys
import json
import time
import re
import argparse
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE, MAX_PDF_CHARS

BENCHMARK_MAP = {
    "2012.03411v2": ("MLS", "facebook/multilingual_librispeech"),
    "2009.03300v3": ("MMLU", "cais/mmlu"),
    "2106.03193v1": ("FLORES", "facebook/flores"),
    "2404.00498v2": ("CIFAR", "uoft-cs/cifar10"),
    "1405.0312v3": ("MSCOCO", "detection-datasets/coco"),
    "2311.16502v4": ("MMMU", "MMMU/MMMU"),
    "1602.07332v1": ("Visual Genome", "ranjaykrishna/visual_genome"),
    "2310.02255v3": ("MathVista", "AI4Math/MathVista"),
}

RAW_DIR = Path("data/raw")
OUT_BASE = Path("results/ablations/source_ablation")
CARDS_DIR = OUT_BASE / "cards_raw"
GT_PATH = "data/groundtruth_30field/all_annotations.json"


def fetch_hf_cards():
    """Fetch HuggingFace README.md for each benchmark dataset."""
    CARDS_DIR.mkdir(parents=True, exist_ok=True)

    cards = {}
    for pdf_id, (ds_name, hf_id) in BENCHMARK_MAP.items():
        card_file = CARDS_DIR / f"{ds_name}.md"
        if card_file.exists():
            cards[ds_name] = card_file.read_text(encoding="utf-8")
            print(f"  {ds_name}: cached ({len(cards[ds_name])} chars)")
            continue

        url = f"https://huggingface.co/datasets/{hf_id}/raw/main/README.md"
        print(f"  {ds_name}: fetching {url}...", end=" ")
        try:
            resp = requests.get(url, timeout=30)
            if resp.status_code == 200:
                text = resp.text
                card_file.write_text(text, encoding="utf-8")
                cards[ds_name] = text
                print(f"OK ({len(text)} chars)")
            else:
                print(f"HTTP {resp.status_code}")
                cards[ds_name] = None
        except Exception as e:
            print(f"ERROR: {e}")
            cards[ds_name] = None
        time.sleep(0.5)

    return cards


def run_extraction(variant, cards=None):
    """Run extraction for a given source variant."""
    from metadata.extractor import setup_llm_pipeline, clean_llm_output
    from pdf.reader import extract_text_from_pdf
    from pdf.processor import clean_text

    out_dir = OUT_BASE / variant
    out_dir.mkdir(parents=True, exist_ok=True)

    model = setup_llm_pipeline("claude-sonnet-4-5")

    for pdf_id, (ds_name, hf_id) in BENCHMARK_MAP.items():
        out_file = out_dir / f"{ds_name}_extraction.json"
        if out_file.exists():
            print(f"  {ds_name}: cached")
            continue

        print(f"  {ds_name}...", end=" ", flush=True)
        start = time.time()

        # Build input text based on variant
        if variant == "paper_only":
            pdf_path = RAW_DIR / f"{pdf_id}.pdf"
            raw_text = extract_text_from_pdf(pdf_path)
            input_text = clean_text(raw_text)[:MAX_PDF_CHARS]

        elif variant == "card_only":
            card_text = cards.get(ds_name) if cards else None
            if not card_text:
                print("NO CARD, skipping")
                continue
            input_text = card_text[:MAX_PDF_CHARS]

        elif variant == "combined":
            # Paper first, then card
            pdf_path = RAW_DIR / f"{pdf_id}.pdf"
            raw_text = extract_text_from_pdf(pdf_path)
            paper_text = clean_text(raw_text)

            card_text = cards.get(ds_name, "") if cards else ""

            # Combine with separator
            combined = paper_text
            if card_text:
                combined += "\n\n" + "=" * 40 + "\n"
                combined += "HUGGINGFACE DATASET CARD (README.md):\n"
                combined += "=" * 40 + "\n\n"
                combined += card_text

            input_text = combined[:MAX_PDF_CHARS]
        else:
            raise ValueError(f"Unknown variant: {variant}")

        # Extract
        user_prompt = USER_PROMPT_TEMPLATE % input_text
        output = model.generate(user_prompt, system_prompt=SYSTEM_PROMPT)
        json_str = clean_llm_output(output, user_prompt)

        try:
            metadata = json.loads(json_str)
        except json.JSONDecodeError:
            metadata = {}
            for m in re.finditer(r'"([^"]+)"\s*:\s*null', json_str):
                metadata[m.group(1)] = None
            for m in re.finditer(r'"([^"]+)"\s*:\s*"((?:[^"\\]|\\.)*)"', json_str):
                metadata[m.group(1)] = m.group(2).replace('\\n', ' ').strip()
            print(f"(regex: {len(metadata)})", end=" ")

        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        print(f"{time.time()-start:.0f}s")


def run_evaluation():
    """Evaluate all 3 variants with field-type-aware metrics."""
    from evaluation.composite_evaluator import evaluate_method, compute_summary, generate_report
    from evaluation.field_metrics import finalize_cache, ALL_30_FIELDS, get_field_category

    results = {}
    for variant in ["paper_only", "card_only", "combined"]:
        ext_dir = OUT_BASE / variant
        if not ext_dir.exists() or not list(ext_dir.glob("*_extraction.json")):
            print(f"  {variant}: no extractions found, skipping")
            continue
        print(f"  Evaluating {variant}...")
        results[variant] = evaluate_method(str(ext_dir), GT_PATH, variant)

    finalize_cache()

    if len(results) < 2:
        print("Need at least 2 variants to compare.")
        return

    # Generate report
    generate_report(results, str(OUT_BASE / "results"))

    # Per-field source analysis
    print(f"\n{'='*90}")
    print("PER-FIELD SOURCE ANALYSIS")
    print(f"{'='*90}")

    import numpy as np

    summaries = {v: compute_summary(r) for v, r in results.items()}

    print(f"\n{'Field':<40} {'Paper':>7} {'Card':>7} {'Comb':>7} {'Best source':<15}")
    print("-" * 80)

    paper_wins = card_wins = combined_wins = ties = 0
    for field in ALL_30_FIELDS:
        scores = {}
        for variant in ["paper_only", "card_only", "combined"]:
            if variant in summaries:
                scores[variant] = summaries[variant]["per_field"].get(field)

        paper = scores.get("paper_only")
        card = scores.get("card_only")
        combined = scores.get("combined")

        vals = {k: v for k, v in [("Paper", paper), ("Card", card), ("Combined", combined)] if v is not None}
        if not vals:
            continue

        best = max(vals, key=vals.get)
        best_val = vals[best]

        # Check for ties
        at_best = [k for k, v in vals.items() if abs(v - best_val) < 0.01]
        if len(at_best) > 1:
            best = "Tie"
            ties += 1
        elif best == "Paper":
            paper_wins += 1
        elif best == "Card":
            card_wins += 1
        else:
            combined_wins += 1

        p_str = f"{paper:.3f}" if paper is not None else "skip"
        c_str = f"{card:.3f}" if card is not None else "skip"
        b_str = f"{combined:.3f}" if combined is not None else "skip"

        cat = get_field_category(field)
        marker = ""
        if paper is not None and card is not None:
            diff = (paper or 0) - (card or 0)
            if diff > 0.2:
                marker = " ← Paper dominates"
            elif diff < -0.2:
                marker = " ← Card dominates"

        print(f"{field:<40} {p_str:>7} {c_str:>7} {b_str:>7} {best:<15}{marker}")

    print(f"\nBest source wins: Paper={paper_wins}, Card={card_wins}, Combined={combined_wins}, Ties={ties}")


def main():
    parser = argparse.ArgumentParser(description="Source ablation experiment")
    parser.add_argument("--extract-only", action="store_true")
    parser.add_argument("--eval-only", action="store_true")
    args = parser.parse_args()

    print("=" * 60)
    print("SOURCE ABLATION: Paper vs Card vs Combined")
    print("=" * 60)

    if not args.eval_only:
        # Step 1: Fetch cards
        print("\nStep 1: Fetching HuggingFace dataset cards...")
        cards = fetch_hf_cards()

        # Step 2: Paper-only (symlink existing v2 extractions)
        print("\nStep 2: Paper-only extraction...")
        paper_dir = OUT_BASE / "paper_only"
        paper_dir.mkdir(parents=True, exist_ok=True)

        # Copy existing v2 extractions as paper-only
        import shutil
        v2_dir = Path("evaluation_outputs_v2")
        for f in v2_dir.glob("*_extraction.json"):
            dest = paper_dir / f.name
            if not dest.exists():
                shutil.copy(f, dest)
                print(f"  {f.name}: copied from v2")

        # Step 3: Card-only extraction
        print("\nStep 3: Card-only extraction...")
        run_extraction("card_only", cards)

        # Step 4: Combined extraction
        print("\nStep 4: Combined extraction...")
        run_extraction("combined", cards)

    if args.extract_only:
        return

    # Step 5: Evaluate
    print("\nStep 5: Evaluating all variants...")
    run_evaluation()


if __name__ == "__main__":
    main()
