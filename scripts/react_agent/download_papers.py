"""Download arXiv PDFs for the 103 papers in data/agentic/dev_test_split.json.

Reads URLs from data/paper_links.json, rewrites /abs/ → /pdf/, saves to
data/raw/{ds_id}.pdf. Skips papers already downloaded unless --force.
"""

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
SPLIT_PATH = ROOT / "data" / "agentic" / "dev_test_split.json"
LINKS_PATH = ROOT / "data" / "paper_links.json"
RAW_DIR = ROOT / "data" / "raw"

USER_AGENT = "croissantminer-react-agent/0.1 (research; contact: yavuzahmetcan1@gmail.com)"
TIMEOUT = 60
RETRIES = 3
BACKOFF = 2.0


def to_pdf_url(url: str) -> str:
    if "/abs/" in url:
        return url.replace("/abs/", "/pdf/")
    if "arxiv.org" in url and not url.endswith(".pdf"):
        return url.rstrip("/") + ".pdf"
    # ACL Anthology: e.g. https://aclanthology.org/Q19-1026/ -> .../Q19-1026.pdf
    if ("aclanthology.org" in url or "aclweb.org" in url) and not url.endswith(".pdf"):
        return url.rstrip("/") + ".pdf"
    return url


def download_one(ds_id: str, url: str, force: bool) -> tuple[str, str]:
    dest = RAW_DIR / f"{ds_id}.pdf"
    if dest.exists() and dest.stat().st_size > 1024 and not force:
        return ds_id, "cached"

    pdf_url = to_pdf_url(url)
    headers = {"User-Agent": USER_AGENT}

    last_err = None
    for attempt in range(RETRIES):
        try:
            r = requests.get(pdf_url, headers=headers, timeout=TIMEOUT, stream=True)
            r.raise_for_status()
            ctype = r.headers.get("Content-Type", "")
            if "pdf" not in ctype.lower():
                last_err = f"not a pdf (Content-Type: {ctype})"
                time.sleep(BACKOFF ** attempt)
                continue
            tmp = dest.with_suffix(".pdf.part")
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
            tmp.rename(dest)
            return ds_id, f"ok ({dest.stat().st_size // 1024} KB)"
        except requests.RequestException as e:
            last_err = str(e)
            time.sleep(BACKOFF ** attempt)

    return ds_id, f"FAIL: {last_err}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=["dev", "test", "all"], default="all")
    parser.add_argument("--force", action="store_true", help="Re-download even if cached")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--dataset", help="Download a single dataset id")
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    split = json.loads(SPLIT_PATH.read_text())
    links = json.loads(LINKS_PATH.read_text())

    if args.dataset:
        ids = [args.dataset]
    elif args.split == "all":
        ids = split["dev"] + split["test"]
    else:
        ids = split[args.split]

    missing_links = [i for i in ids if i not in links]
    if missing_links:
        print(f"[warn] {len(missing_links)} papers missing from paper_links.json: {missing_links}", file=sys.stderr)

    jobs = [(i, links[i]) for i in ids if i in links]
    print(f"Downloading {len(jobs)} papers into {RAW_DIR}/ ({args.workers} workers)")

    results = {"ok": [], "cached": [], "failed": []}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(download_one, ds, url, args.force): ds for ds, url in jobs}
        for fut in as_completed(futures):
            ds_id, status = fut.result()
            bucket = "cached" if status == "cached" else ("ok" if status.startswith("ok") else "failed")
            results[bucket].append((ds_id, status))
            print(f"  [{bucket:6}] {ds_id}: {status}")

    print()
    print(f"ok:     {len(results['ok'])}")
    print(f"cached: {len(results['cached'])}")
    print(f"failed: {len(results['failed'])}")

    if results["failed"]:
        print("\nFailures:")
        for ds, status in results["failed"]:
            print(f"  {ds}: {status}")
        sys.exit(1)


if __name__ == "__main__":
    main()
