#!/usr/bin/env python3
"""
Task 2: Deduplication & Filtering

Removes gold-set overlap, deduplicates by arxiv paper, classifies domains,
filters low-quality entries.

Usage:
  python silver/filter_datasets.py
"""

import json
import logging
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent
SILVER = Path(__file__).parent
RAW_INPUT = SILVER / "data" / "hf_datasets_with_papers_raw.json"
OUTPUT = SILVER / "data" / "candidate_datasets.json"
PAPER_LINKS = ROOT / "data" / "paper_links.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("filter")

# Domain classification based on HuggingFace task tags
DOMAIN_MAP = {
    "text-classification": "NLP", "token-classification": "NLP",
    "question-answering": "NLP", "summarization": "NLP",
    "translation": "NLP", "text-generation": "NLP",
    "fill-mask": "NLP", "sentence-similarity": "NLP",
    "text2text-generation": "NLP", "feature-extraction": "NLP",
    "text-retrieval": "NLP", "conversational": "NLP",
    "table-question-answering": "NLP", "zero-shot-classification": "NLP",
    "image-classification": "Vision", "object-detection": "Vision",
    "image-segmentation": "Vision", "image-to-text": "Vision",
    "depth-estimation": "Vision", "video-classification": "Vision",
    "image-feature-extraction": "Vision", "keypoint-detection": "Vision",
    "automatic-speech-recognition": "Audio", "audio-classification": "Audio",
    "text-to-speech": "Audio", "voice-activity-detection": "Audio",
    "audio-to-audio": "Audio",
    "visual-question-answering": "Multimodal", "document-question-answering": "Multimodal",
    "image-text-to-text": "Multimodal", "video-text-to-text": "Multimodal",
    "code-generation": "Code",
    "reinforcement-learning": "Other", "robotics": "Other",
    "tabular-classification": "Other", "tabular-regression": "Other",
    "graph-ml": "Other", "time-series-forecasting": "Other",
}


def classify_domain(tasks: list) -> str:
    domains = []
    for t in tasks:
        if t in DOMAIN_MAP:
            domains.append(DOMAIN_MAP[t])
    if not domains:
        return "Other"
    # Most common
    return Counter(domains).most_common(1)[0][0]


def main():
    if not RAW_INPUT.exists():
        log.error(f"Raw input not found: {RAW_INPUT}")
        log.info("Run silver/discover_datasets.py first.")
        sys.exit(1)

    with open(RAW_INPUT) as f:
        raw = json.load(f)
    log.info(f"Raw candidates: {len(raw)}")

    # Load gold set IDs and arxiv IDs
    gold_ds_ids = set()
    gold_arxiv_ids = set()
    if PAPER_LINKS.exists():
        with open(PAPER_LINKS) as f:
            paper_links = json.load(f)
        gold_ds_ids = set(paper_links.keys())
        # Extract arxiv IDs from gold URLs
        import re
        for url in paper_links.values():
            m = re.search(r'(\d{4}\.\d{4,5})', url)
            if m:
                gold_arxiv_ids.add(m.group(1))
    log.info(f"Gold set: {len(gold_ds_ids)} dataset IDs, {len(gold_arxiv_ids)} arxiv IDs")

    # Filter
    filtered = []
    removed = Counter()

    for ds in raw:
        ds_id = ds["dataset_id"]
        arxiv_ids = ds.get("arxiv_ids", [])

        # Remove gold overlap (by dataset ID)
        if ds_id in gold_ds_ids or ds_id.replace("/", "_") in gold_ds_ids:
            removed["gold_overlap_ds"] += 1
            continue

        # Remove gold overlap (by arxiv ID)
        if any(aid.split("v")[0] in gold_arxiv_ids for aid in arxiv_ids):
            removed["gold_overlap_arxiv"] += 1
            continue

        # Remove zero downloads
        if ds["downloads"] <= 0:
            removed["zero_downloads"] += 1
            continue

        # Remove no valid arxiv
        valid_arxiv = [a for a in arxiv_ids if len(a) >= 9]  # min YYMM.NNNNN
        if not valid_arxiv:
            removed["no_valid_arxiv"] += 1
            continue

        domain = classify_domain(ds.get("tasks", []))

        filtered.append({
            "dataset_id": ds_id,
            "downloads": ds["downloads"],
            "likes": ds["likes"],
            "arxiv_ids": valid_arxiv,
            "primary_arxiv": valid_arxiv[0].split("v")[0],  # strip version
            "domain": domain,
            "license": ds.get("license"),
            "languages": ds.get("languages", []),
            "tasks": ds.get("tasks", []),
        })

    log.info(f"After basic filtering: {len(filtered)}")
    log.info(f"Removed: {dict(removed)}")

    # Deduplicate by arxiv paper — keep highest-download dataset per paper
    by_paper = defaultdict(list)
    for ds in filtered:
        by_paper[ds["primary_arxiv"]].append(ds)

    deduped = []
    n_dupes = 0
    for arxiv_id, datasets in by_paper.items():
        datasets.sort(key=lambda x: -x["downloads"])
        deduped.append(datasets[0])  # keep top
        n_dupes += len(datasets) - 1

    deduped.sort(key=lambda x: -x["downloads"])
    log.info(f"After dedup: {len(deduped)} (removed {n_dupes} same-paper duplicates)")

    # Domain distribution
    domain_dist = Counter(ds["domain"] for ds in deduped)
    log.info(f"\nDomain distribution:")
    for domain, count in domain_dist.most_common():
        pct = count / len(deduped) * 100
        warn = " ← underrepresented" if pct < 5 else ""
        log.info(f"  {domain:<15} {count:>5} ({pct:.1f}%){warn}")

    # Save
    with open(OUTPUT, "w") as f:
        json.dump(deduped, f, indent=2, ensure_ascii=False)
    log.info(f"\nSaved: {OUTPUT}")


if __name__ == "__main__":
    main()
