#!/usr/bin/env python3
"""
Download all 103 dataset papers from arXiv/web to data/raw/.

Usage:
    python scripts/download_papers.py              # download all
    python scripts/download_papers.py --check      # check which are missing
    python scripts/download_papers.py --paper AI4Math_MathVista  # download one
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
RAW_DIR = ROOT / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

def load_paper_links():
    with open(ROOT / "data" / "paper_links.json") as f:
        return json.load(f)

def arxiv_pdf_url(url):
    """Convert arXiv abstract URL to PDF URL."""
    m = re.search(r'(\d{4}\.\d{4,5})', url)
    if m:
        return f"https://arxiv.org/pdf/{m.group(1)}.pdf"
    return None

def download_pdf(url, dest_path, timeout=60):
    """Download a PDF from URL."""
    req = urllib.request.Request(url)
    req.add_header('User-Agent', 'CroissantMiner/1.0 (research)')
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        with open(dest_path, 'wb') as f:
            f.write(resp.read())
        return True
    except Exception as e:
        print(f"  ERROR: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Download dataset papers")
    parser.add_argument("--check", action="store_true", help="Check which papers are missing")
    parser.add_argument("--paper", type=str, help="Download a specific paper by dataset_id")
    args = parser.parse_args()

    links = load_paper_links()
    
    if args.check:
        missing = []
        for ds_id, url in sorted(links.items()):
            pdf_path = RAW_DIR / f"{ds_id}.pdf"
            if not pdf_path.exists():
                missing.append(ds_id)
        print(f"Total: {len(links)} papers, Present: {len(links) - len(missing)}, Missing: {len(missing)}")
        if missing:
            for m in missing:
                print(f"  MISSING: {m}")
        return

    if args.paper:
        url = links.get(args.paper)
        if not url:
            print(f"Unknown dataset_id: {args.paper}")
            sys.exit(1)
        links = {args.paper: url}

    downloaded = 0
    skipped = 0
    failed = 0

    for i, (ds_id, url) in enumerate(sorted(links.items())):
        pdf_path = RAW_DIR / f"{ds_id}.pdf"
        if pdf_path.exists():
            skipped += 1
            continue

        pdf_url = arxiv_pdf_url(url)
        if not pdf_url:
            # Try direct URL if it ends in .pdf
            if url.endswith('.pdf'):
                pdf_url = url
            else:
                print(f"  [{i+1}/{len(links)}] {ds_id}: Cannot derive PDF URL from {url[:50]}...")
                failed += 1
                continue

        print(f"  [{i+1}/{len(links)}] {ds_id}: downloading...")
        if download_pdf(pdf_url, pdf_path):
            downloaded += 1
        else:
            failed += 1
        
        time.sleep(1)  # rate limit

    print(f"\nDone. Downloaded: {downloaded}, Skipped (exists): {skipped}, Failed: {failed}")

if __name__ == "__main__":
    main()
