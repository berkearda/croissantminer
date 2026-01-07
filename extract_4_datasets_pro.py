#!/usr/bin/env python3
"""
Extract only the 4 missing datasets with Gemini 2.5 Pro
"""

import sys
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from main import process_paper

# Only the 4 datasets that need re-extraction
DATASETS = [
    {"id": "MLS", "pdf": "2012.03411v2", "name": "Multilingual LibriSpeech"},
    {"id": "FLORES", "pdf": "2106.03193v1", "name": "FLORES-101"},
    {"id": "CIFAR", "pdf": "2404.00498v2", "name": "CIFAR-10/100"},
    {"id": "Visual Genome", "pdf": "1602.07332v1", "name": "Visual Genome"},
]

def main():
    """Extract 4 datasets with Gemini 2.5 Pro"""
    model_id = "gemini-2.5-pro"
    
    print("=" * 100)
    print("RE-EXTRACTING 4 DATASETS WITH GEMINI 2.5 PRO")
    print("=" * 100)
    print(f"Model: {model_id}")
    print(f"Datasets: {len(DATASETS)}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 100)
    print()
    
    for i, dataset in enumerate(DATASETS, 1):
        dataset_id = dataset["id"]
        pdf_name = dataset["pdf"]
        display_name = dataset["name"]
        
        print(f"\n{'=' * 100}")
        print(f"DATASET {i}/{len(DATASETS)}: {display_name}")
        print(f"{'=' * 100}")
        
        start_time = time.time()
        
        try:
            # Process with full-PDF mode
            metadata = process_paper(
                paper_id=dataset_id,
                paper_path=pdf_name,
                model_id=model_id,
                extraction_mode="full-pdf"
            )
            
            elapsed = time.time() - start_time
            
            print(f"\n✅ SUCCESS - {display_name}")
            print(f"   Time: {elapsed:.2f}s")
            
            # Wait 90 seconds before next request (rate limit protection)
            if i < len(DATASETS):
                print(f"\n⏳ Waiting 90 seconds before next extraction (rate limit protection)...")
                time.sleep(90)
                
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"\n❌ FAILED - {display_name}")
            print(f"   Error: {str(e)}")
            
            # Still wait before retry
            if i < len(DATASETS):
                print(f"\n⏳ Waiting 90 seconds before next extraction...")
                time.sleep(90)
    
    print(f"\n{'=' * 100}")
    print("✅ RE-EXTRACTION COMPLETE")
    print(f"{'=' * 100}\n")

if __name__ == "__main__":
    main()
