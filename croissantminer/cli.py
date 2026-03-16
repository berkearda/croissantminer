"""
CroissantMiner CLI entry point.

Usage:
    croissantminer extract --paper path/to/paper.pdf
    croissantminer evaluate --results evaluation_outputs/ --groundtruth data/groundtruth/
    croissantminer version
"""

import argparse
import sys

from . import __version__


def main():
    parser = argparse.ArgumentParser(
        prog="croissantminer",
        description="CroissantMiner: Automated ML Dataset Metadata Extraction",
    )
    parser.add_argument("--version", action="version", version=f"croissantminer {__version__}")

    subparsers = parser.add_subparsers(dest="command")

    # Extract command
    extract_parser = subparsers.add_parser("extract", help="Extract metadata from a paper PDF")
    extract_parser.add_argument("--paper", required=True, help="Path to PDF file")
    extract_parser.add_argument("--model", default="claude-sonnet-4-5", help="Model to use")
    extract_parser.add_argument("--output", default=None, help="Output directory")

    # Evaluate command
    eval_parser = subparsers.add_parser("evaluate", help="Evaluate extraction results")
    eval_parser.add_argument("--results", required=True, help="Directory with extraction results")
    eval_parser.add_argument("--groundtruth", default="data/groundtruth/", help="Groundtruth directory")
    eval_parser.add_argument("--output", default=None, help="Output file for report")

    # Version command
    subparsers.add_parser("version", help="Show version")

    args = parser.parse_args()

    if args.command == "extract":
        from .extractor import extract_metadata_full_pdf, setup_llm_pipeline
        from .pdf.reader import extract_text_from_pdf
        from .pdf.processor import clean_text
        from .config import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE, MAX_PDF_CHARS
        from pathlib import Path
        import json

        pdf_path = Path(args.paper)
        if not pdf_path.exists():
            print(f"Error: PDF not found: {pdf_path}")
            sys.exit(1)

        print(f"Extracting metadata from {pdf_path}...")
        model = setup_llm_pipeline(args.model)
        raw_text = extract_text_from_pdf(pdf_path)
        cleaned = clean_text(raw_text)

        output_dir = Path(args.output) if args.output else pdf_path.parent
        output_dir.mkdir(parents=True, exist_ok=True)

        metadata = extract_metadata_full_pdf(cleaned, model, output_dir, MAX_PDF_CHARS)
        print(json.dumps(metadata, indent=2, ensure_ascii=False))

    elif args.command == "evaluate":
        from .evaluator import batch_evaluate
        results = batch_evaluate(
            extraction_outputs_dir=args.results,
            groundtruth_dir=args.groundtruth,
            output_file=args.output,
            verbose=True,
            use_llm=True,
        )

    elif args.command == "version":
        print(f"croissantminer {__version__}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
