#!/usr/bin/env python3
"""Test Claude Sonnet 4.5 on MLS paper"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from main import process_paper

print("=" * 80)
print("TESTING CLAUDE SONNET 4.5 ON MLS PAPER")
print("=" * 80)
print("Model: claude-sonnet-4-5-20250929")
print("Expected accuracy: 78-82% (vs 70.2% Gemini Flash baseline)")
print("=" * 80)
print()

start_time = time.time()

try:
    metadata = process_paper(
        paper_id="MLS",
        paper_path="2012.03411v2",
        model_id="claude-sonnet-4-5",
        extraction_mode="full-pdf"
    )
    
    elapsed = time.time() - start_time
    print(f"\n✅ SUCCESS - Time: {elapsed:.2f}s")
    print(f"   Output: data/processed/MLS/")
    print()
    print("Extracted metadata fields:")
    for key, value in metadata.items():
        if not key.startswith("@"):
            value_preview = str(value)[:80] + "..." if len(str(value)) > 80 else str(value)
            print(f"  {key}: {value_preview}")
    
except Exception as e:
    elapsed = time.time() - start_time
    print(f"\n❌ FAILED - Time: {elapsed:.2f}s")
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
