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
    MAX_SECTION_TOKENS,
    MAX_SECTIONS
)

from pdf.reader import download_pdf, extract_text_from_pdf
from pdf.processor import (
    clean_text, 
    process_paper as process_paper_text,  
    extract_targeted_sections,
    process_sections, 
    chunk_for_llm,
    save_processed_paper
)

from metadata.relevance import select_relevant_sections
from metadata.extractor import (
    setup_llm_pipeline,
    extract_metadata,
    parse_metadata_results
)

from metadata.unifier import unify_metadata, convert_to_croissant


def process_paper(paper_id, paper_url=None, paper_path=None, model_name="gpt-4o-mini", **model_kwargs):
    """
    Process a paper to extract dataset metadata
    
    Args:
        paper_id (str): Identifier for the paper
        paper_url (str, optional): URL to download the paper
        paper_path (str, optional): Path to existing PDF file
        model_name (str): Name of the model to use
        **model_kwargs: Additional model configuration
    """
    print(f"===== Processing paper: {paper_id} =====")
    print(f"Using model: {model_name}")
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
    
    # Step 3: Clean and normalize text
    print("----- Cleaning and normalizing text -----")
    cleaned_text = clean_text(raw_text)
    
    # Step 4: Process paper and extract targeted sections
    print("----- Extracting targeted sections -----")
    processed_paper = process_paper_text(cleaned_text, paper_dir / "processed_sections.json", debug=True)
    
    # Get the processed sections from the result
    processed_sections = processed_paper['sections']
    
    # Save processed paper
    paper_data = {
        'paper_id': paper_id,
        'model_used': model_name,
        'full_text': cleaned_text[:1000] + "...",  # Just a preview of full text
        'sections': processed_sections
    }
    save_processed_paper(paper_data, paper_dir / "processed_paper.json")
    
    # Step 5: Prepare sections for LLM
    print("\n----- Preparing sections for LLM processing -----")
    llm_sections = chunk_for_llm(processed_sections, MAX_SECTION_TOKENS)
    
    # Step 6: Filter sections by relevance
    print("\n----- Selecting most relevant sections -----")
    relevant_sections = select_relevant_sections(llm_sections, MAX_SECTIONS)
    
    # Step 7: Extract metadata with LLM
    print(f"\n----- Extracting metadata with {model_name} -----")
    model = setup_llm_pipeline(model_name, **model_kwargs)
    
    try:
        section_results = extract_metadata(relevant_sections, model, paper_dir)
        
        # Step 8: Parse and unify metadata
        print("\n----- Parsing and unifying metadata -----")
        metadata_list = parse_metadata_results(section_results)
        
        if not metadata_list:
            print("⚠️ No valid metadata was extracted from the paper")
            return
        
        unified_metadata, ambiguous_fields = unify_metadata(metadata_list, paper_dir)
        
        # Step 9: Convert to Croissant format
        print("\n----- Converting to Croissant format -----") 
        croissant_metadata = convert_to_croissant(unified_metadata, paper_dir)
        
    finally:
        # Always cleanup model resources
        model.cleanup()
    
    # Done!
    elapsed_time = time.time() - start_time
    print(f"\n===== Completed processing paper: {paper_id} =====")
    print(f"Model used: {model_name}")
    print(f"Time taken: {elapsed_time:.2f} seconds")
    print(f"Results saved to {paper_dir}")


def main():
    """Command-line interface for the metadata extraction pipeline"""
    parser = argparse.ArgumentParser(description="Extract dataset metadata from academic papers")
    
    # Paper arguments
    parser.add_argument("--paper-id", default='dolly', help="Identifier for the paper")
    parser.add_argument("--paper-url", default='https://arxiv.org/pdf/2310.02255', help="URL to download the paper")
    parser.add_argument("--paper-path", default= 'dolly', help="Path to existing PDF file")
    
    # Model arguments
    parser.add_argument("--model", default="gpt-4o-mini", help="Model to use (gpt-4o, gpt-4o-mini, mistral-7b)")
    parser.add_argument("--temperature", type=float, default=0.3, help="Model temperature")
    parser.add_argument("--max-tokens", type=int, default=1024, help="Maximum tokens to generate")
    
    args = parser.parse_args()
    
    if not args.paper_url and not args.paper_path:
        parser.error("Either --paper-url or --paper-path must be provided")
    
    # Model configuration
    model_kwargs = {
        'temperature': args.temperature,
        'max_tokens': args.max_tokens,
    }
    
    process_paper(
        paper_id=args.paper_id,
        paper_url=args.paper_url,
        paper_path=args.paper_path,
        model_name=args.model,
        **model_kwargs
    )


if __name__ == "__main__":
    main()