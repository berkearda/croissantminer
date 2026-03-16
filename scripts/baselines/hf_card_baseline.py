#!/usr/bin/env python3
"""
HuggingFace dataset card baseline for metadata extraction.

Extracts metadata from HuggingFace README.md cards instead of papers.
Compares card-only vs paper-only vs combined approaches.

Status: TODO — assigned to Nobin (see docs/CONTRIBUTING.md)

Usage:
    python scripts/baselines/hf_card_baseline.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

def main():
    print("HuggingFace card baseline: not yet implemented")
    print("See docs/CONTRIBUTING.md for task specification")
    print("Assigned to: a team member")

if __name__ == "__main__":
    main()
