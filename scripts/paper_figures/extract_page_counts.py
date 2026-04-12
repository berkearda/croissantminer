#!/usr/bin/env python3
"""Extract page counts from all 103 paper PDFs and save to data/paper_lengths.csv."""

import csv
import json
import sys
from pathlib import Path
import fitz  # PyMuPDF

ROOT = Path(__file__).parent.parent.parent
RAW_DIR = ROOT / "data" / "raw"
PAPER_LINKS = ROOT / "data" / "paper_links.json"
OUTPUT = ROOT / "data" / "paper_lengths.csv"


def main():
    with open(PAPER_LINKS) as f:
        paper_links = json.load(f)

    rows = []
    for ds_id in sorted(paper_links.keys()):
        # Try multiple PDF naming conventions
        candidates = [
            RAW_DIR / f"{ds_id}.pdf",
        ]
        pdf_path = None
        for c in candidates:
            if c.exists():
                pdf_path = c
                break

        if not pdf_path:
            print(f"  MISS: {ds_id}")
            rows.append({"dataset_id": ds_id, "num_pages": None, "pdf_file": ""})
            continue

        try:
            doc = fitz.open(pdf_path)
            num_pages = len(doc)
            doc.close()
            rows.append({"dataset_id": ds_id, "num_pages": num_pages, "pdf_file": pdf_path.name})
        except Exception as e:
            print(f"  ERR: {ds_id}: {e}")
            rows.append({"dataset_id": ds_id, "num_pages": None, "pdf_file": ""})

    with open(OUTPUT, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["dataset_id", "num_pages", "pdf_file"])
        writer.writeheader()
        writer.writerows(rows)

    found = sum(1 for r in rows if r["num_pages"] is not None)
    print(f"\nSaved: {OUTPUT}")
    print(f"  Found: {found}/{len(rows)} PDFs")
    pages = [r["num_pages"] for r in rows if r["num_pages"]]
    if pages:
        print(f"  Pages: min={min(pages)}, max={max(pages)}, mean={sum(pages)/len(pages):.1f}")


if __name__ == "__main__":
    main()
