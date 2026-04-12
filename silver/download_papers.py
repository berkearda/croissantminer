#!/usr/bin/env python3
"""
Task 4a: Paper Download

Downloads PDFs from arxiv for verified datasets.

Usage:
  python silver/download_papers.py
  python silver/download_papers.py --limit 100
"""

import argparse
import json
import logging
import time
from pathlib import Path

import httpx
from tqdm import tqdm

SILVER = Path(__file__).parent
INPUT = SILVER / "data" / "verified_datasets.json"
PDF_DIR = SILVER / "papers_pdf"

ARXIV_DELAY = 3  # seconds between downloads (ToS compliant)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("download")


def download_arxiv_pdf(arxiv_id: str, output_path: Path) -> bool:
    """Download PDF from arxiv."""
    url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    try:
        with httpx.stream("GET", url, timeout=60, follow_redirects=True) as resp:
            if resp.status_code != 200:
                return False
            with open(output_path, "wb") as f:
                for chunk in resp.iter_bytes(chunk_size=8192):
                    f.write(chunk)
        return output_path.stat().st_size > 1000  # sanity: > 1KB
    except Exception as e:
        log.warning(f"  Download failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Download papers")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    if not INPUT.exists():
        log.error(f"Input not found: {INPUT}. Run check_papers.py first.")
        return

    PDF_DIR.mkdir(parents=True, exist_ok=True)

    with open(INPUT) as f:
        datasets = json.load(f)

    if args.limit:
        datasets = datasets[:args.limit]

    # Get unique arxiv IDs to download
    to_download = []
    for ds in datasets:
        aid = ds["primary_arxiv"]
        pdf_path = PDF_DIR / f"{aid}.pdf"
        if not pdf_path.exists():
            to_download.append((aid, pdf_path))

    log.info(f"Total datasets: {len(datasets)}")
    log.info(f"PDFs to download: {len(to_download)} (already cached: {len(datasets) - len(to_download)})")

    success = 0
    failed = 0

    for aid, pdf_path in tqdm(to_download, desc="Downloading"):
        if download_arxiv_pdf(aid, pdf_path):
            success += 1
        else:
            failed += 1
            pdf_path.unlink(missing_ok=True)

        time.sleep(ARXIV_DELAY)

    log.info(f"\nDownloaded: {success}, Failed: {failed}")
    log.info(f"Total PDFs: {len(list(PDF_DIR.glob('*.pdf')))}")


if __name__ == "__main__":
    main()
