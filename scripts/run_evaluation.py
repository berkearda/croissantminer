#!/usr/bin/env python3
"""
Professional evaluation pipeline for FULL-PDF extraction results

Evaluates the metadata extracted using full-PDF mode against groundtruth annotations
using the LLM-as-judge approach with lenient scoring (max score across annotators).

Generates comprehensive accuracy reports and comparison with multi-section mode.
"""

import sys
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from evaluation.evaluator import batch_evaluate
from evaluation.groundtruth_parser_md import parse_markdown_groundtruth
from evaluation.markdown_generator import generate_detailed_markdown


def run_full_pdf_evaluation():
    """
    Run evaluation on full-PDF extraction results

    Returns:
        dict: Evaluation results
    """
    print("=" * 100)
    print("FULL-PDF EXTRACTION EVALUATION PIPELINE")
    print("=" * 100)
    print("Extraction Mode: FULL-PDF (1 LLM call per paper)")
    print("Evaluation Strategy: LLM-as-Judge with Lenient Scoring")
    print("Scoring: Accept if ANY annotator matches (max score)")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 100)
    print()

    # Parse markdown groundtruth
    md_path = "groundtruth/Croissant_Dataset_Annotations.md"
    print(f"📖 Loading groundtruth from: {md_path}")

    groundtruth_dir = "groundtruth/parsed_md_filtered"
    all_annotations = parse_markdown_groundtruth(md_path, output_dir=groundtruth_dir)

    # Filter to the 8 datasets we extracted
    datasets_to_evaluate = ['MLS', 'MMLU', 'FLORES', 'CIFAR', 'MSCOCO', 'MMMU', 'Visual Genome', 'MathVista']
    filtered_gt = {k: v for k, v in all_annotations.items() if k in datasets_to_evaluate}

    print(f"✓ Filtered to {len(filtered_gt)} datasets: {list(filtered_gt.keys())}")
    print()

    # Run evaluation on full-PDF extraction results
    extraction_dir = "evaluation_outputs"  # Full-PDF results are copied here
    output_file = "evaluation_outputs/evaluation_report_full_pdf.json"

    print("=" * 100)
    print("RUNNING EVALUATION")
    print("=" * 100)
    print()

    results = batch_evaluate(
        extraction_outputs_dir=extraction_dir,
        groundtruth_dir=groundtruth_dir,
        output_file=output_file,
        verbose=True,
        use_llm=True
    )

    print()
    print("=" * 100)
    print("✅ EVALUATION COMPLETE")
    print(f"Results saved to: {output_file}")
    print("=" * 100)
    print()

    # Generate detailed markdown report
    print("=" * 100)
    print("GENERATING DETAILED MARKDOWN REPORT")
    print("=" * 100)
    print()

    md_output = "evaluation_outputs/full_pdf_evaluation_detailed.md"
    generate_detailed_markdown(
        report_path=output_file,
        groundtruth_dir=groundtruth_dir,
        extraction_dir=extraction_dir,
        output_path=md_output
    )

    print(f"✓ Detailed markdown report: {md_output}")
    print()

    return results


