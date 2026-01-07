#!/usr/bin/env python3
"""
Extract all 8 datasets with Claude Sonnet 4.5
CRITICAL: This must succeed on first try - no re-runs!
"""

import sys
import time
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from main import process_paper

# All 8 datasets
DATASETS = [
    {"id": "MLS", "pdf": "2012.03411v2", "name": "Multilingual LibriSpeech"},
    {"id": "FLORES", "pdf": "2106.03193v1", "name": "FLORES-101"},
    {"id": "CIFAR", "pdf": "2404.00498v2", "name": "CIFAR-10/100"},
    {"id": "Visual Genome", "pdf": "1602.07332v1", "name": "Visual Genome"},
    {"id": "MSCOCO", "pdf": "1405.0312v3", "name": "MS COCO"},
    {"id": "MMLU", "pdf": "2009.03300v3", "name": "MMLU"},
    {"id": "MMMU", "pdf": "2311.16502v4", "name": "MMMU"},
    {"id": "MathVista", "pdf": "2310.02255v3", "name": "MathVista"},
]

def check_if_extracted(dataset_id: str) -> bool:
    """Check if dataset already has Claude extraction"""
    result_file = Path(f"data/processed/{dataset_id}/full_pdf_metadata_result.json")
    if result_file.exists():
        # Check if it's recent (within last hour)
        mtime = result_file.stat().st_mtime
        age_seconds = time.time() - mtime
        if age_seconds < 3600:  # Less than 1 hour old
            return True
    return False

def main():
    """Extract all 8 datasets with robust error handling"""
    model_id = "claude-sonnet-4-5"
    
    print("=" * 100)
    print("EXTRACTING ALL 8 DATASETS WITH CLAUDE SONNET 4.5")
    print("=" * 100)
    print(f"Model: {model_id}")
    print(f"Datasets: {len(DATASETS)}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Strategy: 30s delay between extractions to avoid rate limits")
    print("=" * 100)
    print()
    
    results = []
    successful = 0
    failed = 0
    skipped = 0
    
    for i, dataset in enumerate(DATASETS, 1):
        dataset_id = dataset["id"]
        pdf_name = dataset["pdf"]
        display_name = dataset["name"]
        
        print(f"\n{'=' * 100}")
        print(f"DATASET {i}/{len(DATASETS)}: {display_name}")
        print(f"{'=' * 100}")
        print(f"ID: {dataset_id}")
        print(f"PDF: {pdf_name}.pdf")
        
        # Check if already extracted
        if check_if_extracted(dataset_id):
            print(f"⏭️  SKIPPED - Already extracted recently (< 1 hour ago)")
            skipped += 1
            results.append({
                'dataset': dataset_id,
                'status': 'skipped',
                'reason': 'Already extracted'
            })
            continue
        
        print(f"⏳ Starting extraction...")
        start_time = time.time()
        
        try:
            # Process with Claude Sonnet 4.5
            metadata = process_paper(
                paper_id=dataset_id,
                paper_path=pdf_name,
                model_id=model_id,
                extraction_mode="full-pdf"
            )
            
            elapsed = time.time() - start_time
            
            # Verify extraction success
            if metadata and 'name' in metadata:
                print(f"\n✅ SUCCESS - {display_name}")
                print(f"   Time: {elapsed:.2f}s")
                print(f"   Extracted fields: {len(metadata)}")
                print(f"   Output: data/processed/{dataset_id}/")
                
                successful += 1
                results.append({
                    'dataset': dataset_id,
                    'status': 'success',
                    'time': round(elapsed, 2),
                    'fields': len(metadata)
                })
            else:
                print(f"\n⚠️  WARNING - Extraction completed but metadata incomplete")
                print(f"   Time: {elapsed:.2f}s")
                failed += 1
                results.append({
                    'dataset': dataset_id,
                    'status': 'incomplete',
                    'time': round(elapsed, 2)
                })
            
            # Wait 30 seconds before next extraction (rate limit protection)
            if i < len(DATASETS):
                print(f"\n⏳ Waiting 30 seconds before next extraction (rate limit protection)...")
                time.sleep(30)
                
        except Exception as e:
            elapsed = time.time() - start_time
            
            print(f"\n❌ FAILED - {display_name}")
            print(f"   Error: {str(e)}")
            print(f"   Time: {elapsed:.2f}s")
            
            failed += 1
            results.append({
                'dataset': dataset_id,
                'status': 'failed',
                'error': str(e),
                'time': round(elapsed, 2)
            })
            
            # Critical: If extraction fails, wait longer before retry
            if i < len(DATASETS):
                print(f"\n⏳ Error occurred. Waiting 60 seconds before next extraction...")
                time.sleep(60)
    
    # Summary
    print(f"\n{'=' * 100}")
    print("EXTRACTION SUMMARY")
    print(f"{'=' * 100}")
    print(f"Total datasets:      {len(DATASETS)}")
    print(f"Successful:          {successful} ✅")
    print(f"Failed:              {failed} ❌")
    print(f"Skipped:             {skipped} ⏭️")
    print(f"{'=' * 100}")
    
    # Save results
    results_file = Path("claude_extraction_results.json")
    with open(results_file, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'model': model_id,
            'total': len(DATASETS),
            'successful': successful,
            'failed': failed,
            'skipped': skipped,
            'results': results
        }, f, indent=2)
    
    print(f"\n📄 Results saved to: {results_file}")
    
    if failed > 0:
        print(f"\n⚠️  WARNING: {failed} extractions failed. Review errors above.")
        return 1
    
    print(f"\n✅ ALL EXTRACTIONS COMPLETE!")
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
