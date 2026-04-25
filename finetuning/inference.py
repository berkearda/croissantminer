#!/usr/bin/env python3
"""
6d: Inference with Fine-Tuned Model + Constrained JSON Decoding

Loads the fine-tuned Qwen model via vLLM with JSON schema guided generation,
runs extraction on all 103 papers, validates outputs.

Requirements:
  pip install vllm

Usage:
  python finetuning/inference.py
  python finetuning/inference.py --model finetuning/models/croissantminer-qwen-7b/
  python finetuning/inference.py --start 0 --end 50
  python finetuning/inference.py --dry-run
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

from croissantminer.pdf.reader import extract_text_from_pdf as _canonical_extract_text
from croissantminer.pdf.processor import clean_text as _canonical_clean_text
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from config import SYSTEM_PROMPT
from validation.validate_extraction import validate_extraction, CANONICAL_FIELDS

# ═══════════════════════════════════════════════════════════════════════
# Config
# ═══════════════════════════════════════════════════════════════════════

PAPER_LINKS = ROOT / "data" / "paper_links.json"
RAW_DIR = ROOT / "data" / "raw"
DEFAULT_MODEL = ROOT / "finetuning" / "models" / "croissantminer-qwen-7b"
OUTPUT_DIR = ROOT / "data" / "extractions" / "finetuned_qwen7b"

MAX_PAPER_CHARS = 150000
MAX_OUTPUT_TOKENS = 4096

# JSON schema for constrained decoding
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {f: {"type": ["string", "null"]} for f in sorted(CANONICAL_FIELDS)},
    "required": list(sorted(CANONICAL_FIELDS)),
    "additionalProperties": False,
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("inference")


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


def extract_text(pdf_path: Path) -> str:
    text = _canonical_clean_text(_canonical_extract_text(pdf_path))
    return text[:MAX_PAPER_CHARS]


def main():
    parser = argparse.ArgumentParser(description="Fine-tuned model inference")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-constrained", action="store_true",
                        help="Disable JSON schema constrained decoding")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(PAPER_LINKS) as f:
        dataset_ids = sorted(json.load(f).keys())
    subset = dataset_ids[args.start:args.end]

    log.info(f"Model: {args.model}")
    log.info(f"Datasets: {len(subset)}")
    log.info(f"Constrained decoding: {'OFF' if args.no_constrained else 'ON'}")

    if args.dry_run:
        log.info("Dry run — checking data availability only.")
        found = sum(1 for ds in subset if find_pdf(ds))
        log.info(f"  PDFs found: {found}/{len(subset)}")
        log.info(f"  Schema fields: {len(CANONICAL_FIELDS)}")
        log.info(f"  Output dir: {OUTPUT_DIR}")
        return

    # ── Load model via vLLM ──
    try:
        from vllm import LLM, SamplingParams
    except ImportError:
        log.error("vLLM not installed. Install with: pip install vllm")
        sys.exit(1)

    if not args.model.exists():
        log.error(f"Model not found: {args.model}")
        log.info("Run `python finetuning/train.py` first.")
        sys.exit(1)

    log.info("Loading model...")
    llm_kwargs = {
        "model": str(args.model),
        "max_model_len": 16384,
        "dtype": "auto",
        "trust_remote_code": True,
    }

    # Guided decoding config
    guided_params = None
    if not args.no_constrained:
        try:
            from vllm.sampling_params import GuidedDecodingParams
            guided_params = GuidedDecodingParams(json=OUTPUT_SCHEMA)
        except ImportError:
            log.warning("GuidedDecodingParams not available in this vLLM version. "
                        "Falling back to unconstrained.")

    llm = LLM(**llm_kwargs)
    tokenizer = llm.get_tokenizer()

    sampling = SamplingParams(
        temperature=0.0,
        max_tokens=MAX_OUTPUT_TOKENS,
        guided_decoding=guided_params,
    )

    # ── Run inference ──
    success = 0
    failed = 0
    skipped = 0
    times = []
    token_counts = []
    valid_json_count = 0

    for i, ds_id in enumerate(subset):
        out_file = OUTPUT_DIR / f"{ds_id}.json"
        if out_file.exists():
            skipped += 1
            continue

        pdf_path = find_pdf(ds_id)
        if not pdf_path:
            failed += 1
            continue

        paper_text = extract_text(pdf_path)

        # Build prompt using chat template
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Extract metadata from the following academic paper. "
                                         f"Return a JSON object with all 30 Croissant metadata fields.\n\n"
                                         f"PAPER TEXT:\n{paper_text}"},
        ]

        prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

        log.info(f"[{i+1}/{len(subset)}] {ds_id}: {len(paper_text)} chars...")
        start = time.time()

        try:
            outputs = llm.generate([prompt], sampling)
            raw = outputs[0].outputs[0].text.strip()
            elapsed = time.time() - start
            times.append(elapsed)

            n_tokens = len(outputs[0].outputs[0].token_ids)
            token_counts.append(n_tokens)

            # Parse JSON
            if "```json" in raw:
                raw = raw.split("```json", 1)[1].split("```", 1)[0].strip()
            elif raw.startswith("```"):
                raw = raw.split("```", 1)[1].split("```", 1)[0].strip()

            data = json.loads(raw)
            valid_json_count += 1

            # Normalize fields
            for field in CANONICAL_FIELDS:
                data.setdefault(field, None)
            data = {k: v for k, v in data.items() if k in CANONICAL_FIELDS}

            valid, errs = validate_extraction(data, ds_id)
            if not valid:
                log.warning(f"  Validation: {errs}")

            with open(out_file, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            non_null = sum(1 for v in data.values() if v is not None and str(v).strip())
            success += 1
            log.info(f"  OK ({non_null}/30 non-null, {elapsed:.1f}s, {n_tokens} tokens)")

        except json.JSONDecodeError as e:
            elapsed = time.time() - start
            times.append(elapsed)
            log.error(f"  JSON parse error: {e}")
            failed += 1
        except Exception as e:
            elapsed = time.time() - start
            times.append(elapsed)
            log.error(f"  Error: {e}")
            failed += 1

    # ── Summary ──
    import numpy as np

    log.info(f"\n{'='*60}")
    log.info(f"INFERENCE SUMMARY")
    log.info(f"{'='*60}")
    log.info(f"  Success: {success}")
    log.info(f"  Failed: {failed}")
    log.info(f"  Skipped (cached): {skipped}")
    log.info(f"  JSON validity: {valid_json_count}/{success + failed} ({valid_json_count / max(success + failed, 1) * 100:.0f}%)")

    if times:
        log.info(f"  Time per paper: mean={np.mean(times):.1f}s, "
                 f"min={min(times):.1f}s, max={max(times):.1f}s")
    if token_counts:
        log.info(f"  Output tokens: mean={np.mean(token_counts):.0f}, "
                 f"min={min(token_counts)}, max={max(token_counts)}")


if __name__ == "__main__":
    main()