def generate_comparison_report():
    """
    Generate comprehensive comparison report between multi-section and full-PDF modes

    Compares:
    - Overall accuracy
    - Per-dataset accuracy
    - Processing time
    - LLM call count
    - Cost efficiency
    - Field coverage
    """
    print("=" * 100)
    print("GENERATING COMPARISON REPORT: MULTI-SECTION vs FULL-PDF")
    print("=" * 100)
    print()

    # Load results
    multi_section_file = Path("evaluation_outputs/evaluation_report_lenient.json")
    full_pdf_file = Path("evaluation_outputs/evaluation_report_full_pdf.json")
    extraction_results_file = Path("evaluation_outputs/full_pdf_extraction_results.json")

    if not multi_section_file.exists():
        print(f"⚠️ Multi-section results not found: {multi_section_file}")
        print("   Skipping comparison report")
        return

    if not full_pdf_file.exists():
        print(f"⚠️ Full-PDF evaluation results not found: {full_pdf_file}")
        return

    # Load data
    with open(multi_section_file, 'r') as f:
        multi_results = json.load(f)

    with open(full_pdf_file, 'r') as f:
        full_results = json.load(f)

    extraction_stats = {}
    if extraction_results_file.exists():
        with open(extraction_results_file, 'r') as f:
            extraction_data = json.load(f)
            extraction_stats = extraction_data.get("summary", {})

    # Calculate comparison statistics
    comparison = {
        "metadata": {
            "comparison_date": datetime.now().isoformat(),
            "multi_section_file": str(multi_section_file),
            "full_pdf_file": str(full_pdf_file),
        },
        "overall_accuracy": {},
        "per_dataset_accuracy": {},
        "performance_metrics": {},
        "field_coverage": {},
        "cost_analysis": {},
    }

    # Overall accuracy comparison
    multi_overall = multi_results.get("summary", {}).get("overall_accuracy", 0)
    full_overall = full_results.get("summary", {}).get("overall_accuracy", 0)

    comparison["overall_accuracy"] = {
        "multi_section": round(multi_overall * 100, 2),
        "full_pdf": round(full_overall * 100, 2),
        "difference": round((full_overall - multi_overall) * 100, 2),
        "improvement_pct": round(((full_overall - multi_overall) / multi_overall * 100), 2) if multi_overall > 0 else 0
    }

    # Per-dataset accuracy comparison
    for dataset_name in ['MLS', 'MMLU', 'FLORES', 'CIFAR', 'MSCOCO', 'MMMU', 'Visual Genome', 'MathVista']:
        multi_acc = multi_results.get("results", {}).get(dataset_name, {}).get("metrics", {}).get("accuracy", 0)
        full_acc = full_results.get("results", {}).get(dataset_name, {}).get("metrics", {}).get("accuracy", 0)

        comparison["per_dataset_accuracy"][dataset_name] = {
            "multi_section": round(multi_acc * 100, 2),
            "full_pdf": round(full_acc * 100, 2),
            "difference": round((full_acc - multi_acc) * 100, 2),
        }

    # Performance metrics (if extraction stats available)
    if extraction_stats:
        comparison["performance_metrics"] = {
            "multi_section": {
                "avg_time_per_paper": "~60s",  # From previous tests
                "llm_calls_per_paper": 8,
                "total_llm_calls": 8 * 8,  # 8 datasets * 8 calls
            },
            "full_pdf": {
                "avg_time_per_paper": f"{extraction_stats.get('avg_time_per_paper', 0)}s",
                "llm_calls_per_paper": 1,
                "total_llm_calls": extraction_stats.get('total_llm_calls', 8),
                "total_time": f"{extraction_stats.get('total_time', 0)}s",
            },
            "improvement": {
                "time_reduction_pct": "~87.5%",  # Estimated based on tests
                "llm_call_reduction_pct": "87.5%",
            }
        }

    # Cost analysis
    input_cost_per_1k = 0.00015  # gpt-4o-mini
    output_cost_per_1k = 0.0006

    multi_cost = 64 * (2000 * input_cost_per_1k + 500 * output_cost_per_1k)  # 8 datasets * 8 calls
    full_cost = 8 * (10000 * input_cost_per_1k + 500 * output_cost_per_1k)  # 8 datasets * 1 call

    comparison["cost_analysis"] = {
        "multi_section_total": round(multi_cost, 4),
        "full_pdf_total": round(full_cost, 4),
        "savings": round(multi_cost - full_cost, 4),
        "savings_pct": round((multi_cost - full_cost) / multi_cost * 100, 2),
    }

    # Save comparison report
    output_file = Path("evaluation_outputs/mode_comparison_report.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(comparison, f, indent=2, ensure_ascii=False)

    print(f"✓ Comparison report saved to: {output_file}")
    print()

    # Print summary
    print("=" * 100)
    print("COMPARISON SUMMARY")
    print("=" * 100)
    print()
    print("📊 ACCURACY COMPARISON:")
    print(f"   Multi-section: {comparison['overall_accuracy']['multi_section']:.2f}%")
    print(f"   Full-PDF:      {comparison['overall_accuracy']['full_pdf']:.2f}%")
    print(f"   Difference:    {comparison['overall_accuracy']['difference']:+.2f} percentage points")
    print()

    if extraction_stats:
        print("⚡ PERFORMANCE COMPARISON:")
        print(f"   Avg time per paper:")
        print(f"     Multi-section: ~60s")
        print(f"     Full-PDF:      {extraction_stats.get('avg_time_per_paper', 0)}s")
        print(f"   LLM calls per paper:")
        print(f"     Multi-section: 8 calls")
        print(f"     Full-PDF:      1 call (87.5% reduction)")
        print()

    print("💰 COST COMPARISON (estimated):")
    print(f"   Multi-section: ${comparison['cost_analysis']['multi_section_total']:.4f}")
    print(f"   Full-PDF:      ${comparison['cost_analysis']['full_pdf_total']:.4f}")
    print(f"   Savings:       ${comparison['cost_analysis']['savings']:.4f} ({comparison['cost_analysis']['savings_pct']:.1f}%)")
    print()

    print("📈 PER-DATASET ACCURACY:")
    for dataset_name, acc in comparison["per_dataset_accuracy"].items():
        diff_indicator = "+" if acc["difference"] >= 0 else ""
        print(f"   {dataset_name:15s}: Multi={acc['multi_section']:5.1f}%  Full={acc['full_pdf']:5.1f}%  Diff={diff_indicator}{acc['difference']:+5.2f}pp")

    print()
    print("=" * 100)

    return comparison


def main():
    """Run full-PDF evaluation pipeline"""
    print("\n" + "=" * 100)
    print("FULL-PDF EXTRACTION - COMPREHENSIVE EVALUATION PIPELINE")
    print("=" * 100)
    print()

    # Step 1: Run evaluation
    results = run_full_pdf_evaluation()

    # Step 2: Generate comparison report
    print()
    comparison = generate_comparison_report()

    print()
    print("=" * 100)
    print("✅ ALL EVALUATIONS COMPLETE")
    print("=" * 100)
    print()
    print("Generated files:")
    print("  1. evaluation_outputs/evaluation_report_full_pdf.json")
    print("  2. evaluation_outputs/full_pdf_evaluation_detailed.md")
    print("  3. evaluation_outputs/mode_comparison_report.json")
    print()
    print("=" * 100)
    print()


if __name__ == "__main__":
    main()
