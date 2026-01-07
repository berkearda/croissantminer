"""
End-to-end evaluation test script for CroissantMiner

This script:
1. Parses groundtruth annotations from the PDF
2. Runs the extraction pipeline on all 8 papers
3. Evaluates results against groundtruth
4. Generates comprehensive reports

Usage:
    python test_evaluation.py --mode parse     # Parse groundtruth only
    python test_evaluation.py --mode extract   # Run extraction only
    python test_evaluation.py --mode evaluate  # Evaluate only (requires extracted outputs)
    python test_evaluation.py --mode full      # Full pipeline (default)
"""

import argparse
import sys
import json
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from evaluation.groundtruth_parser import parse_groundtruth, DATASET_PDF_MAPPING
from evaluation.evaluator import batch_evaluate
from evaluation.reporter import generate_report, visualize_results, export_results


def parse_groundtruth_step(base_dir: Path, verbose: bool = True):
    """
    Step 1: Parse groundtruth from PDF

    Args:
        base_dir: Base directory of the project
        verbose: Whether to print detailed output

    Returns:
        Path to parsed groundtruth directory
    """
    print("=" * 80)
    print("STEP 1: PARSING GROUNDTRUTH")
    print("=" * 80)

    groundtruth_pdf = base_dir / "groundtruth" / "Croissant User Research Report.pdf"
    output_dir = base_dir / "groundtruth" / "parsed"

    if not groundtruth_pdf.exists():
        print(f"Error: Groundtruth PDF not found: {groundtruth_pdf}")
        return None

    # Parse
    annotations = parse_groundtruth(str(groundtruth_pdf), str(output_dir))

    print(f"\nSuccessfully parsed {len(annotations)} datasets")
    print(f"Output directory: {output_dir}")

    return output_dir


def run_extraction_step(base_dir: Path, test_mode: bool = False, verbose: bool = True):
    """
    Step 2: Run extraction pipeline on all 8 papers

    Args:
        base_dir: Base directory of the project
        test_mode: If True, only process first 2 papers for testing
        verbose: Whether to print detailed output

    Returns:
        Path to extraction outputs directory
    """
    print("\n" + "=" * 80)
    print("STEP 2: RUNNING EXTRACTION PIPELINE")
    print("=" * 80)

    # Import main pipeline - adjust based on your actual main script
    try:
        from main import extract_metadata_from_pdf
    except ImportError:
        print("Warning: Could not import main extraction pipeline")
        print("Please ensure you have a main.py with extract_metadata_from_pdf function")
        return None

    data_dir = base_dir / "data"
    output_dir = base_dir / "evaluation_outputs"
    output_dir.mkdir(exist_ok=True)

    # Get PDFs to process
    pdfs_to_process = list(DATASET_PDF_MAPPING.values())
    if test_mode:
        pdfs_to_process = pdfs_to_process[:2]
        print(f"\nTest mode: Processing only {len(pdfs_to_process)} papers")

    successful = 0
    failed = 0

    for pdf_filename in pdfs_to_process:
        pdf_path = data_dir / pdf_filename
        output_file = output_dir / pdf_filename.replace('.pdf', '_extraction.json')

        if not pdf_path.exists():
            print(f"\n⚠ Warning: PDF not found: {pdf_filename}")
            failed += 1
            continue

        print(f"\nProcessing: {pdf_filename}")

        try:
            # Run extraction
            metadata = extract_metadata_from_pdf(str(pdf_path))

            # Save results
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)

            print(f"  ✓ Saved to: {output_file.name}")
            successful += 1

        except Exception as e:
            print(f"  ✗ Error: {e}")
            failed += 1

    print(f"\nExtraction complete: {successful} successful, {failed} failed")
    return output_dir


def run_evaluation_step(
    base_dir: Path,
    extraction_output_dir: Path,
    groundtruth_dir: Path,
    verbose: bool = True,
    use_llm: bool = False
):
    """
    Step 3: Evaluate extraction results against groundtruth

    Args:
        base_dir: Base directory of the project
        extraction_output_dir: Directory with extraction outputs
        groundtruth_dir: Directory with parsed groundtruth
        verbose: Whether to print detailed output
        use_llm: Whether to use LLM-based evaluation

    Returns:
        Evaluation results dictionary
    """
    print("\n" + "=" * 80)
    print("STEP 3: EVALUATING RESULTS")
    print("=" * 80)

    if use_llm:
        print("Using LLM-based semantic evaluation (GPT-4o-mini as judge)")
    else:
        print("Using string-based evaluation")

    # Run batch evaluation
    results = batch_evaluate(
        str(extraction_output_dir),
        str(groundtruth_dir),
        verbose=verbose,
        use_llm=use_llm
    )

    return results


