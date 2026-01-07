"""
Test extraction pipeline on multiple PDFs to ensure robustness
"""

import sys
from pathlib import Path
import json

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


def test_single_pdf(pdf_path):
    """Test extraction on a single PDF and return results"""

    results = {
        'pdf_name': pdf_path.name,
        'success': False,
        'error': None,
        'stats': {}
    }

    try:
        # Extract text
        raw_text = extract_text_from_pdf(pdf_path)
        if not raw_text:
            results['error'] = "Failed to extract text"
            return results

        results['stats']['raw_text_chars'] = len(raw_text)

        # Clean text
        cleaned_text = clean_text(raw_text)
        results['stats']['cleaned_text_chars'] = len(cleaned_text)

        # Extract targeted sections
        targeted_sections = extract_targeted_sections_with_tfidf(cleaned_text)
        results['stats']['targeted_sections'] = len(targeted_sections)

        # Count section types
        section_types = {}
        for section in targeted_sections:
            section_type = section.get('section_title', 'Unknown')
            section_types[section_type] = section_types.get(section_type, 0) + 1
        results['stats']['section_types'] = section_types

        # Process sections
        processed_sections = process_sections(targeted_sections)
        results['stats']['processed_sections'] = len(processed_sections)

        # Create chunks
        llm_chunks = chunk_for_llm(processed_sections, max_chunk_size=12000)
        results['stats']['llm_chunks'] = len(llm_chunks)

        # Select relevant sections
        relevant_chunks = select_relevant_sections(llm_chunks, max_sections=15)
        results['stats']['relevant_chunks'] = len(relevant_chunks)

        # Calculate coverage
        total_content = sum(len(c['content']) for c in relevant_chunks)
        results['stats']['total_content_chars'] = total_content
        results['stats']['avg_chunk_size'] = total_content // max(1, len(relevant_chunks))

        # Check for important sections
        chunk_names = [c['section_name'].lower() for c in relevant_chunks]
        results['stats']['has_abstract'] = any('abstract' in name for name in chunk_names)
        results['stats']['has_introduction'] = any('introduction' in name for name in chunk_names)
        results['stats']['has_dataset'] = any('dataset' in name or 'data' in name for name in chunk_names)
        results['stats']['has_methods'] = any('method' in name or 'approach' in name for name in chunk_names)
        results['stats']['has_rai'] = any(keyword in ' '.join(chunk_names)
                                          for keyword in ['ethic', 'limitation', 'bias', 'fairness', 'privacy'])

        results['success'] = True

    except Exception as e:
        results['error'] = str(e)

    return results


def main():
    """Test all PDFs in the data folder"""

    print("=" * 80)
    print("TESTING EXTRACTION PIPELINE ON MULTIPLE PDFs")
    print("=" * 80)

    data_dir = Path(__file__).parent / "data"
    pdf_files = sorted(data_dir.glob("*.pdf"))

    if not pdf_files:
        print("❌ No PDF files found in data/")
        return

    print(f"\nFound {len(pdf_files)} PDF files:")
    for pdf in pdf_files:
        print(f"  - {pdf.name} ({pdf.stat().st_size / 1024 / 1024:.1f} MB)")

    print("\n" + "=" * 80)
    print("RUNNING TESTS")
    print("=" * 80)

    all_results = []

    for i, pdf_path in enumerate(pdf_files, 1):
        print(f"\n[{i}/{len(pdf_files)}] Testing: {pdf_path.name}")
        print("-" * 80)

        result = test_single_pdf(pdf_path)
        all_results.append(result)

        if result['success']:
            stats = result['stats']
            print(f"✅ SUCCESS")
            print(f"   Text: {stats['raw_text_chars']:,} chars")
            print(f"   Targeted sections: {stats['targeted_sections']}")
            print(f"   Section types: {stats['section_types']}")
            print(f"   Final chunks: {stats['relevant_chunks']}")
            print(f"   Total content: {stats['total_content_chars']:,} chars")
            print(f"   Has Abstract: {'✓' if stats['has_abstract'] else '✗'}")
            print(f"   Has Introduction: {'✓' if stats['has_introduction'] else '✗'}")
            print(f"   Has Dataset: {'✓' if stats['has_dataset'] else '✗'}")
            print(f"   Has Methods: {'✓' if stats['has_methods'] else '✗'}")
            print(f"   Has RAI sections: {'✓' if stats['has_rai'] else '✗'}")
        else:
            print(f"❌ FAILED: {result['error']}")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    successful = [r for r in all_results if r['success']]
    failed = [r for r in all_results if not r['success']]

    print(f"\nSuccess rate: {len(successful)}/{len(all_results)} ({len(successful)/len(all_results)*100:.1f}%)")

    if failed:
        print(f"\n❌ Failed PDFs:")
        for result in failed:
            print(f"   - {result['pdf_name']}: {result['error']}")

    if successful:
        print(f"\n✅ Statistics across successful PDFs:")

        # Aggregate stats
        avg_targeted = sum(r['stats']['targeted_sections'] for r in successful) / len(successful)
        avg_chunks = sum(r['stats']['relevant_chunks'] for r in successful) / len(successful)
        avg_content = sum(r['stats']['total_content_chars'] for r in successful) / len(successful)

        has_abstract = sum(1 for r in successful if r['stats']['has_abstract'])
        has_intro = sum(1 for r in successful if r['stats']['has_introduction'])
        has_dataset = sum(1 for r in successful if r['stats']['has_dataset'])
        has_methods = sum(1 for r in successful if r['stats']['has_methods'])
        has_rai = sum(1 for r in successful if r['stats']['has_rai'])

        print(f"   Avg targeted sections: {avg_targeted:.1f}")
        print(f"   Avg final chunks: {avg_chunks:.1f}")
        print(f"   Avg content size: {avg_content:,.0f} chars")
        print(f"\n   Section coverage:")
        print(f"   - Abstract: {has_abstract}/{len(successful)} ({has_abstract/len(successful)*100:.0f}%)")
        print(f"   - Introduction: {has_intro}/{len(successful)} ({has_intro/len(successful)*100:.0f}%)")
        print(f"   - Dataset: {has_dataset}/{len(successful)} ({has_dataset/len(successful)*100:.0f}%)")
        print(f"   - Methods: {has_methods}/{len(successful)} ({has_methods/len(successful)*100:.0f}%)")
        print(f"   - RAI sections: {has_rai}/{len(successful)} ({has_rai/len(successful)*100:.0f}%)")

        # Section type distribution
        print(f"\n   Section type distribution:")
        all_section_types = {}
        for r in successful:
            for stype, count in r['stats']['section_types'].items():
                all_section_types[stype] = all_section_types.get(stype, 0) + count

        for stype, count in sorted(all_section_types.items(), key=lambda x: -x[1]):
            print(f"   - {stype}: {count}")

    # Save results to JSON
    output_file = Path(__file__).parent / "test_results.json"
    with open(output_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    print(f"\n📄 Detailed results saved to: {output_file}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
