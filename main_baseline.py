"""
Complete baseline pipeline that processes BOTH papers and dataset cards,
then unifies results - matching your LLM approach methodology.
"""

import argparse
import time
import json
from pathlib import Path
from collections import Counter

from config import (
    RAW_DATA_DIR, 
    PROCESSED_DATA_DIR, 
    DATACARD_DIR,
    MAX_SECTION_TOKENS,
    MAX_SECTIONS
)

from pdf.reader import download_pdf, extract_text_from_pdf
from pdf.processor import (
    clean_text, 
    process_paper as process_paper_text,
    chunk_for_llm,
    save_processed_paper
)

from metadata.relevance import select_relevant_sections
from metadata.card_parser import parse_dataset_card
from baseline_extractors import run_all_baselines


def process_paper_with_unified_baselines(paper_id, paper_url=None, paper_path=None, dataset_card_path=None):
    """
    Complete baseline pipeline that matches your LLM approach:
    1. Process PDF paper with baselines
    2. Process dataset card with baselines  
    3. Unify results like your LLM pipeline does
    """
    print(f"===== Processing paper with unified baselines: {paper_id} =====")
    start_time = time.time()
    
    # Create directories
    paper_dir = PROCESSED_DATA_DIR / paper_id
    baseline_dir = paper_dir / "baselines_unified"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    
    # Step 1: Process PDF paper
    print("\n" + "="*60)
    print("STEP 1: PROCESSING PDF PAPER")
    print("="*60)
    
    if paper_path:
        pdf_path = RAW_DATA_DIR / f"{paper_path}.pdf"
    elif paper_url:
        pdf_path = RAW_DATA_DIR / f"{paper_id}.pdf"
        download_pdf(paper_url, pdf_path)
    else:
        raise ValueError("Either paper_url or paper_path must be provided")
    
    # Extract and process PDF
    raw_text = extract_text_from_pdf(pdf_path)
    cleaned_text = clean_text(raw_text)
    processed_paper = process_paper_text(cleaned_text, baseline_dir / "processed_sections.json", debug=False)
    processed_sections = processed_paper['sections']
    
    # Get relevant sections
    llm_sections = chunk_for_llm(processed_sections, MAX_SECTION_TOKENS)
    relevant_sections = select_relevant_sections(llm_sections, MAX_SECTIONS)
    
    print(f"✓ Extracted {len(relevant_sections)} relevant sections from PDF")
    
    # Run baselines on PDF
    print(f"\n----- Running baselines on PDF content -----")
    pdf_baseline_results = run_all_baselines(relevant_sections, baseline_dir)
    
    # Step 2: Process Dataset Card
    print("\n" + "="*60)
    print("STEP 2: PROCESSING DATASET CARD")
    print("="*60)
    
    card_baseline_results = {}
    
    if dataset_card_path and Path(dataset_card_path).exists():
        print(f"Processing dataset card: {dataset_card_path}")
        
        # Parse dataset card content
        try:
            with open(dataset_card_path, 'r', encoding='utf-8') as f:
                card_content = f.read()
            
            # Convert card to sections format for baseline processing
            card_sections = [{
                'section_name': 'Dataset Card',
                'content': card_content
            }]
            
            print(f"✓ Loaded dataset card ({len(card_content)} characters)")
            
            # Run baselines on dataset card
            print(f"\n----- Running baselines on dataset card content -----")
            card_baseline_results = run_all_baselines(card_sections, baseline_dir)
            
            # Save card results separately
            card_results_path = baseline_dir / "card_baseline_results.json"
            with open(card_results_path, 'w', encoding='utf-8') as f:
                json.dump(card_baseline_results, f, indent=2, ensure_ascii=False)
            print(f"✓ Saved card baseline results to {card_results_path}")
            
        except Exception as e:
            print(f"❌ Error processing dataset card: {e}")
            card_baseline_results = {}
    else:
        print(f"⚠️ No dataset card found at: {dataset_card_path}")
        # Create empty card results
        card_baseline_results = {
            "regex_baseline": create_empty_metadata(),
            "ner_baseline": create_empty_metadata(), 
            "tfidf_baseline": create_empty_metadata()
        }
    
    # Step 3: Unify Results
    print("\n" + "="*60)
    print("STEP 3: UNIFYING BASELINE RESULTS")
    print("="*60)
    
    unified_results = {}
    
    baseline_methods = ["regex_baseline", "ner_baseline", "tfidf_baseline"]
    
    for method in baseline_methods:
        print(f"\n----- Unifying {method} results -----")
        
        pdf_result = pdf_baseline_results.get(method, create_empty_metadata())
        card_result = card_baseline_results.get(method, create_empty_metadata())
        
        # Unify using same logic as your LLM approach
        unified = unify_baseline_metadata(pdf_result, card_result, method)
        unified_results[method] = unified
        
        # Count meaningful fields
        meaningful_count = count_meaningful_fields(unified)
        print(f"✓ {method} unified result: {meaningful_count} meaningful fields")
    
    # Step 4: Save Results and Analysis
    print("\n" + "="*60)
    print("STEP 4: SAVING RESULTS")
    print("="*60)
    
    # Save unified results
    unified_path = baseline_dir / "unified_baseline_results.json"
    with open(unified_path, 'w', encoding='utf-8') as f:
        json.dump(unified_results, f, indent=2, ensure_ascii=False)
    print(f"✓ Saved unified baseline results to {unified_path}")
    
    # Create comparison analysis
    analysis = analyze_unified_baselines(pdf_baseline_results, card_baseline_results, unified_results)
    
    analysis_path = baseline_dir / "unified_baseline_analysis.json"
    with open(analysis_path, 'w', encoding='utf-8') as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)
    print(f"✓ Saved analysis to {analysis_path}")
    
    # Print summary
    print_baseline_summary(analysis)
    
    # Done
    elapsed_time = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"UNIFIED BASELINE PROCESSING COMPLETED")
    print(f"{'='*60}")
    print(f"Paper: {paper_id}")
    print(f"Total time: {elapsed_time:.2f} seconds")
    print(f"Results saved to: {baseline_dir}")
    
    return {
        'paper_id': paper_id,
        'processing_time': elapsed_time,
        'pdf_results': pdf_baseline_results,
        'card_results': card_baseline_results,
        'unified_results': unified_results,
        'analysis': analysis
    }


