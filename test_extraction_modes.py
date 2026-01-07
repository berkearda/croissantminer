#!/usr/bin/env python3
"""
Compare multi-section vs full-PDF extraction modes

This script runs both extraction modes on the same PDF and compares:
- Extraction quality (field coverage)
- LLM call count
- Processing time
- Cost estimation
"""

import sys
import time
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from main import process_paper
from config import DEFAULT_MODEL_ID, PROCESSED_DATA_DIR


def count_extracted_fields(metadata):
    """Count how many fields were successfully extracted (not 'Not mentioned')"""
    if not metadata:
        return 0

    count = 0
    for key, value in metadata.items():
        if key.startswith("@") or key == "cro:dataModality":
            continue  # Skip metadata fields

        if isinstance(value, dict):
            # Nested fields (like creator, rai:responsibleAIMetadata)
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


def get_field_comparison(multi_metadata, full_metadata):
    """Compare field-by-field extraction results"""
    comparisons = {}

    # Get all field names from schema
    all_fields = set()

    def extract_field_names(data, prefix=""):
        for key, value in data.items():
            if key.startswith("@") or key == "cro:dataModality":
                continue
            full_key = f"{prefix}{key}" if prefix else key
            all_fields.add(full_key)
            if isinstance(value, dict):
                extract_field_names(value, f"{full_key}.")

    extract_field_names(multi_metadata)
    extract_field_names(full_metadata)

    # Compare each field
    for field in sorted(all_fields):
        parts = field.split(".")
        multi_val = multi_metadata
        full_val = full_metadata

        # Navigate nested structure
        try:
            for part in parts:
                multi_val = multi_val.get(part, "Not mentioned") if isinstance(multi_val, dict) else "Not mentioned"
                full_val = full_val.get(part, "Not mentioned") if isinstance(full_val, dict) else "Not mentioned"

            # Convert to string for comparison
            multi_str = str(multi_val) if not isinstance(multi_val, dict) else json.dumps(multi_val)
            full_str = str(full_val) if not isinstance(full_val, dict) else json.dumps(full_val)

            multi_extracted = multi_str not in ["Not mentioned", "unknown", ""]
            full_extracted = full_str not in ["Not mentioned", "unknown", ""]

            comparisons[field] = {
                "multi_section": multi_str[:100] if multi_extracted else "(not extracted)",
                "full_pdf": full_str[:100] if full_extracted else "(not extracted)",
                "both_extracted": multi_extracted and full_extracted,
                "only_multi": multi_extracted and not full_extracted,
                "only_full": full_extracted and not multi_extracted,
                "neither": not multi_extracted and not full_extracted
            }
        except:
            continue

    return comparisons


