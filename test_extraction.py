"""
Test script for debugging PDF extraction and chunking pipeline
No LLM calls - just tests PDF → sections → chunks
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from pdf.reader import extract_text_from_pdf
from pdf.processor import (
    clean_text,
    preprocess_for_section_detection,
    find_all_section_headers,
    extract_sections,
    extract_targeted_sections_with_tfidf,
    process_sections,
    chunk_for_llm
)
from metadata.relevance import select_relevant_sections


def test_extraction_pipeline(pdf_path):
    """Test the full extraction pipeline without LLM calls"""

    print("=" * 80)
    print(f"TESTING EXTRACTION PIPELINE")
    print(f"PDF: {pdf_path}")
    print("=" * 80)

    # Step 1: Extract raw text from PDF
    print("\n" + "=" * 80)
    print("STEP 1: PDF Text Extraction")
    print("=" * 80)
    raw_text = extract_text_from_pdf(pdf_path)
    if not raw_text:
        print("❌ Failed to extract text from PDF")
        return

    print(f"✓ Extracted {len(raw_text)} characters")
    print(f"\nFirst 500 characters of raw text:")
    print("-" * 80)
    print(raw_text[:500])
    print("-" * 80)

    # Step 2: Clean text
    print("\n" + "=" * 80)
    print("STEP 2: Text Cleaning")
    print("=" * 80)
    cleaned_text = clean_text(raw_text)
    print(f"✓ Cleaned text: {len(cleaned_text)} characters")
    print(f"\nFirst 500 characters after cleaning:")
    print("-" * 80)
    print(cleaned_text[:500])
    print("-" * 80)

    # Step 3: Preprocess for section detection
    print("\n" + "=" * 80)
    print("STEP 3: Preprocessing for Section Detection")
    print("=" * 80)
    preprocessed = preprocess_for_section_detection(cleaned_text)
    print(f"✓ Preprocessed text: {len(preprocessed)} characters")

    # Step 4: Find all section headers
    print("\n" + "=" * 80)
    print("STEP 4: Finding Section Headers")
    print("=" * 80)
    headers = find_all_section_headers(preprocessed)
    print(f"\n✓ Found {len(headers)} potential section headers:")
    for i, (start, end, num, title, full) in enumerate(headers[:20]):  # Show first 20
        print(f"  {i+1}. Section {num}: {title} - '{full}'")
    if len(headers) > 20:
        print(f"  ... and {len(headers) - 20} more")

    # Step 5: Extract all sections
    print("\n" + "=" * 80)
    print("STEP 5: Extracting All Sections (with sequential filtering)")
    print("=" * 80)
    all_sections = extract_sections(cleaned_text)
    print(f"\n✓ Extracted {len(all_sections)} sections after sequential filtering:")
    for i, section in enumerate(all_sections):
        content_preview = section['content'][:100].replace('\n', ' ')
        print(f"  {i+1}. [{section['section_number']}] {section['section_title']}")
        print(f"      Length: {len(section['content'])} chars")
        print(f"      Preview: {content_preview}...")

    # Step 6: Extract targeted sections with TF-IDF
    print("\n" + "=" * 80)
    print("STEP 6: Extracting Targeted Sections (Title + TF-IDF)")
    print("=" * 80)
    targeted_sections = extract_targeted_sections_with_tfidf(cleaned_text)
    print(f"\n✓ Found {len(targeted_sections)} targeted sections:")
    for i, section in enumerate(targeted_sections):
        method = section.get('selection_method', 'unknown')
        score_info = f" (TF-IDF: {section.get('tfidf_score', 0):.4f})" if method == "tfidf" else ""
        print(f"  {i+1}. [{section['section_number']}] {section['section_title']}")
        print(f"      Selection: {method}{score_info}")
        print(f"      Length: {len(section['content'])} chars")

    # Step 7: Process sections and create chunks
    print("\n" + "=" * 80)
    print("STEP 7: Processing Sections and Creating Chunks")
    print("=" * 80)
    processed_sections = process_sections(targeted_sections)
    print(f"\n✓ Processed {len(processed_sections)} sections")

    # Step 8: Prepare chunks for LLM
    print("\n" + "=" * 80)
    print("STEP 8: Preparing Chunks for LLM")
    print("=" * 80)
    llm_chunks = chunk_for_llm(processed_sections, max_chunk_size=12000)
    print(f"\n✓ Created {len(llm_chunks)} chunks:")
    for i, chunk in enumerate(llm_chunks):
        print(f"  {i+1}. {chunk['section_name']}")
        print(f"      Section: {chunk['section_title']}")
        print(f"      Length: {len(chunk['content'])} chars (~{len(chunk['content'])//4} tokens)")
        content_preview = chunk['content'][:100].replace('\n', ' ')
        print(f"      Preview: {content_preview}...")

    # Step 9: Select relevant sections (final filtering)
    print("\n" + "=" * 80)
    print("STEP 9: Selecting Relevant Sections (Final Filter)")
    print("=" * 80)
    relevant_chunks = select_relevant_sections(llm_chunks, max_sections=15)
    print(f"\n✓ Selected {len(relevant_chunks)} relevant chunks for LLM processing")

    # Summary statistics
    print("\n" + "=" * 80)
    print("SUMMARY STATISTICS")
    print("=" * 80)
    print(f"Total raw text:              {len(raw_text):,} chars")
    print(f"Total cleaned text:          {len(cleaned_text):,} chars")
    print(f"Section headers found:       {len(headers)}")
    print(f"Sections extracted:          {len(all_sections)}")
    print(f"Targeted sections:           {len(targeted_sections)}")
    print(f"  - By title:                {sum(1 for s in targeted_sections if s.get('selection_method') == 'title')}")
    print(f"  - By TF-IDF:               {sum(1 for s in targeted_sections if s.get('selection_method') == 'tfidf')}")
    print(f"Total chunks created:        {len(llm_chunks)}")
    print(f"Relevant chunks (final):     {len(relevant_chunks)}")
    print(f"Average chunk size:          {sum(len(c['content']) for c in llm_chunks) // max(1, len(llm_chunks)):,} chars")
    print(f"Total content to process:    {sum(len(c['content']) for c in relevant_chunks):,} chars")

    # Check for important sections
    print("\n" + "=" * 80)
    print("IMPORTANT SECTIONS CHECK")
    print("=" * 80)
    has_abstract = any('abstract' in s['section_title'].lower() for s in targeted_sections)
    has_intro = any('introduction' in s['section_title'].lower() for s in targeted_sections)
    has_dataset = any('dataset' in s['section_title'].lower() or 'data' in s['section_title'].lower()
                     for s in targeted_sections)

    print(f"Has Abstract:     {'✓' if has_abstract else '✗'}")
    print(f"Has Introduction: {'✓' if has_intro else '✗'}")
    print(f"Has Dataset:      {'✓' if has_dataset else '✗'}")

    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)

    return {
        'raw_text': raw_text,
        'cleaned_text': cleaned_text,
        'headers': headers,
        'all_sections': all_sections,
        'targeted_sections': targeted_sections,
        'llm_chunks': llm_chunks,
        'relevant_chunks': relevant_chunks
    }


if __name__ == "__main__":
    # Test with the PDF in data folder
    pdf_path = Path(__file__).parent / "data" / "2110.14168v2.pdf"

    if not pdf_path.exists():
        print(f"❌ PDF not found: {pdf_path}")
        print("\nAvailable files in data/:")
        data_dir = Path(__file__).parent / "data"
        if data_dir.exists():
            for f in data_dir.iterdir():
                print(f"  - {f.name}")
        sys.exit(1)

    results = test_extraction_pipeline(pdf_path)