def create_empty_metadata():
    """Create empty metadata in correct format"""
    return {
        "description": "Not mentioned",
        "license": "Not mentioned", 
        "name": "Not mentioned",
        "url": "Not mentioned",
        "creator": {"@type": "Person", "name": "Not mentioned"},
        "publisher": "Not mentioned",
        "datePublished": "Not mentioned",
        "inLanguage": "Not mentioned",
        "citeAs": "Not mentioned",
        "isLiveDataset": "Not mentioned",
        "dataCollection": "Not mentioned",
        "dataCollectionTimeframe": "Not mentioned",
        "dataAnnotationPlatform": "Not mentioned",
        "annotatorDemographics": "Not mentioned",
        "dataUseCases": "Not mentioned",
        "personalSensitiveInformation": "Not mentioned"
    }


def unify_baseline_metadata(pdf_result, card_result, method_name):
    """
    Unify PDF and card results using same logic as LLM approach:
    Dataset cards are authoritative, PDF provides context
    """
    unified = create_empty_metadata()
    
    print(f"  Unifying {method_name}:")
    
    changes_made = []
    
    # Go through each field
    for field in unified.keys():
        pdf_value = get_field_value(pdf_result, field)
        card_value = get_field_value(card_result, field)
        
        # Priority: Card > PDF > Default
        if card_value != "Not mentioned":
            unified[field] = card_value if field != 'creator' else {"@type": "Person", "name": card_value}
            if pdf_value != "Not mentioned":
                changes_made.append(f"    {field}: Used card value (had both sources)")
            else:
                changes_made.append(f"    {field}: Used card value (only source)")
                
        elif pdf_value != "Not mentioned":
            unified[field] = pdf_value if field != 'creator' else {"@type": "Person", "name": pdf_value}
            changes_made.append(f"    {field}: Used PDF value (only source)")
    
    # Handle creator field special case
    if isinstance(pdf_result.get('creator'), dict) and pdf_result['creator'].get('name') != "Not mentioned":
        if unified['creator']['name'] == "Not mentioned":
            unified['creator'] = pdf_result['creator']
            changes_made.append(f"    creator: Used PDF creator object")
    
    if isinstance(card_result.get('creator'), dict) and card_result['creator'].get('name') != "Not mentioned":
        unified['creator'] = card_result['creator']
        changes_made.append(f"    creator: Used card creator object (overriding PDF)")
    
    if changes_made:
        for change in changes_made[:3]:  # Show first 3 changes
            print(change)
        if len(changes_made) > 3:
            print(f"    ... and {len(changes_made) - 3} more fields")
    else:
        print("    No meaningful fields found in either source")
    
    return unified


