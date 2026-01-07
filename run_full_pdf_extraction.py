#!/usr/bin/env python3
"""
Professional batch extraction pipeline using FULL-PDF mode

Extracts metadata from all 8 datasets using the new full-PDF extraction mode
(1 LLM call per paper instead of 8), then evaluates against groundtruth.

Datasets processed:
1. CIFAR (2404.00498v2.pdf)
2. MLS (2012.03411v2.pdf)
3. Visual Genome (1602.07332v1.pdf)
4. FLORES (2106.03193v1.pdf)
5. MSCOCO (1405.0312v3.pdf)
6. MMLU (2009.03300v3.pdf)
7. MMMU (2311.16502v4.pdf)
8. MathVista (2310.02255v3.pdf)
"""

import sys
import time
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from main import process_paper
from config import DEFAULT_MODEL_ID, PROCESSED_DATA_DIR

# Dataset configurations
DATASETS = [
    {"id": "CIFAR", "pdf": "2404.00498v2", "name": "CIFAR-10/100"},
    {"id": "MLS", "pdf": "2012.03411v2", "name": "Multilingual LibriSpeech"},
    {"id": "Visual Genome", "pdf": "1602.07332v1", "name": "Visual Genome"},
    {"id": "FLORES", "pdf": "2106.03193v1", "name": "FLORES-101"},
    {"id": "MSCOCO", "pdf": "1405.0312v3", "name": "MS COCO"},
    {"id": "MMLU", "pdf": "2009.03300v3", "name": "MMLU"},
    {"id": "MMMU", "pdf": "2311.16502v4", "name": "MMMU"},
    {"id": "MathVista", "pdf": "2310.02255v3", "name": "MathVista"},
]


def count_extracted_fields(metadata):
    """Count successfully extracted fields (not 'Not mentioned')"""
    if not metadata:
        return 0

    count = 0
    for key, value in metadata.items():
        if key.startswith("@") or key == "cro:dataModality":
            continue

        if isinstance(value, dict):
            for nested_key, nested_value in value.items():
                if nested_key.startswith("@"):
                    continue
                if isinstance(nested_value, str) and nested_value not in ["Not mentioned", "unknown", ""]:
                    count += 1
        elif isinstance(value, str):
            if value not in ["Not mentioned", "unknown", ""]:
                count += 1
        elif isinstance(value, list):
            if len(value) > 0:
                count += 1

    return count


def extract_all_datasets(model_id=DEFAULT_MODEL_ID):
    """
    Extract metadata from all 8 datasets using full-PDF mode

    Returns:
        dict: Extraction results and statistics
    """
    print("=" * 100)
    print("FULL-PDF EXTRACTION PIPELINE - BATCH PROCESSING")
    print("=" * 100)
    print(f"Mode: FULL-PDF (1 LLM call per paper)")
    print(f"Model: {model_id}")
    print(f"Datasets: {len(DATASETS)}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 100)
    print()

    results = {
        "metadata": {
            "extraction_mode": "full-pdf",
            "model_id": model_id,
            "timestamp": datetime.now().isoformat(),
            "num_datasets": len(DATASETS),
        },
        "datasets": {},
        "summary": {
            "total_datasets": len(DATASETS),
            "successful": 0,
            "failed": 0,
            "total_time": 0,
            "total_llm_calls": 0,
            "avg_time_per_paper": 0,
            "avg_fields_extracted": 0,
        }
    }

    overall_start = time.time()

    for i, dataset in enumerate(DATASETS, 1):
        dataset_id = dataset["id"]
        pdf_name = dataset["pdf"]
        display_name = dataset["name"]

        print(f"\n{'=' * 100}")
        print(f"DATASET {i}/{len(DATASETS)}: {display_name}")
        print(f"{'=' * 100}")
        print(f"ID: {dataset_id}")
        print(f"PDF: {pdf_name}.pdf")
        print()

        start_time = time.time()

        try:
            # Process with full-PDF mode
            metadata = process_paper(
                paper_id=dataset_id,
                paper_path=pdf_name,
                model_id=model_id,
                extraction_mode="full-pdf"
            )

            elapsed = time.time() - start_time
            fields_extracted = count_extracted_fields(metadata)

            # Store results
            results["datasets"][dataset_id] = {
                "status": "success",
                "pdf_file": f"{pdf_name}.pdf",
                "display_name": display_name,
                "extraction_time": round(elapsed, 2),
                "llm_calls": 1,
                "fields_extracted": fields_extracted,
                "metadata": metadata,
                "output_dir": str(PROCESSED_DATA_DIR / dataset_id)
            }

            results["summary"]["successful"] += 1
            results["summary"]["total_llm_calls"] += 1

            print(f"\n✅ SUCCESS - {display_name}")
            print(f"   Time: {elapsed:.2f}s")
            print(f"   Fields extracted: {fields_extracted}")
            print(f"   Output: {PROCESSED_DATA_DIR / dataset_id}")

        except Exception as e:
            elapsed = time.time() - start_time

            results["datasets"][dataset_id] = {
                "status": "failed",
                "pdf_file": f"{pdf_name}.pdf",
                "display_name": display_name,
                "extraction_time": round(elapsed, 2),
                "error": str(e),
            }

            results["summary"]["failed"] += 1

            print(f"\n❌ FAILED - {display_name}")
            print(f"   Error: {str(e)}")

    # Calculate summary statistics
    overall_time = time.time() - overall_start
    results["summary"]["total_time"] = round(overall_time, 2)

    if results["summary"]["successful"] > 0:
        successful_datasets = [d for d in results["datasets"].values() if d["status"] == "success"]
        results["summary"]["avg_time_per_paper"] = round(
            sum(d["extraction_time"] for d in successful_datasets) / len(successful_datasets), 2
        )
        results["summary"]["avg_fields_extracted"] = round(
            sum(d["fields_extracted"] for d in successful_datasets) / len(successful_datasets), 1
        )

    # Print summary
    print(f"\n{'=' * 100}")
    print("EXTRACTION SUMMARY")
    print(f"{'=' * 100}")
    print(f"Total datasets:      {results['summary']['total_datasets']}")
    print(f"Successful:          {results['summary']['successful']} ✅")
    print(f"Failed:              {results['summary']['failed']} ❌")
    print(f"Total LLM calls:     {results['summary']['total_llm_calls']}")
    print(f"Total time:          {results['summary']['total_time']:.2f}s")
    print(f"Avg time per paper:  {results['summary']['avg_time_per_paper']:.2f}s")
    print(f"Avg fields/paper:    {results['summary']['avg_fields_extracted']:.1f}")
    print(f"{'=' * 100}")

    # Save results
    output_dir = Path("evaluation_outputs")
    output_dir.mkdir(exist_ok=True)

    results_file = output_dir / "full_pdf_extraction_results.json"
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n📄 Full results saved to: {results_file}")

    return results


def main():
    """Run full-PDF extraction on all datasets"""
    import argparse

    parser = argparse.ArgumentParser(description="Batch extract metadata using full-PDF mode")
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID, help="Model ID to use")

    args = parser.parse_args()

    results = extract_all_datasets(model_id=args.model_id)

    print(f"\n{'=' * 100}")
    print("✅ BATCH EXTRACTION COMPLETE")
    print(f"{'=' * 100}")
    print(f"Next step: Run evaluation with 'python run_evaluation_full_pdf.py'")
    print(f"{'=' * 100}\n")

    return results


if __name__ == "__main__":
    main()
