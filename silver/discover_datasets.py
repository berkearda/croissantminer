#!/usr/bin/env python3
"""
Task 1: HuggingFace Dataset Enumeration

Queries HuggingFace Hub for public datasets with arxiv paper links.
Sorts by downloads, extracts metadata, saves candidates.

Usage:
  python silver/discover_datasets.py
  python silver/discover_datasets.py --max-datasets 5000
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path

from huggingface_hub import HfApi
from tqdm import tqdm

ROOT = Path(__file__).parent.parent
OUTPUT = Path(__file__).parent / "data" / "hf_datasets_with_papers_raw.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("discover")

ARXIV_TAG_RE = re.compile(r"arxiv:(\d{4}\.\d{4,5}(?:v\d+)?)")
ARXIV_URL_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5}(?:v\d+)?)")


def main():
    parser = argparse.ArgumentParser(description="Discover HF datasets with papers")
    parser.add_argument("--max-datasets", type=int, default=10000,
                        help="Max datasets to scan (sorted by downloads)")
    args = parser.parse_args()

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    # Resume support
    if OUTPUT.exists():
        log.info(f"Output exists: {OUTPUT}. Delete to re-run.")
        with open(OUTPUT) as f:
            existing = json.load(f)
        log.info(f"  {len(existing)} datasets already discovered.")
        return

    api = HfApi()
    log.info(f"Listing datasets (max {args.max_datasets}, sorted by downloads)...")

    results = []
    n_with_paper = 0
    n_scanned = 0

    for ds in tqdm(api.list_datasets(sort="downloads", direction=-1, limit=args.max_datasets),
                   total=args.max_datasets, desc="Scanning"):
        n_scanned += 1
        tags = ds.tags or []

        # Extract arxiv IDs from tags
        arxiv_ids = set()
        for tag in tags:
            m = ARXIV_TAG_RE.match(tag)
            if m:
                arxiv_ids.add(m.group(1))

        # Extract task tags, language tags, license
        task_tags = [t for t in tags if t.startswith("task_categories:")]
        lang_tags = [t.replace("language:", "") for t in tags if t.startswith("language:")]
        license_tags = [t.replace("license:", "") for t in tags if t.startswith("license:")]

        # Check card content for arxiv URLs not in tags
        card_snippet = ""
        if hasattr(ds, "card_data") and ds.card_data:
            # card_data might not have raw text, but check
            pass

        # Also check description if available
        # (HfApi list_datasets doesn't return full card — we'd need a separate call)
        # We'll rely on tags for discovery and do card checks in filtering

        if not arxiv_ids:
            continue

        n_with_paper += 1
        results.append({
            "dataset_id": ds.id,
            "downloads": ds.downloads or 0,
            "likes": ds.likes or 0,
            "arxiv_ids": sorted(arxiv_ids),
            "tasks": [t.replace("task_categories:", "") for t in task_tags],
            "languages": lang_tags[:5],  # cap to avoid huge lists
            "license": license_tags[0] if license_tags else None,
            "all_tags": tags,
        })

    # Sort by downloads
    results.sort(key=lambda x: -x["downloads"])

    with open(OUTPUT, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    log.info(f"\nScanned: {n_scanned}")
    log.info(f"With arxiv paper: {n_with_paper} ({n_with_paper/n_scanned*100:.1f}%)")
    log.info(f"Saved: {OUTPUT}")


if __name__ == "__main__":
    main()
