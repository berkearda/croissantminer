#!/usr/bin/env python3
"""
Submit batch extraction job via Anthropic Message Batches API.

Uses the same model (claude-sonnet-4-5-20250929) and prompts as the gold
extraction pipeline. 50% cost savings vs sequential API calls.

Usage:
  python silver/batch_extract.py
  python silver/batch_extract.py --dry-run        # Show what would be submitted
  python silver/batch_extract.py --limit 10       # Test with first 10
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
MANIFEST = SILVER / "data" / "final_500_manifest.json"
OUTPUT_DIR = SILVER / "extractions"
BATCH_ID_FILE = SILVER / "data" / "batch_id.txt"

sys.path.insert(0, str(ROOT))
from models.claude_model import ClaudeModel

MODEL = "claude-sonnet-4-5-20250929"
MAX_TOKENS = 4096
TEMPERATURE = 0.0

# Use the exact same prompts as the gold extraction pipeline (ClaudeModel)
_cm = object.__new__(ClaudeModel)
SYSTEM_PROMPT = _cm._build_system_prompt()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("batch_extract")


def build_user_prompt(paper_text: str) -> str:
    """Build user prompt with sc: prefixed schema — identical to ClaudeModel._build_user_prompt."""
    fixed_schema = """{
  "sc:name": "string",
  "sc:description": "string",
  "sc:url": "string",
  "sc:license": "string",
  "sc:creator": "string",
  "sc:publisher": "string",
  "sc:datePublished": "string",
  "sc:inLanguage": "string",
  "cr:citeAs": "string",
  "cr:isLiveDataset": "string",

  "rai:dataCollection": "string",
  "rai:dataCollectionType": "string (Select from recommended values)",
  "rai:dataCollectionMissingData": "string",
  "rai:dataCollectionRawData": "string",
  "rai:dataCollectionTimeframe": "string",
  "rai:dataImputationProtocol": "string",
  "rai:dataManipulationProtocol": "string",
  "rai:dataPreprocessingProtocol": "string",

  "rai:dataAnnotationProtocol": "string",
  "rai:dataAnnotationPlatform": "string",
  "rai:dataAnnotationAnalysis": "string",
  "rai:annotationsPerItem": "string",
  "rai:annotatorDemographics": "string",
  "rai:machineAnnotationTools": "string",

  "rai:dataReleaseMaintenancePlan": "string",
  "rai:personalSensitiveInformation": "string",
  "rai:dataSocialImpact": "string",
  "rai:dataBiases": "string",
  "rai:dataLimitations": "string",
  "rai:dataUseCases": "string"
}"""
    return f"""Extract metadata from the following academic paper by matching text to the field descriptions above. Your output must conform exactly to the following schema:

SCHEMA:
{fixed_schema}

PAPER TEXT:
{paper_text}

