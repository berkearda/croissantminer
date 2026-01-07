
"""
PMLR Metadata Extraction Pipeline

This script processes PDF papers to extract dataset metadata using LLMs.
"""

import argparse
import time
from pathlib import Path

from config import (
    RAW_DATA_DIR,
    PROCESSED_DATA_DIR,
    DEFAULT_MODEL_ID,
    MAX_SECTION_TOKENS,
    MAX_SECTIONS,
    EXTRACTION_MODE,
    MAX_PDF_CHARS
)

from pdf.reader import download_pdf, extract_text_from_pdf
from pdf.processor import (
    clean_text, 
    process_paper as process_paper_text,  # İsim çakışmasını önlemek için yeniden adlandırma
    extract_targeted_sections,
    process_sections, 
    chunk_for_llm,
    save_processed_paper
)

from metadata.relevance import select_relevant_sections
from metadata.extractor import (
    setup_llm_pipeline,
    extract_metadata,
    extract_metadata_full_pdf,
    parse_metadata_results
)

from metadata.unifier import unify_metadata, convert_to_croissant


def extract_metadata_from_pdf(pdf_path, model_id=DEFAULT_MODEL_ID):
    """
    Extract metadata from a single PDF file

    Args:
        pdf_path (str): Path to PDF file
        model_id (str): HuggingFace model ID for metadata extraction

    Returns:
        dict: Extracted Croissant metadata
    """
    from pathlib import Path
    import shutil

    pdf_path = Path(pdf_path)
    paper_id = pdf_path.stem

    # The process_paper function expects the PDF to be in RAW_DATA_DIR
    # So we need to copy it there if it's not already
    target_pdf = RAW_DATA_DIR / pdf_path.name
    if not target_pdf.exists() and pdf_path.exists():
        shutil.copy(pdf_path, target_pdf)

    # Use the main process_paper function (pass just the paper_id as paper_path)
    process_paper(
        paper_id=paper_id,
        paper_path=paper_id,  # Just the name, it will add .pdf and RAW_DATA_DIR
        model_id=model_id
    )

    # Load the croissant metadata that was saved
    paper_dir = PROCESSED_DATA_DIR / paper_id
    croissant_file = paper_dir / "croissant_metadata.json"

    if croissant_file.exists():
        import json
        with open(croissant_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        return {}


def process_paper(paper_id, paper_url=None, paper_path=None, model_id=DEFAULT_MODEL_ID, extraction_mode=None):
    """
    Process a paper to extract dataset metadata

    Args:
        paper_id (str): Identifier for the paper
        paper_url (str, optional): URL to download the paper
        paper_path (str, optional): Path to existing PDF file
        model_id (str): HuggingFace model ID for metadata extraction
        extraction_mode (str, optional): "multi-section" or "full-pdf". Defaults to config.EXTRACTION_MODE
    """
    # Use config default if not specified
    if extraction_mode is None:
        extraction_mode = EXTRACTION_MODE

    print(f"===== Processing paper: {paper_id} =====")
    print(f"Extraction mode: {extraction_mode.upper()}")
    start_time = time.time()

    # Create paper-specific directories
    paper_dir = PROCESSED_DATA_DIR / paper_id
    paper_dir.mkdir(exist_ok=True)

    # Step 1: Get the PDF
    if paper_path:
        pdf_path = RAW_DATA_DIR / f"{paper_path}.pdf"
    elif paper_url:
        pdf_path = RAW_DATA_DIR / f"{paper_id}.pdf"
        download_pdf(paper_url, pdf_path)
    else:
        raise ValueError("Either paper_url or paper_path must be provided")

    # Step 2: Extract and process text
    print("\n----- Extracting text from PDF -----")
    raw_text = extract_text_from_pdf(pdf_path)
    if not raw_text:
        raise ValueError("Failed to extract text from PDF")

    # Step 2: Clean and normalize text
    print("----- Cleaning and normalizing text -----")
    cleaned_text = clean_text(raw_text)

    # Initialize LLM pipeline (needed for both modes)
    llm_pipeline = setup_llm_pipeline(model_id)

    # Branch based on extraction mode
    if extraction_mode == "full-pdf":
        # FULL-PDF MODE: Extract from entire PDF in one call
        print("\n----- Extracting metadata with FULL-PDF mode (1 LLM call) -----")
        unified_metadata = extract_metadata_full_pdf(cleaned_text, llm_pipeline, paper_dir, MAX_PDF_CHARS)

        # No need for unification - already have complete metadata
        ambiguous_fields = {}

    elif extraction_mode == "multi-section":
        # MULTI-SECTION MODE: Original approach with section-based extraction
        # Step 3: Process paper and extract targeted sections
        print("----- Extracting targeted sections -----")
        # İsim çakışmasını önlemek için yeniden adlandırılan fonksiyonu kullan
        processed_paper = process_paper_text(cleaned_text, paper_dir / "processed_sections.json", debug=True)

        # Get the processed sections from the result
        processed_sections = processed_paper['sections']

        # Save processed paper
        paper_data = {
            'paper_id': paper_id,
            'full_text': cleaned_text[:1000] + "...",  # Just a preview of full text
            'sections': processed_sections
        }
        save_processed_paper(paper_data, paper_dir / "processed_paper.json")

        # Step 4: Prepare sections for LLM
        print("\n----- Preparing sections for LLM processing -----")
        llm_sections = chunk_for_llm(processed_sections, MAX_SECTION_TOKENS)

        # Step 5: Filter sections by relevance
        print("\n----- Selecting most relevant sections -----")
        relevant_sections = select_relevant_sections(llm_sections, MAX_SECTIONS)

        # Step 6: Extract metadata with LLM
        print("\n----- Extracting metadata with LLM (MULTI-SECTION mode) -----")
        section_results = extract_metadata(relevant_sections, llm_pipeline, paper_dir)

        # Step 7: Parse and unify metadata
        print("\n----- Parsing and unifying metadata -----")
        metadata_list = parse_metadata_results(section_results)

        if not metadata_list:
            print("⚠️ No valid metadata was extracted from the paper")
            return

        unified_metadata, ambiguous_fields = unify_metadata(metadata_list, paper_dir)

    else:
        raise ValueError(f"Invalid extraction_mode: {extraction_mode}. Must be 'multi-section' or 'full-pdf'")

    # Step 8: Convert to Croissant format (same for both modes)
    print("\n----- Converting to Croissant format -----")
    croissant_metadata = convert_to_croissant(unified_metadata, paper_dir)

    # Done!
    elapsed_time = time.time() - start_time
    print(f"\n===== Completed processing paper: {paper_id} =====")
    print(f"Extraction mode: {extraction_mode.upper()}")
    print(f"Time taken: {elapsed_time:.2f} seconds")
    print(f"Results saved to {paper_dir}")

    return croissant_metadata


def main():
    """Command-line interface for the metadata extraction pipeline"""
    parser = argparse.ArgumentParser(description="Extract dataset metadata from academic papers")

    parser.add_argument("--paper-id", default='visualgenome', help="Identifier for the paper")
    parser.add_argument("--paper-url", default='https://arxiv.org/pdf/2310.02255', help="URL to download the paper")
    parser.add_argument("--paper-path", default='visualgenome', help="Path to existing PDF file")
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID, help="HuggingFace model ID")
    parser.add_argument("--extraction-mode", default=None, choices=["multi-section", "full-pdf"],
                        help="Extraction mode: 'multi-section' (8 LLM calls) or 'full-pdf' (1 LLM call). Defaults to config.EXTRACTION_MODE")

    args = parser.parse_args()

    if not args.paper_url and not args.paper_path:
        parser.error("Either --paper-url or --paper-path must be provided")

    process_paper(
        paper_id=args.paper_id,
        paper_url=args.paper_url,
        paper_path=args.paper_path,
        model_id=args.model_id,
        extraction_mode=args.extraction_mode,
    )


if __name__ == "__main__":
    main()