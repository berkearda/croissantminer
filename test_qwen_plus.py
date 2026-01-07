#!/usr/bin/env python3
"""Test Qwen-Plus on MLS paper"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from main import process_paper

print("=" * 80)
print("TESTING QWEN-PLUS ON MLS PAPER")
print("=" * 80)
print("Expected accuracy: 68-73%")
print()

start_time = time.time()

try:
    metadata = process_paper(
        paper_id="MLS",
        paper_path="2012.03411v2",
        model_id="qwen-plus",
        extraction_mode="full-pdf"
    )
    
    elapsed = time.time() - start_time
    print(f"\n✅ SUCCESS - Time: {elapsed:.2f}s")
    
except Exception as e:
    elapsed = time.time() - start_time
    print(f"\n❌ FAILED - Time: {elapsed:.2f}s")
    print(f"Error: {e}")