def compare_extraction_modes(paper_id, paper_path, model_id=DEFAULT_MODEL_ID):
    """
    Run both extraction modes on the same paper and compare results

    Args:
        paper_id (str): Identifier for the paper
        paper_path (str): Path to existing PDF file (without .pdf extension)
        model_id (str): Model ID to use
    """
    print("=" * 80)
    print("EXTRACTION MODE COMPARISON TEST")
    print("=" * 80)
    print(f"Paper ID: {paper_id}")
    print(f"Paper Path: {paper_path}.pdf")
    print(f"Model: {model_id}")
    print()

    results = {
        "paper_id": paper_id,
        "model_id": model_id,
        "multi_section": {},
        "full_pdf": {},
        "comparison": {}
    }

    # Run multi-section mode
    print("\n" + "=" * 80)
    print("TEST 1: MULTI-SECTION MODE (8 LLM calls)")
    print("=" * 80)
    start_time = time.time()

    try:
        multi_metadata = process_paper(
            paper_id=f"{paper_id}_multi",
            paper_path=paper_path,
            model_id=model_id,
            extraction_mode="multi-section"
        )
        multi_time = time.time() - start_time

        results["multi_section"]["success"] = True
        results["multi_section"]["time"] = multi_time
        results["multi_section"]["metadata"] = multi_metadata
        results["multi_section"]["fields_extracted"] = count_extracted_fields(multi_metadata)
        results["multi_section"]["llm_calls"] = 8  # Known for multi-section mode

        print(f"\n✅ Multi-section mode completed in {multi_time:.2f}s")
        print(f"   Fields extracted: {results['multi_section']['fields_extracted']}")

    except Exception as e:
        print(f"\n❌ Multi-section mode failed: {str(e)}")
        results["multi_section"]["success"] = False
        results["multi_section"]["error"] = str(e)
        multi_metadata = None

    # Run full-PDF mode
    print("\n" + "=" * 80)
    print("TEST 2: FULL-PDF MODE (1 LLM call)")
    print("=" * 80)
    start_time = time.time()

    try:
        full_metadata = process_paper(
            paper_id=f"{paper_id}_full",
            paper_path=paper_path,
            model_id=model_id,
            extraction_mode="full-pdf"
        )
        full_time = time.time() - start_time

        results["full_pdf"]["success"] = True
        results["full_pdf"]["time"] = full_time
        results["full_pdf"]["metadata"] = full_metadata
        results["full_pdf"]["fields_extracted"] = count_extracted_fields(full_metadata)
        results["full_pdf"]["llm_calls"] = 1  # Known for full-pdf mode

        print(f"\n✅ Full-PDF mode completed in {full_time:.2f}s")
        print(f"   Fields extracted: {results['full_pdf']['fields_extracted']}")

    except Exception as e:
        print(f"\n❌ Full-PDF mode failed: {str(e)}")
        results["full_pdf"]["success"] = False
        results["full_pdf"]["error"] = str(e)
        full_metadata = None

    # Comparison
    print("\n" + "=" * 80)
    print("COMPARISON RESULTS")
    print("=" * 80)

    if results["multi_section"]["success"] and results["full_pdf"]["success"]:
        # Field comparison
        field_comp = get_field_comparison(multi_metadata, full_metadata)
        results["comparison"]["field_comparison"] = field_comp

        both_extracted = sum(1 for v in field_comp.values() if v["both_extracted"])
        only_multi = sum(1 for v in field_comp.values() if v["only_multi"])
        only_full = sum(1 for v in field_comp.values() if v["only_full"])
        neither = sum(1 for v in field_comp.values() if v["neither"])

        print("\nField Extraction Coverage:")
        print(f"  Both modes extracted:        {both_extracted} fields")
        print(f"  Only multi-section extracted: {only_multi} fields")
        print(f"  Only full-pdf extracted:      {only_full} fields")
        print(f"  Neither mode extracted:       {neither} fields")

        print(f"\nProcessing Time:")
        print(f"  Multi-section: {results['multi_section']['time']:.2f}s")
        print(f"  Full-PDF:      {results['full_pdf']['time']:.2f}s")
        print(f"  Speedup:       {results['multi_section']['time'] / results['full_pdf']['time']:.2f}x")

        print(f"\nLLM Call Efficiency:")
        print(f"  Multi-section: {results['multi_section']['llm_calls']} calls")
        print(f"  Full-PDF:      {results['full_pdf']['llm_calls']} call")
        print(f"  Reduction:     {(1 - results['full_pdf']['llm_calls'] / results['multi_section']['llm_calls']) * 100:.1f}%")

        # Cost estimation (assuming gpt-4o-mini pricing)
        input_cost_per_1k = 0.00015  # $0.150 per 1M tokens = $0.00015 per 1k tokens
        output_cost_per_1k = 0.0006  # $0.600 per 1M tokens = $0.0006 per 1k tokens

        # Rough estimate: ~2000 tokens input + 500 tokens output per call
        multi_cost = results['multi_section']['llm_calls'] * (2000 * input_cost_per_1k + 500 * output_cost_per_1k)
        full_cost = results['full_pdf']['llm_calls'] * (10000 * input_cost_per_1k + 500 * output_cost_per_1k)

        print(f"\nEstimated Cost (gpt-4o-mini):")
        print(f"  Multi-section: ~${multi_cost:.4f}")
        print(f"  Full-PDF:      ~${full_cost:.4f}")

        # Print fields where results differ
        print(f"\n" + "=" * 80)
        print("FIELD-BY-FIELD DIFFERENCES")
        print("=" * 80)

        print("\nFields extracted by multi-section but NOT by full-pdf:")
        for field, comp in field_comp.items():
            if comp["only_multi"]:
                print(f"  {field}:")
                print(f"    Multi-section: {comp['multi_section'][:80]}")

        print("\nFields extracted by full-pdf but NOT by multi-section:")
        for field, comp in field_comp.items():
            if comp["only_full"]:
                print(f"  {field}:")
                print(f"    Full-PDF: {comp['full_pdf'][:80]}")

    # Save results
    output_file = PROCESSED_DATA_DIR / f"{paper_id}_comparison.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)

    print(f"\n" + "=" * 80)
    print(f"📄 Detailed comparison saved to: {output_file}")
    print("=" * 80)

    return results


def main():
    """Test extraction modes on a sample PDF"""
    import argparse

    parser = argparse.ArgumentParser(description="Compare multi-section vs full-PDF extraction modes")
    parser.add_argument("--paper-id", default="test_comparison", help="Identifier for the paper")
    parser.add_argument("--paper-path", default="1405.0312v3", help="Path to PDF (without .pdf extension)")
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID, help="Model ID to use")

    args = parser.parse_args()

    compare_extraction_modes(
        paper_id=args.paper_id,
        paper_path=args.paper_path,
        model_id=args.model_id
    )


if __name__ == "__main__":
    main()
