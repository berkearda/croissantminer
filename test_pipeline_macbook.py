"""
Simple validation script to test the CroissantMiner pipeline on MacBook with OpenAI API
"""

import sys
import os
from pathlib import Path
import argparse
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from pdf.reader import extract_text_from_pdf
from pdf.processor import (
    clean_text,
    extract_targeted_sections_with_tfidf,
    process_sections,
    chunk_for_llm
)
from metadata.relevance import select_relevant_sections
from metadata.extractor import setup_llm_pipeline, extract_metadata, parse_metadata_results
from metadata.unifier import unify_metadata, convert_to_croissant


def test_pipeline(pdf_path, model_name="gpt-4o-mini", max_sections=15):
    """
    Test the complete extraction pipeline on a single PDF

    Args:
        pdf_path (str): Path to the PDF file
        model_name (str): Model to use for extraction
        max_sections (int): Maximum number of sections to process
    """
    print("=" * 80)
    print("CROISSANTMINER PIPELINE VALIDATION TEST")
    print("=" * 80)

    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        print(f"❌ PDF not found: {pdf_path}")
        return False

    print(f"\n📄 Testing with: {pdf_path.name}")
    print(f"🤖 Using model: {model_name}")
    print(f"📊 Max sections: {max_sections}")

    try:
        # Step 1: Extract text from PDF
        print("\n" + "=" * 80)
        print("STEP 1: Extracting text from PDF")
        print("=" * 80)
        raw_text = extract_text_from_pdf(pdf_path)
        if not raw_text:
            print("❌ Failed to extract text from PDF")
            return False
        print(f"✅ Extracted {len(raw_text):,} characters")

        # Step 2: Clean text
        print("\n" + "=" * 80)
        print("STEP 2: Cleaning text")
        print("=" * 80)
        cleaned_text = clean_text(raw_text)
        print(f"✅ Cleaned text: {len(cleaned_text):,} characters")

        # Step 3: Extract targeted sections with TF-IDF
        print("\n" + "=" * 80)
        print("STEP 3: Extracting targeted sections with TF-IDF")
        print("=" * 80)
        targeted_sections = extract_targeted_sections_with_tfidf(cleaned_text)
        print(f"✅ Found {len(targeted_sections)} targeted sections")

        # Show section breakdown
        section_types = {}
        for section in targeted_sections:
            section_type = section.get('section_title', 'Unknown')
            section_types[section_type] = section_types.get(section_type, 0) + 1

        print("\n📋 Section breakdown:")
        for stype, count in sorted(section_types.items(), key=lambda x: -x[1]):
            print(f"   - {stype}: {count}")

        # Step 4: Process sections
        print("\n" + "=" * 80)
        print("STEP 4: Processing sections")
        print("=" * 80)
        processed_sections = process_sections(targeted_sections)
        print(f"✅ Processed {len(processed_sections)} sections")

        # Step 5: Create chunks for LLM
        print("\n" + "=" * 80)
        print("STEP 5: Creating chunks for LLM")
        print("=" * 80)
        llm_chunks = chunk_for_llm(processed_sections, max_chunk_size=12000)
        print(f"✅ Created {len(llm_chunks)} chunks")

        total_chars = sum(len(c['content']) for c in llm_chunks)
        print(f"   Total content: {total_chars:,} characters")
        print(f"   Avg chunk size: {total_chars // max(1, len(llm_chunks)):,} characters")

        # Step 6: Select relevant sections
        print("\n" + "=" * 80)
        print("STEP 6: Selecting most relevant sections")
        print("=" * 80)
        relevant_chunks = select_relevant_sections(llm_chunks, max_sections=max_sections)
        print(f"✅ Selected {len(relevant_chunks)} most relevant sections")

        print("\n📋 Selected sections:")
        for i, chunk in enumerate(relevant_chunks, 1):
            print(f"   {i}. {chunk['section_name']} ({len(chunk['content'])} chars)")

        # Step 7: Setup LLM
        print("\n" + "=" * 80)
        print("STEP 7: Setting up LLM for metadata extraction")
        print("=" * 80)

        # Check API key
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("❌ OPENAI_API_KEY not found in environment")
            print("   Please set it in .env file or export it:")
            print("   export OPENAI_API_KEY='your-key-here'")
            return False
        print(f"✅ API key found: {api_key[:15]}...{api_key[-10:]}")

        llm_pipeline = setup_llm_pipeline(model_name)
        print(f"✅ LLM pipeline ready")

        # Step 8: Extract metadata with LLM
        print("\n" + "=" * 80)
        print("STEP 8: Extracting metadata with LLM")
        print("=" * 80)
        print(f"⏳ Processing {len(relevant_chunks)} sections with {model_name}...")
        print("   (This may take 1-2 minutes)")

        # Create output directory
        output_dir = Path(__file__).parent / "validation_output"
        output_dir.mkdir(exist_ok=True)

        section_results = extract_metadata(relevant_chunks, llm_pipeline, output_dir)
        print(f"✅ Extracted metadata from {len(section_results)} sections")

        # Step 9: Parse and unify metadata
        print("\n" + "=" * 80)
        print("STEP 9: Parsing and unifying metadata")
        print("=" * 80)
        metadata_list = parse_metadata_results(section_results)
        print(f"✅ Parsed {len(metadata_list)} metadata entries")

        if not metadata_list:
            print("⚠️ No valid metadata was extracted")
            return False

        unified_metadata, ambiguous_fields = unify_metadata(metadata_list, output_dir)
        print(f"✅ Unified metadata created")

        if ambiguous_fields:
            print(f"⚠️ Found {len(ambiguous_fields)} ambiguous fields")

        # Step 10: Convert to Croissant format
        print("\n" + "=" * 80)
        print("STEP 10: Converting to Croissant format")
        print("=" * 80)
        croissant_metadata = convert_to_croissant(unified_metadata, output_dir)
        print(f"✅ Croissant metadata generated")

        # Save validation summary
        print("\n" + "=" * 80)
        print("VALIDATION SUMMARY")
        print("=" * 80)

        summary = {
            "pdf_name": pdf_path.name,
            "model_used": model_name,
            "success": True,
            "stats": {
                "raw_text_chars": len(raw_text),
                "cleaned_text_chars": len(cleaned_text),
                "targeted_sections": len(targeted_sections),
                "processed_sections": len(processed_sections),
                "llm_chunks": len(llm_chunks),
                "relevant_chunks": len(relevant_chunks),
                "metadata_entries": len(metadata_list),
                "section_types": section_types,
                "has_abstract": any('abstract' in s.get('section_title', '').lower() for s in targeted_sections),
                "has_introduction": any('introduction' in s.get('section_title', '').lower() for s in targeted_sections),
                "has_dataset": any('dataset' in s.get('section_title', '').lower() or 'data' in s.get('section_title', '').lower() for s in targeted_sections),
                "has_methods": any('method' in s.get('section_title', '').lower() for s in targeted_sections),
            },
            "croissant_fields_extracted": list(croissant_metadata.keys()) if croissant_metadata else []
        }

        summary_file = output_dir / "validation_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)

        print(f"\n✅ SUCCESS!")
        print(f"   📁 Results saved to: {output_dir}")
        print(f"   📄 Summary: {summary_file}")
        print(f"   📊 Croissant metadata: {output_dir / 'croissant_metadata.json'}")

        # Show key extracted fields
        print(f"\n📋 Key metadata fields extracted:")
        for key, value in list(unified_metadata.items())[:10]:
            if isinstance(value, dict):
                print(f"   - {key}: {value.get('name', 'N/A')}")
            elif isinstance(value, str) and len(value) > 50:
                print(f"   - {key}: {value[:50]}...")
            else:
                print(f"   - {key}: {value}")

        print("\n" + "=" * 80)
        print("VALIDATION TEST COMPLETED SUCCESSFULLY")
        print("=" * 80)

        return True

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Command-line interface"""
    parser = argparse.ArgumentParser(description="Test CroissantMiner pipeline on MacBook")
    parser.add_argument("--pdf", default="data/2110.14168v2.pdf", help="Path to PDF file")
    parser.add_argument("--model", default="gpt-4o-mini", help="Model to use (gpt-4o-mini, gpt-4o, etc.)")
    parser.add_argument("--max-sections", type=int, default=15, help="Maximum sections to process")

    args = parser.parse_args()

    success = test_pipeline(args.pdf, args.model, args.max_sections)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