def get_field_value(metadata, field):
    """Get field value, handling creator object"""
    if field == 'creator':
        if isinstance(metadata.get('creator'), dict):
            return metadata['creator'].get('name', 'Not mentioned')
        else:
            return metadata.get('creator', 'Not mentioned')
    else:
        return metadata.get(field, 'Not mentioned')


def count_meaningful_fields(metadata):
    """Count fields with meaningful values"""
    count = 0
    for field, value in metadata.items():
        if field == 'creator':
            if isinstance(value, dict) and value.get('name') != 'Not mentioned':
                count += 1
        elif value != 'Not mentioned':
            count += 1
    return count


def analyze_unified_baselines(pdf_results, card_results, unified_results):
    """Analyze the unification process"""
    analysis = {
        'method_performance': {},
        'source_contribution': {'pdf_only': 0, 'card_only': 0, 'both_sources': 0},
        'field_coverage': {},
        'unification_impact': {}
    }
    
    baseline_methods = ["regex_baseline", "ner_baseline", "tfidf_baseline"]
    
    for method in baseline_methods:
        pdf_count = count_meaningful_fields(pdf_results.get(method, {}))
        card_count = count_meaningful_fields(card_results.get(method, {}))
        unified_count = count_meaningful_fields(unified_results.get(method, {}))
        
        analysis['method_performance'][method] = {
            'pdf_fields': pdf_count,
            'card_fields': card_count,
            'unified_fields': unified_count,
            'improvement': unified_count - max(pdf_count, card_count)
        }
    
    # Overall field coverage
    all_fields = list(create_empty_metadata().keys())
    for field in all_fields:
        field_stats = {'extracted_by': []}
        
        for method in baseline_methods:
            unified = unified_results.get(method, {})
            if get_field_value(unified, field) != "Not mentioned":
                field_stats['extracted_by'].append(method)
        
        analysis['field_coverage'][field] = field_stats
    
    return analysis


def print_baseline_summary(analysis):
    """Print summary of unified baseline results"""
    print(f"\n📊 UNIFIED BASELINE SUMMARY")
    print(f"{'='*50}")
    
    # Method performance
    print(f"\n🔧 METHOD PERFORMANCE:")
    for method, stats in analysis['method_performance'].items():
        print(f"  {method.replace('_', ' ').title()}:")
        print(f"    PDF: {stats['pdf_fields']} fields")
        print(f"    Card: {stats['card_fields']} fields") 
        print(f"    Unified: {stats['unified_fields']} fields")
        print(f"    Improvement: +{stats['improvement']}")
    
    # Field coverage
    print(f"\n✅ FIELD EXTRACTION SUCCESS:")
    successful_fields = [field for field, data in analysis['field_coverage'].items() 
                        if len(data['extracted_by']) > 0]
    print(f"  Successfully extracted: {len(successful_fields)}/16 fields")
    
    if successful_fields:
        print(f"  Fields found: {', '.join(successful_fields[:5])}")
        if len(successful_fields) > 5:
            print(f"    ... and {len(successful_fields) - 5} more")


def main():
    """Command-line interface"""
    parser = argparse.ArgumentParser(description="Run unified baseline extraction (PDF + Card)")
    default_card_path = DATACARD_DIR / "VisualGenome.txt"
    parser.add_argument("--paper-id", default='visualgenome', help="Paper identifier")
    parser.add_argument("--paper-path", default='visualgenome', help="Path to PDF file")
    parser.add_argument("--dataset-card", default=str(default_card_path), help="Path to dataset card file")
    
    args = parser.parse_args()
    
    # Auto-detect dataset card if not provided
    if not args.dataset_card:
        possible_cards = [
            DATACARD_DIR / f"{args.paper_id}.txt",
            DATACARD_DIR / f"{args.paper_id.upper()}.txt",
            DATACARD_DIR / f"{args.paper_id.title()}.txt"
        ]
        
        for card_path in possible_cards:
            if card_path.exists():
                args.dataset_card = str(card_path)
                print(f"✓ Auto-detected dataset card: {card_path}")
                break
        else:
            print(f"⚠️ No dataset card found, will process PDF only")
    
    try:
        result = process_paper_with_unified_baselines(
            paper_id=args.paper_id,
            paper_path=args.paper_path,
            dataset_card_path=args.dataset_card
        )
        
        print(f"\n🎉 Successfully processed {args.paper_id} with unified baselines!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        raise


if __name__ == "__main__":
    main()