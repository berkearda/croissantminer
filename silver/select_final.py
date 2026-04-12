#!/usr/bin/env python3
"""
Task 5: Final Selection (Top 500)

Selects top 500 dataset-paper pairs from verified candidates.
Enforces zero overlap with gold set, strict 1:1 paper mapping,
minimum text quality, domain diversity.

Usage:
  python silver/select_final.py
  python silver/select_final.py --target 500
"""

import argparse
import json
import logging
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent.parent
SILVER = Path(__file__).parent
INPUT = SILVER / "data" / "verified_datasets.json"
TEXT_DIR = SILVER / "papers_text"
OUTPUT = SILVER / "data" / "final_500_manifest.json"
PAPER_LINKS = ROOT / "data" / "paper_links.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("select_final")


def load_gold_ids():
    """Load all dataset IDs AND arxiv IDs from the gold 103 set."""
    gold_ds_ids = set()
    gold_arxiv_ids = set()

    if PAPER_LINKS.exists():
        with open(PAPER_LINKS) as f:
            paper_links = json.load(f)
        gold_ds_ids = set(paper_links.keys())
        for url in paper_links.values():
            m = re.search(r'(\d{4}\.\d{4,5})', url)
            if m:
                gold_arxiv_ids.add(m.group(1))

    # Also check processed dir for any additional IDs
    processed = ROOT / "data" / "processed"
    if processed.exists():
        for d in processed.iterdir():
            if d.is_dir():
                gold_ds_ids.add(d.name)

    return gold_ds_ids, gold_arxiv_ids


def main():
    parser = argparse.ArgumentParser(description="Select final 500 datasets")
    parser.add_argument("--target", type=int, default=500)
    parser.add_argument("--min-text-chars", type=int, default=1000)
    parser.add_argument("--max-text-chars", type=int, default=200000)
    args = parser.parse_args()

    if not INPUT.exists():
        log.error(f"Input not found: {INPUT}")
        sys.exit(1)

    with open(INPUT) as f:
        candidates = json.load(f)
    log.info(f"Candidates: {len(candidates)}")

    gold_ds_ids, gold_arxiv_ids = load_gold_ids()
    log.info(f"Gold set: {len(gold_ds_ids)} dataset IDs, {len(gold_arxiv_ids)} arxiv IDs")

    # ── Filter ──
    selected = []
    removed = Counter()

    for ds in candidates:
        ds_id = ds["dataset_id"]
        aid = ds["primary_arxiv"]

        # CRITICAL: No overlap with gold
        if ds_id in gold_ds_ids or ds_id.replace("/", "_") in gold_ds_ids:
            removed["gold_overlap_ds"] += 1
            continue
        if aid in gold_arxiv_ids:
            removed["gold_overlap_arxiv"] += 1
            continue

        # Check text file exists and meets length requirements
        txt_path = TEXT_DIR / f"{aid}.txt"
        if not txt_path.exists():
            removed["no_text"] += 1
            continue

        text_len = txt_path.stat().st_size
        if text_len < args.min_text_chars:
            removed["text_too_short"] += 1
            continue
        if text_len > args.max_text_chars:
            # Don't remove, just note — long papers are fine
            pass

        selected.append({
            "dataset_id": ds_id,
            "arxiv_id": aid,
            "paper_text_path": str(txt_path.relative_to(ROOT)),
            "text_length": text_len,
            "downloads": ds["downloads"],
            "domain": ds["domain"],
            "source": ds.get("paper_source", "arxiv_pdf"),
            "license": ds.get("license"),
            "tasks": ds.get("tasks", []),
        })

    log.info(f"After filtering: {len(selected)}")
    log.info(f"Removed: {dict(removed)}")

    # CRITICAL: Enforce strict 1:1 paper mapping (no duplicate arxiv IDs)
    seen_arxiv = set()
    deduped = []
    for ds in sorted(selected, key=lambda x: -x["downloads"]):
        if ds["arxiv_id"] not in seen_arxiv:
            seen_arxiv.add(ds["arxiv_id"])
            deduped.append(ds)

    log.info(f"After dedup: {len(deduped)}")

    # Verify 1:1
    arxiv_set = set(ds["arxiv_id"] for ds in deduped)
    dsid_set = set(ds["dataset_id"] for ds in deduped)
    assert len(arxiv_set) == len(deduped), f"Duplicate arxiv IDs! {len(arxiv_set)} != {len(deduped)}"
    assert len(dsid_set) == len(deduped), f"Duplicate dataset IDs! {len(dsid_set)} != {len(deduped)}"

    # Verify zero gold overlap
    assert len(arxiv_set & gold_arxiv_ids) == 0, f"Gold arxiv overlap: {arxiv_set & gold_arxiv_ids}"
    assert len(dsid_set & gold_ds_ids) == 0, f"Gold dataset overlap: {dsid_set & gold_ds_ids}"

    # Select top N by downloads
    final = deduped[:args.target]

    # Domain diversity check: if any domain < 5%, try to oversample
    domain_dist = Counter(ds["domain"] for ds in final)
    total = len(final)
    underrep = [d for d, c in domain_dist.items() if c / total < 0.05 and d != "Other"]

    if underrep:
        log.info(f"Underrepresented domains: {underrep}")
        remaining = [ds for ds in deduped[args.target:] if ds["domain"] in underrep]
        n_to_add = min(len(remaining), 20)
        if n_to_add > 0:
            final = final[:-n_to_add] + remaining[:n_to_add]
            log.info(f"  Oversampled {n_to_add} from underrepresented domains")

    # Save
    with open(OUTPUT, "w") as f:
        json.dump(final, f, indent=2, ensure_ascii=False)

    # Summary
    domain_final = Counter(ds["domain"] for ds in final)
    text_lengths = [ds["text_length"] for ds in final]

    log.info(f"\n{'='*60}")
    log.info(f"FINAL SELECTION")
    log.info(f"{'='*60}")
    log.info(f"  Datasets selected: {len(final)}")
    log.info(f"  Gold overlap: 0 (verified)")
    log.info(f"  Unique papers: {len(set(ds['arxiv_id'] for ds in final))} (verified 1:1)")
    log.info(f"\n  Domain distribution:")
    for d, c in domain_final.most_common():
        log.info(f"    {d:<15} {c:>4} ({c/len(final)*100:.1f}%)")
    log.info(f"\n  Paper length: mean={np.mean(text_lengths):.0f}, "
             f"median={np.median(text_lengths):.0f}, "
             f"std={np.std(text_lengths):.0f}")
    log.info(f"\n  Saved: {OUTPUT}")


if __name__ == "__main__":
    main()
