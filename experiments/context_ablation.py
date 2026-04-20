#!/usr/bin/env python3
"""
Context Length Ablation Experiment

For each of the 103 papers, creates 4 truncated versions and runs extraction:
  full     — complete paper text (baseline, already exists in data/processed/)
  50pct    — first 50% of paper text by character count
  25pct    — first 25% of paper text
  abstract — abstract section only

Usage:
  python experiments/context_ablation.py --condition 50pct
  python experiments/context_ablation.py --condition abstract --start 0 --end 50
  python experiments/context_ablation.py --condition all  # runs all 4
  python experiments/context_ablation.py --dry-run       # show text lengths, no API calls
"""

import argparse
import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from datetime import datetime

from croissantminer.pdf.reader import extract_text_from_pdf as _canonical_extract_text
from croissantminer.pdf.processor import clean_text as _canonical_clean_text
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from config import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE, MAX_PDF_CHARS
from validation.validate_extraction import validate_extraction, CANONICAL_FIELDS

# ═══════════════════════════════════════════════════════════════════════
# Config
# ═══════════════════════════════════════════════════════════════════════

PAPER_LINKS = ROOT / "data" / "paper_links.json"
RAW_DIR = ROOT / "data" / "raw"
BASELINE_DIR = ROOT / "data" / "processed"
OUTPUT_BASE = ROOT / "data" / "extractions" / "context_ablation"

MODEL_ID = "claude-sonnet-4-5-20250929"
TEMPERATURE = 0.0
MAX_TOKENS = 4096

CONDITIONS = ["full", "50pct", "25pct", "abstract"]

# Rate limiting
MIN_DELAY_SECONDS = 1.0
RATE_LIMIT_DELAY = 60  # seconds to wait on 429

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("context_ablation")

