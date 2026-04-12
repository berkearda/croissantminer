#!/usr/bin/env python3
"""
Download and validate batch extraction results.

Saves each extraction as silver/extractions/{dataset_id}.json
Validates against the 30-field schema.

Usage:
  python silver/download_batch_results.py
  python silver/download_batch_results.py --batch-id X
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

import anthropic

SILVER = Path(__file__).parent
OUTPUT_DIR = SILVER / "extractions"
BATCH_ID_FILE = SILVER / "data" / "batch_id.txt"
ID_MAPPING_FILE = SILVER / "data" / "batch_id_mapping.json"

sys.path.insert(0, str(ROOT))
from validation.validate_extraction import validate_extraction
from silver.batch_extract import normalize_field_names

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("download")


def parse_response_text(text: str) -> dict:
    """Parse JSON from Claude response, handling markdown wrapping."""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return json.loads(text.strip())


def main():
    parser = argparse.ArgumentParser(description="Download batch results")
    parser.add_argument("--batch-id", type=str, default=None)
    args = parser.parse_args()

    batch_id = args.batch_id
    if not batch_id:
        if not BATCH_ID_FILE.exists():
            log.error("No batch ID found. Run batch_extract.py first or pass --batch-id")
            sys.exit(1)
        batch_id = BATCH_ID_FILE.read_text().strip()

    client = anthropic.Anthropic()

    # Check batch is complete
    batch = client.messages.batches.retrieve(batch_id)
    if batch.processing_status != "ended":
        log.error(f"Batch not complete. Status: {batch.processing_status}")
        log.error("Run check_batch_status.py --poll to wait for completion")
        sys.exit(1)

    counts = batch.request_counts
    log.info(f"Batch {batch_id}: {counts.succeeded} succeeded, {counts.errored} errored, {counts.expired} expired")

    # Load ID mapping (custom_id → dataset_id)
    id_mapping = {}
    if ID_MAPPING_FILE.exists():
        with open(ID_MAPPING_FILE) as f:
            id_mapping = json.load(f)
        log.info(f"Loaded ID mapping: {len(id_mapping)} entries")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Download results
    succeeded = 0
    errored = 0
    parse_failed = 0
    validation_failed = 0
    validation_errors = []

    for result in client.messages.batches.results(batch_id):
        custom_id = result.custom_id
        ds_id = id_mapping.get(custom_id, custom_id.replace("__", "/"))
        safe_id = ds_id.replace("/", "__")

        if result.result.type == "succeeded":
            message = result.result.message
            response_text = message.content[0].text

            try:
                metadata = normalize_field_names(parse_response_text(response_text))
            except json.JSONDecodeError as e:
                log.warning(f"JSON parse failed for {ds_id}: {e}")
                # Save raw response for debugging
                raw_path = OUTPUT_DIR / f"{safe_id}_raw.txt"
                raw_path.write_text(response_text)
                parse_failed += 1
                continue

            # Validate extraction
            is_valid, errors = validate_extraction(metadata, ds_id)
            if not is_valid:
                validation_failed += 1
                validation_errors.append({"dataset_id": ds_id, "errors": errors})
                log.warning(f"Validation issues for {ds_id}: {errors}")

            # Save extraction (even if validation has warnings)
            output = {
                "dataset_id": ds_id,
                "model": "claude-sonnet-4-5-20250929",
                "extraction": metadata,
                "usage": {
                    "input_tokens": message.usage.input_tokens,
                    "output_tokens": message.usage.output_tokens,
                },
            }
            out_path = OUTPUT_DIR / f"{safe_id}.json"
            with open(out_path, "w") as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
            succeeded += 1

        elif result.result.type == "errored":
            log.warning(f"Error for {ds_id}: {result.result.error}")
            errored += 1

        else:  # expired, canceled
            log.warning(f"{result.result.type} for {ds_id}")
            errored += 1

    # Summary
    log.info(f"\n{'='*60}")
    log.info(f"DOWNLOAD COMPLETE")
    log.info(f"{'='*60}")
    log.info(f"  Succeeded:         {succeeded}")
    log.info(f"  API errors:        {errored}")
    log.info(f"  JSON parse fails:  {parse_failed}")
    log.info(f"  Validation issues: {validation_failed}")
    log.info(f"  Saved to:          {OUTPUT_DIR}")

    # Save summary
    summary = {
        "batch_id": batch_id,
        "succeeded": succeeded,
        "errored": errored,
        "parse_failed": parse_failed,
        "validation_failed": validation_failed,
        "validation_errors": validation_errors,
    }
    summary_path = SILVER / "data" / "extraction_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    log.info(f"  Summary:           {summary_path}")

    if errored > 0 or parse_failed > 0:
        log.info(f"\nTo retry failed extractions:")
        log.info(f"  python silver/sequential_extract.py --only-missing")

    return 0 if errored == 0 and parse_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
