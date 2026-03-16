#!/usr/bin/env python3
"""Batch process datasets: download PDFs and extract metadata."""

import json
import subprocess
import time
import sys
from pathlib import Path
from datetime import datetime, timezone

# Configuration
DELAY_BETWEEN_DOWNLOADS = 2  # seconds
DELAY_BETWEEN_EXTRACTIONS = 3  # seconds
DATA_DIR = Path("data")
RAW_DIR = DATA_DIR / "raw"
LOG_FILE = DATA_DIR / "extraction_log.json"

def load_log():
    if LOG_FILE.exists():
        with open(LOG_FILE) as f:
            return json.load(f)
    return []

def save_log(entries):
    with open(LOG_FILE, 'w') as f:
        json.dump(entries, f, indent=2)

def log_result(dataset_id, status, url=None, error=None, output_path=None):
    entries = load_log()
    entry = {
        "dataset_id": dataset_id,
        "safe_name": dataset_id.replace('/', '_'),
        "url": url,
        "status": status,
        "error": error,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "output_path": output_path
    }
    entries.append(entry)
    save_log(entries)
    return entry

def download_pdf(url, output_path):
    """Download PDF using the download script."""
    result = subprocess.run(
        ["python3", ".claude/skills/dataset-processor/scripts/download_pdf.py",
         "--url", url, "--output", str(output_path)],
        capture_output=True, text=True
    )
    return result.returncode == 0, result.stderr or result.stdout

def run_extraction(pdf_path, dataset_id):
    """Run metadata extraction."""
    safe_name = dataset_id.replace('/', '_')
    output_dir = DATA_DIR / "processed" / safe_name
    output_dir.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        ["python3", "main.py",
         "--paper-path", str(pdf_path),
         "--extraction-mode", "full-pdf",
         "--model-id", "claude-sonnet-4-5-20250929",
         "--output-dir", str(output_dir)],
        capture_output=True, text=True,
        timeout=300  # 5 minute timeout
    )
    return result.returncode == 0, result.stderr or result.stdout

def main():
    # Load parsed datasets
    with open(DATA_DIR / "parsed_datasets.json") as f:
        data = json.load(f)

    # Get datasets with papers
    to_process = []
    for d in data['datasets']:
        if d['status'] in ['has_paper', 'uncertain'] and d['url']:
            url = d['url'].strip()
            if url.startswith('http'):
                to_process.append(d)

    print(f"Datasets to process: {len(to_process)}")

    # Track results
    completed = 0
    failed = 0
    skipped = 0

    # Create directories
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    for i, dataset in enumerate(to_process):
        dataset_id = dataset['dataset_id']
        url = dataset['url']
        safe_name = dataset['safe_name']
        pdf_path = RAW_DIR / f"{safe_name}.pdf"

        print(f"\n[{i+1}/{len(to_process)}] Processing: {dataset_id}")
        print(f"  URL: {url}")

        # Check if already processed
        existing_log = load_log()
        already_done = any(e['dataset_id'] == dataset_id and e['status'] == 'completed'
                         for e in existing_log)
        if already_done:
            print(f"  -> Already processed, skipping")
            skipped += 1
            continue

        # Download PDF
        if not pdf_path.exists():
            print(f"  -> Downloading PDF...")
            success, msg = download_pdf(url, pdf_path)
            if not success:
                print(f"  -> Download FAILED: {msg[:100]}")
                log_result(dataset_id, "failed", url, f"Download failed: {msg[:200]}")
                failed += 1
                time.sleep(DELAY_BETWEEN_DOWNLOADS)
                continue
            print(f"  -> Downloaded to {pdf_path}")
            time.sleep(DELAY_BETWEEN_DOWNLOADS)
        else:
            print(f"  -> PDF already exists")

        # Run extraction
        print(f"  -> Extracting metadata...")
        try:
            success, msg = run_extraction(pdf_path, dataset_id)
            if success:
                output_path = str(DATA_DIR / "processed" / safe_name)
                log_result(dataset_id, "completed", url, output_path=output_path)
                print(f"  -> Extraction COMPLETED")
                completed += 1
            else:
                log_result(dataset_id, "failed", url, f"Extraction failed: {msg[:200]}")
                print(f"  -> Extraction FAILED: {msg[:100]}")
                failed += 1
        except subprocess.TimeoutExpired:
            log_result(dataset_id, "failed", url, "Extraction timed out")
            print(f"  -> Extraction TIMED OUT")
            failed += 1
        except Exception as e:
            log_result(dataset_id, "failed", url, str(e))
            print(f"  -> Extraction ERROR: {e}")
            failed += 1

        time.sleep(DELAY_BETWEEN_EXTRACTIONS)

    # Summary
    print("\n" + "="*50)
    print("BATCH PROCESSING COMPLETE")
    print("="*50)
    print(f"Completed: {completed}")
    print(f"Failed: {failed}")
    print(f"Skipped (already done): {skipped}")
    print(f"Total: {completed + failed + skipped}")

if __name__ == "__main__":
    main()
