#!/usr/bin/env python3
"""
6b: Synthetic Data Augmentation

Runs Claude extraction on additional papers (silver standard)
and merges with human-verified data for fine-tuning.

Usage:
  python finetuning/generate_synthetic.py --papers_dir data/papers_extended/
  python finetuning/generate_synthetic.py --papers_dir data/papers_extended/ --limit 50
  python finetuning/generate_synthetic.py --merge-only  # just merge existing
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

import fitz

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from config import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE, MAX_PDF_CHARS
from validation.validate_extraction import validate_extraction, CANONICAL_FIELDS

OUTPUT_DIR = ROOT / "finetuning" / "data"
SYNTHETIC_DIR = OUTPUT_DIR / "synthetic_extractions"

MODEL_ID = "claude-sonnet-4-5-20250929"
TEMPERATURE = 0.0
MAX_TOKENS = 4096
MIN_DELAY = 1.0

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("synthetic")


def extract_text(pdf_path: Path, max_chars: int = 200000) -> str:
    doc = fitz.open(pdf_path)
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    return text[:max_chars]


def call_claude(paper_text: str) -> dict:
    import anthropic
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    if len(paper_text) > MAX_PDF_CHARS:
        paper_text = paper_text[:MAX_PDF_CHARS]

    response = client.messages.create(
        model=MODEL_ID, max_tokens=MAX_TOKENS, temperature=TEMPERATURE,
        system=[{"type": "text", "text": SYSTEM_PROMPT}],
        messages=[{"role": "user", "content": USER_PROMPT_TEMPLATE % paper_text}],
    )

    raw = response.content[0].text.strip()
    if "```json" in raw:
        raw = raw.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in raw:
        raw = raw.split("```", 1)[1].split("```", 1)[0].strip()

    data = json.loads(raw)
    for f in CANONICAL_FIELDS:
        data.setdefault(f, None)
    return {k: v for k, v in data.items() if k in CANONICAL_FIELDS}


def format_example(paper_text: str, extraction: dict) -> dict:
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Extract metadata from the following academic paper. "
                                         f"Return a JSON object with all 30 Croissant metadata fields.\n\n"
                                         f"PAPER TEXT:\n{paper_text}"},
            {"role": "assistant", "content": json.dumps(extraction, indent=2, ensure_ascii=False)},
        ]
    }


def main():
    parser = argparse.ArgumentParser(description="Synthetic data augmentation")
    parser.add_argument("--papers_dir", type=Path, default=ROOT / "data" / "papers_extended")
    parser.add_argument("--limit", type=int, default=None, help="Max papers to process")
    parser.add_argument("--merge-only", action="store_true")
    parser.add_argument("--max-paper-chars", type=int, default=150000)
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SYNTHETIC_DIR.mkdir(parents=True, exist_ok=True)

    # ── Generate synthetic extractions ──
    if not args.merge_only:
        if not args.papers_dir.exists():
            log.warning(f"Papers directory not found: {args.papers_dir}")
            log.info("Create the directory and add PDF files, then re-run.")
            log.info("Skipping to merge step...")
        else:
            pdfs = sorted(args.papers_dir.glob("*.pdf"))
            if args.limit:
                pdfs = pdfs[:args.limit]
            log.info(f"Processing {len(pdfs)} papers from {args.papers_dir}")

            success = 0
            for i, pdf in enumerate(pdfs):
                ds_id = pdf.stem
                out_file = SYNTHETIC_DIR / f"{ds_id}.json"
                if out_file.exists():
                    continue

                log.info(f"[{i+1}/{len(pdfs)}] {ds_id}...")
                try:
                    text = extract_text(pdf, max_chars=args.max_paper_chars)
                    data = call_claude(text)
                    valid, errs = validate_extraction(data, ds_id)
                    if not valid:
                        log.warning(f"  Validation: {errs}")

                    with open(out_file, "w") as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                    success += 1
                except Exception as e:
                    log.error(f"  Error: {e}")

                time.sleep(MIN_DELAY)

            log.info(f"Generated {success} synthetic extractions")

    # ── Format as JSONL ──
    synthetic_path = OUTPUT_DIR / "synthetic.jsonl"
    synth_count = 0

    synth_files = sorted(SYNTHETIC_DIR.glob("*.json"))
    if synth_files:
        with open(synthetic_path, "w") as out:
            for sf in synth_files:
                ds_id = sf.stem
                with open(sf) as f:
                    extraction = json.load(f)

                # Load paper text
                pdf = args.papers_dir / f"{ds_id}.pdf" if args.papers_dir.exists() else None
                if pdf and pdf.exists():
                    text = extract_text(pdf, max_chars=args.max_paper_chars)
                else:
                    # Try main corpus
                    from finetuning.prepare_data import find_pdf
                    pdf_path = find_pdf(ds_id)
                    text = extract_text(pdf_path, max_chars=args.max_paper_chars) if pdf_path else None

                if text:
                    example = format_example(text, extraction)
                    out.write(json.dumps(example, ensure_ascii=False) + "\n")
                    synth_count += 1

        log.info(f"Synthetic JSONL: {synth_count} examples → {synthetic_path}")

    # ── Merge with human-verified data ──
    train_path = OUTPUT_DIR / "train.jsonl"
    combined_path = OUTPUT_DIR / "combined.jsonl"

    human_count = 0
    with open(combined_path, "w") as out:
        # Human-verified first
        if train_path.exists():
            with open(train_path) as f:
                for line in f:
                    out.write(line)
                    human_count += 1

        # Then synthetic
        if synthetic_path.exists():
            with open(synthetic_path) as f:
                for line in f:
                    out.write(line)

    log.info(f"\nCombined: {human_count} human + {synth_count} synthetic = "
             f"{human_count + synth_count} total → {combined_path}")


if __name__ == "__main__":
    main()