# ═══════════════════════════════════════════════════════════════════════
# PDF text extraction
# ═══════════════════════════════════════════════════════════════════════


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract full text from a PDF using PyMuPDF."""
    doc = fitz.open(pdf_path)
    pages = []
    for page in doc:
        pages.append(page.get_text())
    doc.close()
    return "\n".join(pages)


def find_pdf(ds_id: str) -> Path:
    """Find the PDF for a dataset ID, handling benchmark naming."""
    # Try direct name in data/raw/
    pdf = RAW_DIR / f"{ds_id}.pdf"
    if pdf.exists():
        return pdf

    # Benchmark datasets stored with arxiv IDs
    BENCHMARK_MAP = {
        "CIFAR_30field": "2404.00498v2",
        "FLORES_30field": "2106.03193v1",
        "MLS_30field": "2012.03411v2",
        "MMLU_30field": "2009.03300v3",
        "MMMU_30field": "2311.16502v4",
        "MSCOCO_30field": "1405.0312v3",
        "MathVista_30field": "2310.02255v3",
        "Visual_Genome_30field": "1602.07332v1",
    }
    if ds_id in BENCHMARK_MAP:
        pdf = RAW_DIR / f"{BENCHMARK_MAP[ds_id]}.pdf"
        if pdf.exists():
            return pdf
        # Also check data/ root
        pdf = ROOT / "data" / f"{BENCHMARK_MAP[ds_id]}.pdf"
        if pdf.exists():
            return pdf

    return None


# ═══════════════════════════════════════════════════════════════════════
# Text truncation
# ═══════════════════════════════════════════════════════════════════════


def extract_abstract(text: str) -> str:
    """Extract the abstract section from paper text.

    Looks for 'Abstract' heading and takes text until the next section
    heading (Introduction, 1., etc.).
    """
    # Try to find abstract section
    patterns = [
        # "Abstract" followed by text until "Introduction" or "1." or "1 "
        r'(?i)abstract\s*\n(.*?)(?=\n\s*(?:1[\.\s]|introduction|I\.\s|keywords))',
        # "Abstract" followed by text until double newline + capitalized heading
        r'(?i)abstract\s*\n(.*?)(?=\n\n[A-Z])',
        # Just "Abstract" to end of first ~5000 chars
        r'(?i)abstract\s*\n(.{200,5000})',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            abstract = match.group(1).strip()
            # Sanity: abstract should be 100-5000 chars
            if 100 <= len(abstract) <= 5000:
                return abstract

    # Fallback: take first 3000 characters (roughly first page)
    return text[:3000].strip()


def truncate_text(text: str, condition: str) -> str:
    """Truncate text according to the ablation condition."""
    if condition == "full":
        return text
    elif condition == "50pct":
        cutoff = len(text) // 2
        return text[:cutoff]
    elif condition == "25pct":
        cutoff = len(text) // 4
        return text[:cutoff]
    elif condition == "abstract":
        return extract_abstract(text)
    else:
        raise ValueError(f"Unknown condition: {condition}")


# ═══════════════════════════════════════════════════════════════════════
# LLM extraction
# ═══════════════════════════════════════════════════════════════════════


def call_claude(text: str) -> dict:
    """Call Claude API and return parsed extraction dict."""
    import anthropic
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    # Truncate to max chars
    if len(text) > MAX_PDF_CHARS:
        text = text[:MAX_PDF_CHARS]

    user_prompt = USER_PROMPT_TEMPLATE % text

    response = client.messages.create(
        model=MODEL_ID,
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
        system=[{"type": "text", "text": SYSTEM_PROMPT}],
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = response.content[0].text.strip()

    # Parse JSON (handle markdown fences)
    if "```json" in raw:
        raw = raw.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in raw:
        raw = raw.split("```", 1)[1].split("```", 1)[0].strip()

    data = json.loads(raw)

    # Ensure all 30 fields present
    for field in CANONICAL_FIELDS:
        data.setdefault(field, None)

    # Remove extra fields
    data = {k: v for k, v in data.items() if k in CANONICAL_FIELDS}

    return data


# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(description="Context Length Ablation")
    parser.add_argument("--condition", required=True,
                        choices=CONDITIONS + ["all"],
                        help="Truncation condition to run")
    parser.add_argument("--start", type=int, default=0,
                        help="Start index in dataset list")
    parser.add_argument("--end", type=int, default=None,
                        help="End index in dataset list (exclusive)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show text lengths without API calls")
    args = parser.parse_args()

    conditions = CONDITIONS if args.condition == "all" else [args.condition]

    # Load dataset list
    with open(PAPER_LINKS) as f:
        dataset_ids = sorted(json.load(f).keys())

    subset = dataset_ids[args.start:args.end]
    log.info(f"Datasets: {len(subset)} (index {args.start}:{args.end or len(dataset_ids)})")
    log.info(f"Conditions: {conditions}")

    for condition in conditions:
        out_dir = OUTPUT_BASE / condition
        out_dir.mkdir(parents=True, exist_ok=True)

        log.info(f"\n{'='*60}")
        log.info(f"Condition: {condition}")
        log.info(f"{'='*60}")

        success = 0
        skipped = 0
        failed = 0
        errors = []

        for i, ds_id in enumerate(subset):
            out_file = out_dir / f"{ds_id}.json"

            # Cache: skip if already exists
            if out_file.exists():
                skipped += 1
                continue

            # For "full" condition, copy from existing baseline
            if condition == "full":
                baseline = BASELINE_DIR / ds_id / "full_pdf_metadata_result.json"
                if baseline.exists():
                    import shutil
                    shutil.copy2(baseline, out_file)
                    success += 1
                    continue

            # Find and read PDF
            pdf_path = find_pdf(ds_id)
            if not pdf_path:
                log.warning(f"[{i+1}/{len(subset)}] {ds_id}: PDF not found")
                errors.append(f"{ds_id}: PDF not found")
                failed += 1
                continue

            try:
                full_text = extract_text_from_pdf(pdf_path)
            except Exception as e:
                log.warning(f"[{i+1}/{len(subset)}] {ds_id}: PDF read error: {e}")
                errors.append(f"{ds_id}: PDF read error: {e}")
                failed += 1
                continue

            # Truncate
            truncated = truncate_text(full_text, condition)

            if args.dry_run:
                log.info(f"[{i+1}/{len(subset)}] {ds_id}: full={len(full_text)}, "
                         f"{condition}={len(truncated)} ({len(truncated)/len(full_text)*100:.0f}%)")
                success += 1
                continue

            # Call API
            log.info(f"[{i+1}/{len(subset)}] {ds_id}: {len(truncated)} chars → Claude...")
            try:
                data = call_claude(truncated)

                # Validate
                valid, val_errors = validate_extraction(data, ds_id)
                if not valid:
                    log.warning(f"  Validation failed: {val_errors}")
                    # Try to fix: ensure all fields present
                    for field in CANONICAL_FIELDS:
                        data.setdefault(field, None)
                    data = {k: v for k, v in data.items() if k in CANONICAL_FIELDS}

                # Save
                with open(out_file, "w") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

                success += 1
                log.info(f"  OK ({sum(1 for v in data.values() if v is not None)}/30 non-null)")

            except json.JSONDecodeError as e:
                log.error(f"  JSON parse error: {e}")
                errors.append(f"{ds_id}: JSON parse error: {e}")
                failed += 1
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "rate" in err_str.lower():
                    log.warning(f"  Rate limited. Waiting {RATE_LIMIT_DELAY}s...")
                    time.sleep(RATE_LIMIT_DELAY)
                    # Don't count as failed — will retry next run
                    continue
                log.error(f"  API error: {e}")
                errors.append(f"{ds_id}: API error: {e}")
                failed += 1

            # Rate limiting
            time.sleep(MIN_DELAY_SECONDS)

        # Summary
        log.info(f"\n--- {condition} Summary ---")
        log.info(f"  Success: {success}, Skipped (cached): {skipped}, Failed: {failed}")
        if success + skipped != len(subset):
            log.warning(f"  ⚠ Input/output mismatch: {len(subset)} input, {success + skipped} output")
        if errors:
            log.warning(f"  Errors: {errors[:5]}")

    log.info("\nDone.")


if __name__ == "__main__":
    main()
