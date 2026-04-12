#!/usr/bin/env python3
"""
Task 3: Paper Availability Check

Checks whether arxiv papers are accessible (via Semantic Scholar or arxiv PDF).
Removes datasets where paper is unavailable.

Usage:
  python silver/check_papers.py
  python silver/check_papers.py --skip-s2  # skip Semantic Scholar, arxiv only
"""

import argparse
import json
import logging
import time
from pathlib import Path

import httpx
from tqdm import tqdm

SILVER = Path(__file__).parent
INPUT = SILVER / "data" / "candidate_datasets.json"
OUTPUT = SILVER / "data" / "verified_datasets.json"
CACHE = SILVER / "data" / "_paper_check_cache.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("check_papers")

S2_DELAY = 3.5   # ~100 req/5min = 1 per 3s
ARXIV_DELAY = 3   # arxiv ToS


def load_cache():
    if CACHE.exists():
        with open(CACHE) as f:
            return json.load(f)
    return {}


def save_cache(cache):
    with open(CACHE, "w") as f:
        json.dump(cache, f, indent=2)


def check_semantic_scholar(arxiv_id: str, cache: dict) -> dict:
    """Check S2 for open access."""
    key = f"s2:{arxiv_id}"
    if key in cache:
        return cache[key]

    try:
        url = f"https://api.semanticscholar.org/graph/v1/paper/ArXiv:{arxiv_id}"
        resp = httpx.get(url, params={"fields": "isOpenAccess,openAccessPdf,title"},
                         timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            result = {
                "available": bool(data.get("isOpenAccess")),
                "source": "s2orc" if data.get("isOpenAccess") else "s2_closed",
                "title": data.get("title"),
            }
        elif resp.status_code == 404:
            result = {"available": False, "source": "s2_not_found", "title": None}
        else:
            result = {"available": False, "source": f"s2_error_{resp.status_code}", "title": None}
    except Exception as e:
        result = {"available": False, "source": f"s2_error", "title": None}

    cache[key] = result
    return result


def check_arxiv_pdf(arxiv_id: str, cache: dict) -> dict:
    """Check if arxiv PDF is accessible."""
    key = f"arxiv:{arxiv_id}"
    if key in cache:
        return cache[key]

    try:
        url = f"https://arxiv.org/abs/{arxiv_id}"
        resp = httpx.head(url, timeout=10, follow_redirects=True)
        result = {
            "available": resp.status_code == 200,
            "source": "arxiv_pdf" if resp.status_code == 200 else f"arxiv_{resp.status_code}",
        }
    except Exception:
        result = {"available": False, "source": "arxiv_error"}

    cache[key] = result
    return result


def main():
    parser = argparse.ArgumentParser(description="Check paper availability")
    parser.add_argument("--skip-s2", action="store_true", help="Skip Semantic Scholar check")
    args = parser.parse_args()

    if not INPUT.exists():
        log.error(f"Input not found: {INPUT}. Run filter_datasets.py first.")
        return

    with open(INPUT) as f:
        candidates = json.load(f)
    log.info(f"Candidates: {len(candidates)}")

    # Get unique arxiv IDs
    arxiv_ids = set()
    ds_by_arxiv = {}
    for ds in candidates:
        aid = ds["primary_arxiv"]
        arxiv_ids.add(aid)
        ds_by_arxiv.setdefault(aid, ds)

    log.info(f"Unique arxiv IDs: {len(arxiv_ids)}")

    cache = load_cache()
    verified = []
    source_counts = {"s2orc": 0, "arxiv_pdf": 0, "unavailable": 0}

    for aid in tqdm(sorted(arxiv_ids), desc="Checking papers"):
        available = False
        source = "unavailable"

        # Check S2 first (richer metadata)
        if not args.skip_s2:
            s2 = check_semantic_scholar(aid, cache)
            if s2["available"]:
                available = True
                source = "s2orc"
            time.sleep(S2_DELAY)

        # Fallback to arxiv
        if not available:
            arxiv = check_arxiv_pdf(aid, cache)
            if arxiv["available"]:
                available = True
                source = "arxiv_pdf"
            time.sleep(ARXIV_DELAY)

        if available:
            ds = ds_by_arxiv[aid]
            ds["paper_source"] = source
            verified.append(ds)
            source_counts[source] += 1
        else:
            source_counts["unavailable"] += 1

        # Periodic cache save
        if len(cache) % 50 == 0:
            save_cache(cache)

    save_cache(cache)

    with open(OUTPUT, "w") as f:
        json.dump(verified, f, indent=2, ensure_ascii=False)

    log.info(f"\nResults:")
    log.info(f"  Verified: {len(verified)}/{len(arxiv_ids)}")
    log.info(f"  Sources: {source_counts}")
    log.info(f"  Saved: {OUTPUT}")

    from collections import Counter
    domain_dist = Counter(ds["domain"] for ds in verified)
    log.info(f"\n  Domain distribution:")
    for d, c in domain_dist.most_common():
        log.info(f"    {d:<15} {c}")


if __name__ == "__main__":
    main()