def generate_reports_step(
    base_dir: Path,
    evaluation_results: dict,
    verbose: bool = True
):
    """
    Step 4: Generate reports and visualizations

    Args:
        base_dir: Base directory of the project
        evaluation_results: Results from evaluation
        verbose: Whether to print detailed output

    Returns:
        Path to reports directory
    """
    print("\n" + "=" * 80)
    print("STEP 4: GENERATING REPORTS")
    print("=" * 80)

    # Create reports directory with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    reports_dir = base_dir / "evaluation_reports" / f"report_{timestamp}"
    reports_dir.mkdir(parents=True, exist_ok=True)

    # Generate all report formats
    report_file = generate_report(
        evaluation_results,
        str(reports_dir),
        report_name="evaluation_report"
    )

    # Generate visualizations
    try:
        visualize_results(evaluation_results, str(reports_dir))
    except Exception as e:
        print(f"Warning: Could not generate visualizations: {e}")

    print(f"\nReports saved to: {reports_dir}")
    return reports_dir


def main():
    parser = argparse.ArgumentParser(
        description='End-to-end evaluation for CroissantMiner'
    )
    parser.add_argument(
        '--mode',
        choices=['parse', 'extract', 'evaluate', 'full'],
        default='full',
        help='Execution mode (default: full)'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Test mode: process only 2 papers'
    )
    parser.add_argument(
        '--extraction-dir',
        type=str,
        help='Path to existing extraction outputs (for evaluate mode)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        default=True,
        help='Verbose output'
    )
    parser.add_argument(
        '--use-llm',
        action='store_true',
        help='Use LLM-based semantic evaluation (GPT-4o-mini as judge)'
    )

    args = parser.parse_args()

    # Get base directory
    base_dir = Path(__file__).parent

    print("=" * 80)
    print("CROISSANTMINER EVALUATION PIPELINE")
    print("=" * 80)
    print(f"Mode: {args.mode}")
    print(f"Base directory: {base_dir}")
    if args.test:
        print("Test mode: ENABLED (processing 2 papers only)")
    print("=" * 80)

    # Execute based on mode
    if args.mode in ['parse', 'full']:
        groundtruth_dir = parse_groundtruth_step(base_dir, args.verbose)
        if not groundtruth_dir:
            print("\n❌ Groundtruth parsing failed")
            return 1
    else:
        groundtruth_dir = base_dir / "groundtruth" / "parsed"

    if args.mode in ['extract', 'full']:
        extraction_dir = run_extraction_step(base_dir, args.test, args.verbose)
        if not extraction_dir:
            print("\n⚠ Extraction step skipped or failed")
            # Continue anyway - user might want to evaluate existing outputs
            extraction_dir = base_dir / "evaluation_outputs"
    else:
        # Use provided extraction directory or default
        if args.extraction_dir:
            extraction_dir = Path(args.extraction_dir)
        else:
            extraction_dir = base_dir / "evaluation_outputs"

    if args.mode in ['evaluate', 'full']:
        if not extraction_dir.exists():
            print(f"\n❌ Extraction output directory not found: {extraction_dir}")
            return 1

        if not groundtruth_dir.exists():
            print(f"\n❌ Groundtruth directory not found: {groundtruth_dir}")
            print("Please run with --mode parse first")
            return 1

        # Run evaluation
        results = run_evaluation_step(
            base_dir,
            extraction_dir,
            groundtruth_dir,
            args.verbose,
            args.use_llm
        )

        # Generate reports
        reports_dir = generate_reports_step(base_dir, results, args.verbose)

        print("\n" + "=" * 80)
        print("EVALUATION COMPLETE")
        print("=" * 80)
        print(f"Reports available at: {reports_dir}")

    print("\n✓ Pipeline completed successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
