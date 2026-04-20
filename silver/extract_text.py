#!/usr/bin/env python3
"""
Task 4b: Paper Text Extraction

Extracts text from downloaded PDFs using PyMuPDF (same method as gold pipeline).
Strips references and appendices.

Usage:
  python silver/extract_text.py
"""

import json
import logging
import re
from pathlib import Path

from tqdm import tqdm

SILVER = Path(__file__).parent
INPUT = SILVER / "data" / "verified_datasets.json"
PDF_DIR = SILVER / "papers_pdf"
TEXT_DIR = SILVER / "papers_text"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("extract_text")


def strip_references(text: str) -> str:
    """Remove everything after 'References' heading."""
    # Common patterns for references section
    patterns = [
        r'\n\s*References\s*\n',
        r'\n\s*REFERENCES\s*\n',
        r'\n\s*Bibliography\s*\n',
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            # Only cut if it's in the last 40% of the paper (avoid false matches)
            if m.start() > len(text) * 0.6:
                return text[:m.start()].strip()
    return text


def strip_appendices(text: str) -> str:
    """Optionally remove appendices (after main content)."""
    patterns = [
        r'\n\s*(?:Appendix|APPENDIX|Supplementary Material)\s*[A-Z]?\s*\n',
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if m and m.start() > len(text) * 0.7:
            return text[:m.start()].strip()
    return text


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract text using PyMuPDF — matches gold pipeline method."""
    text = _canonical_clean_text(_canonical_extract_text(pdf_path))
    text = "\n".join(pages)

    # Clean up
    text = strip_references(text)
    text = strip_appendices(text)

    return text.strip()


def main():
    if not INPUT.exists():
        log.error(f"Input not found: {INPUT}")
        return

    TEXT_DIR.mkdir(parents=True, exist_ok=True)

    with open(INPUT) as f:
        datasets = json.load(f)

    arxiv_ids = set(ds["primary_arxiv"] for ds in datasets)
    log.info(f"Unique papers to extract: {len(arxiv_ids)}")

    success = 0
    failed = 0
    skipped = 0
    lengths = []

    for aid in tqdm(sorted(arxiv_ids), desc="Extracting text"):
        txt_path = TEXT_DIR / f"{aid}.txt"
        if txt_path.exists():
            skipped += 1
            continue

        pdf_path = PDF_DIR / f"{aid}.pdf"
        if not pdf_path.exists():
            failed += 1
            continue

        try:
            text = extract_text_from_pdf(pdf_path)
            if len(text) < 100:
                log.warning(f"  {aid}: too short ({len(text)} chars)")
                failed += 1
                continue

            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(text)

            lengths.append(len(text))
            success += 1

        except Exception as e:
            log.warning(f"  {aid}: extraction error: {e}")
            failed += 1

    log.info(f"\nExtracted: {success}, Failed: {failed}, Cached: {skipped}")
    log.info(f"Total text files: {len(list(TEXT_DIR.glob('*.txt')))}")

    if lengths:
        import numpy as np
        log.info(f"Text lengths: min={min(lengths)}, max={max(lengths)}, "
                 f"mean={np.mean(lengths):.0f}, median={np.median(lengths):.0f}")


if __name__ == "__main__":
    main()
