#!/usr/bin/env python3
"""
Keyword/regex baseline for metadata extraction.

Extracts metadata using pattern matching without any LLM.
Serves as a non-LLM baseline for comparison in the paper.

Status: TODO — assigned to a contributor (see docs/CONTRIBUTING.md)

Usage:
    python scripts/baselines/keyword_baseline.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

def main():
    print("Keyword baseline: not yet implemented")
    print("See docs/CONTRIBUTING.md for task specification")
    print("Assigned to: a team member")

if __name__ == "__main__":
    main()