Return ONLY valid JSON matching the schema above. Do not include any markdown formatting or explanations."""


def normalize_field_names(metadata: dict) -> dict:
    """Strip sc: and cr: prefixes to match gold extraction format.

    The schema asks for sc:name, sc:license etc. but the gold extractions
    store them as name, license etc. RAI fields keep their rai: prefix.
    """
    PREFIX_MAP = {
        "sc:name": "name", "sc:description": "description", "sc:url": "url",
        "sc:license": "license", "sc:creator": "creator", "sc:publisher": "publisher",
        "sc:datePublished": "datePublished", "sc:inLanguage": "inLanguage",
        "cr:citeAs": "citeAs", "cr:isLiveDataset": "isLiveDataset",
        # Handle occasional model quirks
        "sc:citeAs": "citeAs", "sc:isLiveDataset": "isLiveDataset",
        "cr:name": "name", "cr:description": "description",
    }
    return {PREFIX_MAP.get(k, k): v for k, v in metadata.items()}


def sanitize_id(dataset_id: str) -> str:
    """Convert dataset_id to batch API safe custom_id.

    Must match ^[a-zA-Z0-9_-]{1,64}$
    """
    import re
    safe = dataset_id.replace("/", "__")
    safe = re.sub(r'[^a-zA-Z0-9_-]', '_', safe)  # replace dots etc.
    if len(safe) > 64:
        # Keep first 50 + hash suffix for uniqueness
        import hashlib
        h = hashlib.md5(dataset_id.encode()).hexdigest()[:12]
        safe = safe[:51] + "_" + h
    return safe


def build_request(dataset_id: str, paper_text: str) -> dict:
    """Build a single batch request item."""
    user_prompt = build_user_prompt(paper_text)
    return {
        "custom_id": sanitize_id(dataset_id),
        "params": {
            "model": MODEL,
            "max_tokens": MAX_TOKENS,
            "temperature": TEMPERATURE,
            "system": SYSTEM_PROMPT,
            "messages": [
                {"role": "user", "content": user_prompt}
            ],
        }
    }


def main():
    parser = argparse.ArgumentParser(description="Submit batch extraction")
    parser.add_argument("--dry-run", action="store_true", help="Show stats without submitting")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of papers (0=all)")
    parser.add_argument("--skip-existing", action="store_true", default=True,
                        help="Skip datasets that already have extractions")
    args = parser.parse_args()

    if not MANIFEST.exists():
        log.error(f"Manifest not found: {MANIFEST}")
        sys.exit(1)

    with open(MANIFEST) as f:
        manifest = json.load(f)
    log.info(f"Manifest: {len(manifest)} datasets")

    # Prepare output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Build requests
    requests = []
    id_mapping = {}  # custom_id → dataset_id (for reversing in download)
    skipped_existing = 0
    skipped_no_text = 0

    for ds in manifest:
        ds_id = ds["dataset_id"]
        safe_id = ds_id.replace("/", "__")

        # Skip if already extracted
        if args.skip_existing and (OUTPUT_DIR / f"{safe_id}.json").exists():
            skipped_existing += 1
            continue

        # Read paper text
        txt_path = ROOT / ds["paper_text_path"]
        if not txt_path.exists():
            log.warning(f"Missing text: {ds['arxiv_id']}")
            skipped_no_text += 1
            continue

        paper_text = txt_path.read_text(encoding="utf-8")

        # Truncate if needed (shouldn't happen based on our analysis)
        if len(paper_text) > 600_000:
            paper_text = paper_text[:600_000]
            log.warning(f"Truncated {ds_id} to 600K chars")

        requests.append(build_request(ds_id, paper_text))
        id_mapping[sanitize_id(ds_id)] = ds_id

    if args.limit > 0:
        requests = requests[:args.limit]

    log.info(f"Requests to submit: {len(requests)}")
    log.info(f"Skipped (existing): {skipped_existing}")
    log.info(f"Skipped (no text):  {skipped_no_text}")

    if not requests:
        log.info("Nothing to submit.")
        return

    if args.dry_run:
        # Show stats
        total_chars = sum(len(r["params"]["messages"][0]["content"]) for r in requests)
        log.info(f"Total input chars: {total_chars:,} (~{total_chars // 4:,} tokens)")
        log.info(f"Estimated cost at Sonnet batch rate (~$1.50/M input + $7.50/M output):")
        est_input_cost = (total_chars / 4) / 1_000_000 * 1.50
        est_output_cost = len(requests) * 2000 / 1_000_000 * 7.50  # ~2K output tokens each
        log.info(f"  Input:  ${est_input_cost:.2f}")
        log.info(f"  Output: ${est_output_cost:.2f}")
        log.info(f"  Total:  ${est_input_cost + est_output_cost:.2f}")
        log.info("Pass without --dry-run to submit.")
        return

    # Submit batch
    client = anthropic.Anthropic()
    log.info(f"Submitting batch of {len(requests)} requests...")

    batch = client.messages.batches.create(requests=requests)

    log.info(f"Batch created: {batch.id}")
    log.info(f"Status: {batch.processing_status}")

    # Save batch ID and ID mapping for polling/download
    BATCH_ID_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(BATCH_ID_FILE, "w") as f:
        f.write(batch.id)
    log.info(f"Batch ID saved to {BATCH_ID_FILE}")

    mapping_file = SILVER / "data" / "batch_id_mapping.json"
    with open(mapping_file, "w") as f:
        json.dump(id_mapping, f, indent=2)
    log.info(f"ID mapping saved to {mapping_file} ({len(id_mapping)} entries)")

    log.info("\nNext steps:")
    log.info(f"  python silver/check_batch_status.py")
    log.info(f"  python silver/download_batch_results.py")


if __name__ == "__main__":
    main()
