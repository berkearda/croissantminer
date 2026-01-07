#!/usr/bin/env python3
"""
Run evaluation with lenient scoring (max score across annotators)
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from evaluation.evaluator import batch_evaluate
from evaluation.groundtruth_parser_md import parse_markdown_groundtruth

def main():
    print("=" * 80)
    print("RUNNING EVALUATION WITH LENIENT SCORING")
    print("Strategy: Accept if ANY annotator matches (max score)")
    print("=" * 80)
    print()

    # Parse markdown groundtruth
    md_path = "groundtruth/Croissant_Dataset_Annotations.md"
    print(f"Loading groundtruth from: {md_path}")

    groundtruth_dir = "groundtruth/parsed_md_filtered"
    all_annotations = parse_markdown_groundtruth(md_path, output_dir=groundtruth_dir)

    # Filter to datasets that have both groundtruth AND extraction
    # LibriSpeech and DOLLY have groundtruth but no extraction, so exclude them
    datasets_to_keep = ['MLS', 'MMLU', 'FLORES', 'CIFAR', 'MSCOCO', 'MMMU', 'Visual Genome', 'MathVista']
    filtered_gt = {k: v for k, v in all_annotations.items() if k in datasets_to_keep}

    print(f"\nFiltered to {len(filtered_gt)} datasets: {list(filtered_gt.keys())}")
    print()

    # Run evaluation
    extraction_dir = "evaluation_outputs"
    output_path = "evaluation_outputs/evaluation_report_lenient.json"

    results = batch_evaluate(
        extraction_outputs_dir=extraction_dir,
        groundtruth_dir=groundtruth_dir,
        output_file=output_path,
        verbose=True,
        use_llm=True
    )

    print()
    print("=" * 80)
    print("✅ EVALUATION COMPLETE")
    print(f"Results saved to: {output_path}")
    print("=" * 80)

if __name__ == "__main__":
    main()
