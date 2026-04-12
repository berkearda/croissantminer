#!/usr/bin/env python3
"""
Poll batch extraction status.

Usage:
  python silver/check_batch_status.py              # One-shot status check
  python silver/check_batch_status.py --poll        # Poll every 60s until done
  python silver/check_batch_status.py --batch-id X  # Check specific batch
"""

import argparse
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

SILVER = Path(__file__).parent
load_dotenv(SILVER.parent / ".env")

import anthropic
BATCH_ID_FILE = SILVER / "data" / "batch_id.txt"


def main():
    parser = argparse.ArgumentParser(description="Check batch status")
    parser.add_argument("--batch-id", type=str, default=None)
    parser.add_argument("--poll", action="store_true", help="Poll until complete")
    parser.add_argument("--interval", type=int, default=60, help="Poll interval in seconds")
    args = parser.parse_args()

    batch_id = args.batch_id
    if not batch_id:
        if not BATCH_ID_FILE.exists():
            print("No batch ID found. Run batch_extract.py first or pass --batch-id")
            sys.exit(1)
        batch_id = BATCH_ID_FILE.read_text().strip()

    client = anthropic.Anthropic()
    print(f"Batch ID: {batch_id}")

    while True:
        batch = client.messages.batches.retrieve(batch_id)
        counts = batch.request_counts

        print(f"\nStatus: {batch.processing_status}")
        print(f"  Succeeded:  {counts.succeeded}")
        print(f"  Errored:    {counts.errored}")
        print(f"  Expired:    {counts.expired}")
        print(f"  Canceled:   {counts.canceled}")
        print(f"  Processing: {counts.processing}")
        total = counts.succeeded + counts.errored + counts.expired + counts.canceled
        print(f"  Done:       {total} / {total + counts.processing}")

        if batch.processing_status == "ended":
            print("\nBatch complete!")
            print(f"  {counts.succeeded} succeeded, {counts.errored} errored, {counts.expired} expired")
            if counts.succeeded > 0:
                print(f"\nRun: python silver/download_batch_results.py")
            break

        if not args.poll:
            progress = total / max(total + counts.processing, 1) * 100
            print(f"\nProgress: {progress:.1f}%")
            print(f"Re-run with --poll to auto-refresh every {args.interval}s")
            break

        print(f"\nPolling again in {args.interval}s...")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
