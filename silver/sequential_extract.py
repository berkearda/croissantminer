#!/usr/bin/env python3
"""
Sequential extraction fallback.

Processes papers one at a time via the regular Messages API.
Use when batch API is unavailable or to retry failed extractions.

Usage:
  python silver/sequential_extract.py                  # All missing
  python silver/sequential_extract.py --only-missing   # Only papers without extractions
  python silver/sequential_extract.py --limit 10       # First 10 only
  python silver/sequential_extract.py --start-from 50  # Resume from index 50
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

import anthropic

SILVER = Path(__file__).parent
MANIFEST = SILVER / "data" / "final_500_manifest.json"
OUTPUT_DIR = SILVER / "extractions"

sys.path.insert(0, str(ROOT))
from silver.batch_extract import SYSTEM_PROMPT, build_user_prompt, normalize_field_names
from validation.validate_extraction import validate_extraction

MODEL = "claude-sonnet-4-5-20250929"
MAX_TOKENS = 4096
TEMPERATURE = 0.0

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("sequential")


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


def extract_one(client: anthropic.Anthropic, ds_id: str, paper_text: str) -> dict:
    """Extract metadata for a single paper."""
    user_prompt = build_user_prompt(paper_text)

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    metadata = parse_response_text(response.content[0].text)
    metadata = normalize_field_names(metadata)
    return {
        "dataset_id": ds_id,
        "model": MODEL,
        "extraction": metadata,
        "usage": {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Sequential extraction")
    parser.add_argument("--only-missing", action="store_true", default=True,
                        help="Only extract papers without existing results")
    parser.add_argument("--limit", type=int, default=0, help="Max papers to process")
    parser.add_argument("--start-from", type=int, default=0, help="Start from index")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between requests (seconds)")
    args = parser.parse_args()

    if not MANIFEST.exists():
        log.error(f"Manifest not found: {MANIFEST}")
        sys.exit(1)

    with open(MANIFEST) as f:
        manifest = json.load(f)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    client = anthropic.Anthropic()

    # Build work list
    work = []
    for i, ds in enumerate(manifest):
        if i < args.start_from:
            continue
        ds_id = ds["dataset_id"]
        safe_id = ds_id.replace("/", "__")

        if args.only_missing and (OUTPUT_DIR / f"{safe_id}.json").exists():
            continue

        txt_path = ROOT / ds["paper_text_path"]
        if not txt_path.exists():
            log.warning(f"Missing text: {ds['arxiv_id']}")
            continue

        work.append((ds_id, safe_id, txt_path))

    if args.limit > 0:
        work = work[:args.limit]

    log.info(f"Papers to extract: {len(work)}")
    if not work:
        log.info("Nothing to do.")
        return

    succeeded = 0
    failed = 0
    total_input_tokens = 0
    total_output_tokens = 0

    for idx, (ds_id, safe_id, txt_path) in enumerate(work):
        log.info(f"[{idx + 1}/{len(work)}] {ds_id}")

        paper_text = txt_path.read_text(encoding="utf-8")
        if len(paper_text) > 600_000:
            paper_text = paper_text[:600_000]

        for attempt in range(3):
            try:
                result = extract_one(client, ds_id, paper_text)

                # Validate
                is_valid, errors = validate_extraction(result["extraction"], ds_id)
                if not is_valid:
                    log.warning(f"  Validation issues: {errors}")

                # Save
                out_path = OUTPUT_DIR / f"{safe_id}.json"
                with open(out_path, "w") as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)

                total_input_tokens += result["usage"]["input_tokens"]
                total_output_tokens += result["usage"]["output_tokens"]
                succeeded += 1
                log.info(f"  OK ({result['usage']['input_tokens']} in, {result['usage']['output_tokens']} out)")
                break

            except anthropic.RateLimitError:
                wait = 60 * (2 ** attempt)
                log.warning(f"  Rate limit, waiting {wait}s...")
                time.sleep(wait)

            except json.JSONDecodeError as e:
                log.warning(f"  JSON parse error: {e}")
                if attempt == 2:
                    failed += 1
                time.sleep(2)

            except Exception as e:
                log.warning(f"  Error: {e}")
                if attempt == 2:
                    failed += 1
                time.sleep(5)

        if args.delay > 0:
            time.sleep(args.delay)

    log.info(f"\n{'='*60}")
    log.info(f"SEQUENTIAL EXTRACTION COMPLETE")
    log.info(f"{'='*60}")
    log.info(f"  Succeeded: {succeeded}")
    log.info(f"  Failed:    {failed}")
    log.info(f"  Tokens:    {total_input_tokens:,} in, {total_output_tokens:,} out")
    est_cost = (total_input_tokens / 1_000_000 * 3.0) + (total_output_tokens / 1_000_000 * 15.0)
    log.info(f"  Est. cost: ${est_cost:.2f}")


if __name__ == "__main__":
    main()
