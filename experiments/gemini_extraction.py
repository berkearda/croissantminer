#!/usr/bin/env python3
"""
Gemini 2.5 Pro Extraction Experiment

Runs the same CroissantMiner extraction prompt on all 103 papers using
Google's Gemini 2.5 Pro model via the google-generativeai SDK.

Usage:
  python experiments/gemini_extraction.py
  python experiments/gemini_extraction.py --start 0 --end 50
  python experiments/gemini_extraction.py --dry-run
  python experiments/gemini_extraction.py --model gemini-2.0-flash

Notes:
  - Set GOOGLE_API_KEY in .env or environment
  - Gemini free tier: 2 RPM for 2.5 Pro, 15 RPM for Flash
  - Uses response_mime_type="application/json" for structured output
  - Max input: ~1M tokens for 2.5 Pro (no truncation needed for most papers)
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

import fitz  # PyMuPDF

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from config import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE, MAX_PDF_CHARS
from validation.validate_extraction import validate_extraction, CANONICAL_FIELDS

# ═══════════════════════════════════════════════════════════════════════
# Config
# ═══════════════════════════════════════════════════════════════════════

PAPER_LINKS = ROOT / "data" / "paper_links.json"
RAW_DIR = ROOT / "data" / "raw"
OUTPUT_BASE = ROOT / "data" / "extractions"

# Model configs
MODELS = {
    "gemini-2.5-pro": {
        "model_id": "gemini-2.5-pro-preview-05-06",
        "rpm_limit": 2,          # free tier
        "delay": 35,             # seconds between calls (safe for 2 RPM)
        "max_chars": 900000,     # ~1M token context
    },
    "gemini-2.0-flash": {
        "model_id": "gemini-2.0-flash",
        "rpm_limit": 15,
        "delay": 5,
        "max_chars": 900000,
    },
}

DEFAULT_MODEL = "gemini-2.5-pro"
TEMPERATURE = 0.0
MAX_OUTPUT_TOKENS = 8192
RATE_LIMIT_DELAY = 65  # extra wait on 429

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("gemini_extraction")

# ═══════════════════════════════════════════════════════════════════════
# PDF
# ═══════════════════════════════════════════════════════════════════════


def extract_text_from_pdf(pdf_path: Path) -> str:
    doc = fitz.open(pdf_path)
    pages = [page.get_text() for page in doc]
    doc.close()
    return "\n".join(pages)


def find_pdf(ds_id: str) -> Path:
    pdf = RAW_DIR / f"{ds_id}.pdf"
    if pdf.exists():
        return pdf
    BENCHMARK_MAP = {
        "CIFAR_30field": "2404.00498v2", "FLORES_30field": "2106.03193v1",
        "MLS_30field": "2012.03411v2", "MMLU_30field": "2009.03300v3",
        "MMMU_30field": "2311.16502v4", "MSCOCO_30field": "1405.0312v3",
        "MathVista_30field": "2310.02255v3", "Visual_Genome_30field": "1602.07332v1",
    }
    if ds_id in BENCHMARK_MAP:
        for base in [RAW_DIR, ROOT / "data"]:
            p = base / f"{BENCHMARK_MAP[ds_id]}.pdf"
            if p.exists():
                return p
    return None


# ═══════════════════════════════════════════════════════════════════════
# Gemini API
# ═══════════════════════════════════════════════════════════════════════


def call_gemini(paper_text: str, model_config: dict) -> dict:
    """Call Gemini API and return parsed extraction dict."""
    import google.generativeai as genai
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not set in environment or .env")

    genai.configure(api_key=api_key)

    # Truncate if needed
    max_chars = model_config["max_chars"]
    if len(paper_text) > max_chars:
        paper_text = paper_text[:max_chars]

    user_prompt = USER_PROMPT_TEMPLATE % paper_text

    model = genai.GenerativeModel(
        model_name=model_config["model_id"],
        system_instruction=SYSTEM_PROMPT,
        generation_config=genai.GenerationConfig(
            temperature=TEMPERATURE,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            response_mime_type="application/json",
        ),
    )

    response = model.generate_content(user_prompt)
    raw = response.text.strip()

    # Parse JSON (Gemini with response_mime_type should return clean JSON,
    # but handle markdown fences as fallback)
    if "```json" in raw:
        raw = raw.split("```json", 1)[1].split("```", 1)[0].strip()
    elif raw.startswith("```"):
        raw = raw.split("```", 1)[1].split("```", 1)[0].strip()

    data = json.loads(raw)

    # Normalize to canonical fields
    for field in CANONICAL_FIELDS:
        data.setdefault(field, None)
    data = {k: v for k, v in data.items() if k in CANONICAL_FIELDS}

    return data


# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(description="Gemini Extraction")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        choices=list(MODELS.keys()),
                        help=f"Model to use (default: {DEFAULT_MODEL})")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    model_config = MODELS[args.model]
    model_name_safe = args.model.replace(".", "_")
    out_dir = OUTPUT_BASE / model_name_safe
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(PAPER_LINKS) as f:
        dataset_ids = sorted(json.load(f).keys())
    subset = dataset_ids[args.start:args.end]

    log.info(f"Model: {args.model} ({model_config['model_id']})")
    log.info(f"Datasets: {len(subset)} (index {args.start}:{args.end or len(dataset_ids)})")
    log.info(f"Rate limit: {model_config['rpm_limit']} RPM → {model_config['delay']}s delay")
    log.info(f"Output: {out_dir}/")

    success = 0
    skipped = 0
    failed = 0
    errors = []

    for i, ds_id in enumerate(subset):
        out_file = out_dir / f"{ds_id}.json"

        # Cache
        if out_file.exists():
            skipped += 1
            continue

        # Find PDF
        pdf_path = find_pdf(ds_id)
        if not pdf_path:
            log.warning(f"[{i+1}/{len(subset)}] {ds_id}: PDF not found")
            errors.append(f"{ds_id}: PDF not found")
            failed += 1
            continue

        try:
            full_text = extract_text_from_pdf(pdf_path)
        except Exception as e:
            log.warning(f"[{i+1}/{len(subset)}] {ds_id}: PDF error: {e}")
            errors.append(f"{ds_id}: {e}")
            failed += 1
            continue

        if args.dry_run:
            log.info(f"[{i+1}/{len(subset)}] {ds_id}: {len(full_text)} chars")
            success += 1
            continue

        log.info(f"[{i+1}/{len(subset)}] {ds_id}: {len(full_text)} chars → {args.model}...")

        retries = 0
        max_retries = 3
        while retries < max_retries:
            try:
                data = call_gemini(full_text, model_config)

                valid, val_errors = validate_extraction(data, ds_id)
                if not valid:
                    log.warning(f"  Validation issues: {val_errors}")
                    for field in CANONICAL_FIELDS:
                        data.setdefault(field, None)
                    data = {k: v for k, v in data.items() if k in CANONICAL_FIELDS}

                with open(out_file, "w") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

                non_null = sum(1 for v in data.values() if v is not None and str(v).strip())
                success += 1
                log.info(f"  OK ({non_null}/30 non-null)")
                break  # success, exit retry loop

            except json.JSONDecodeError as e:
                log.error(f"  JSON parse error: {e}")
                errors.append(f"{ds_id}: JSON parse: {e}")
                failed += 1
                break  # don't retry parse errors

            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "quota" in err_str.lower() or "rate" in err_str.lower():
                    retries += 1
                    wait = RATE_LIMIT_DELAY * retries
                    log.warning(f"  Rate limited (attempt {retries}/{max_retries}). Waiting {wait}s...")
                    time.sleep(wait)
                    continue
                elif "500" in err_str or "503" in err_str:
                    retries += 1
                    wait = 10 * retries
                    log.warning(f"  Server error (attempt {retries}/{max_retries}). Waiting {wait}s...")
                    time.sleep(wait)
                    continue
                else:
                    log.error(f"  API error: {e}")
                    errors.append(f"{ds_id}: {e}")
                    failed += 1
                    break
        else:
            # Exhausted retries
            log.error(f"  Failed after {max_retries} retries")
            errors.append(f"{ds_id}: exhausted retries")
            failed += 1

        # Rate limiting delay
        time.sleep(model_config["delay"])

    # Summary
    log.info(f"\n{'='*60}")
    log.info(f"SUMMARY: {args.model}")
    log.info(f"{'='*60}")
    log.info(f"  Success: {success}")
    log.info(f"  Skipped (cached): {skipped}")
    log.info(f"  Failed: {failed}")
    total_output = success + skipped
    if total_output != len(subset):
        log.warning(f"  ⚠ Input/output mismatch: {len(subset)} input, {total_output} output")
    if errors:
        log.warning(f"  Errors ({len(errors)}):")
        for e in errors[:10]:
            log.warning(f"    {e}")

    # Estimate cost/time
    if success > 0:
        total_time = success * model_config["delay"]
        remaining = len(dataset_ids) - (success + skipped)
        eta = remaining * model_config["delay"]
        log.info(f"\n  Estimated remaining: {remaining} datasets, ~{eta // 60}m {eta % 60}s")


if __name__ == "__main__":
    main()
