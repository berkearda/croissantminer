#!/usr/bin/env python3
"""
Few-Shot Ablation Experiment

Prepends N example extractions (rated Correct by annotators) to the prompt.
  0-shot — baseline (already exists in data/processed/)
  1-shot — 1 demonstration example
  3-shot — 3 demonstration examples

Examples are stored in data/fewshot_examples/ and chosen for domain diversity:
  - google_boolq        (NLP / QA)
  - lmms-lab_ChartQA    (Vision / Multimodal)
  - livecodebench_code_generation_lite  (Code)

Usage:
  python experiments/fewshot_ablation.py --shots 1
  python experiments/fewshot_ablation.py --shots 3 --start 0 --end 50
  python experiments/fewshot_ablation.py --shots 0     # copies baseline
  python experiments/fewshot_ablation.py --dry-run --shots 3
"""

import argparse
import json
import logging
import os
import re
import shutil
import sys
import time
from pathlib import Path

from croissantminer.pdf.reader import extract_text_from_pdf as _canonical_extract_text
from croissantminer.pdf.processor import clean_text as _canonical_clean_text
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from config import SYSTEM_PROMPT, MAX_PDF_CHARS
from validation.validate_extraction import validate_extraction, CANONICAL_FIELDS

# ═══════════════════════════════════════════════════════════════════════
# Config
# ═══════════════════════════════════════════════════════════════════════

PAPER_LINKS = ROOT / "data" / "paper_links.json"
RAW_DIR = ROOT / "data" / "raw"
BASELINE_DIR = ROOT / "data" / "processed"
EXAMPLES_DIR = ROOT / "data" / "fewshot_examples"
OUTPUT_BASE = ROOT / "data" / "extractions" / "fewshot"

MODEL_ID = "claude-sonnet-4-5-20250929"
TEMPERATURE = 0.0
MAX_TOKENS = 4096

# Example order (1-shot uses first, 3-shot uses all three)
EXAMPLE_IDS = [
    "google_boolq",                       # NLP / QA
    "lmms-lab_ChartQA",                   # Vision / Multimodal
    "livecodebench_code_generation_lite",  # Code
]

# Rate limiting
MIN_DELAY_SECONDS = 1.0
RATE_LIMIT_DELAY = 60

# Schema block (same as USER_PROMPT_TEMPLATE but we build the prompt differently)
SCHEMA_BLOCK = """{
  "name": "string",
  "description": "string",
  "url": "string",
  "license": "string",
  "creator": "object or string",
  "publisher": "string",
  "datePublished": "string (YYYY-MM-DD or YYYY)",
  "inLanguage": "string (ISO codes)",
  "citeAs": "string",
  "isLiveDataset": "string (Yes/No)",

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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("fewshot_ablation")

# ═══════════════════════════════════════════════════════════════════════
# Example loading and prompt building
# ═══════════════════════════════════════════════════════════════════════


def load_examples(n: int) -> list:
    """Load N few-shot examples from data/fewshot_examples/."""
    examples = []
    for ds_id in EXAMPLE_IDS[:n]:
        path = EXAMPLES_DIR / f"{ds_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Few-shot example not found: {path}")
        with open(path) as f:
            examples.append(json.load(f))
    return examples


def build_fewshot_prompt(paper_text: str, examples: list) -> str:
    """Build the user prompt with few-shot examples prepended.

    Format:
      Extract metadata from academic papers according to the schema.
      [schema]

      Here are N examples of correct extractions:

      Example 1:
      Paper excerpt: [summary]
      Extraction: [JSON]

      ...

      Now extract metadata from the following paper:
      [paper text]

      Return ONLY valid JSON matching the schema above.
    """
    parts = []

    parts.append(
        "Extract metadata from the following academic paper by matching text "
        "to the field descriptions above. Your output must conform exactly to "
        "the following schema:\n\n"
        f"SCHEMA:\n{SCHEMA_BLOCK}\n"
    )

    if examples:
        parts.append(
            f"\nHere are {len(examples)} example(s) of correct metadata extractions:\n"
        )
        for i, ex in enumerate(examples, 1):
            extraction_json = json.dumps(ex["extraction"], indent=2, ensure_ascii=False)
            # Trim paper summary to keep prompt manageable
            summary = ex["paper_summary"][:2000]
            parts.append(
                f"--- Example {i} ---\n"
                f"Paper excerpt:\n{summary}\n\n"
                f"Extraction:\n{extraction_json}\n"
            )
        parts.append(
            "\n--- End of examples ---\n\n"
            "Now extract metadata from the following paper:\n"
        )
    else:
        parts.append("\n")

    parts.append(f"PAPER TEXT:\n{paper_text}\n\n")
    parts.append(
        "Return ONLY valid JSON matching the schema above. "
        "Do not include any markdown formatting or explanations."
    )

    return "".join(parts)


# ═══════════════════════════════════════════════════════════════════════
# PDF + LLM
# ═══════════════════════════════════════════════════════════════════════


def extract_text_from_pdf(pdf_path: Path) -> str:
    text = _canonical_clean_text(_canonical_extract_text(pdf_path))
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


def call_claude(system_prompt: str, user_prompt: str) -> dict:
    import anthropic
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    response = client.messages.create(
        model=MODEL_ID,
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
        system=[{"type": "text", "text": system_prompt}],
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = response.content[0].text.strip()

    if "```json" in raw:
        raw = raw.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in raw:
        raw = raw.split("```", 1)[1].split("```", 1)[0].strip()

    data = json.loads(raw)

    for field in CANONICAL_FIELDS:
        data.setdefault(field, None)
    data = {k: v for k, v in data.items() if k in CANONICAL_FIELDS}

    return data


# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(description="Few-Shot Ablation")
    parser.add_argument("--shots", required=True, type=int, choices=[0, 1, 3],
                        help="Number of few-shot examples")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true",
                        help="Show prompt sizes without API calls")
    args = parser.parse_args()

    condition = f"{args.shots}shot"
    out_dir = OUTPUT_BASE / condition
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(PAPER_LINKS) as f:
        dataset_ids = sorted(json.load(f).keys())
    subset = dataset_ids[args.start:args.end]

    # Load examples (skip for 0-shot)
    examples = load_examples(args.shots) if args.shots > 0 else []

    # Don't use the example datasets themselves as targets
    example_ids = set(EXAMPLE_IDS[:args.shots])

    log.info(f"Condition: {condition} ({args.shots} examples)")
    log.info(f"Datasets: {len(subset)} (index {args.start}:{args.end or len(dataset_ids)})")
    if examples:
        log.info(f"Examples: {[e['dataset_id'] for e in examples]}")
        # Estimate prompt overhead from examples
        example_chars = sum(len(e["paper_summary"]) + len(json.dumps(e["extraction"])) for e in examples)
        log.info(f"Example overhead: ~{example_chars} chars ({example_chars // 4} tokens est.)")

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

        # Skip example datasets (avoid data leakage)
        if ds_id in example_ids:
            log.info(f"[{i+1}/{len(subset)}] {ds_id}: skipping (used as example)")
            skipped += 1
            continue

        # 0-shot: copy baseline
        if args.shots == 0:
            baseline = BASELINE_DIR / ds_id / "full_pdf_metadata_result.json"
            if baseline.exists():
                shutil.copy2(baseline, out_file)
                success += 1
            else:
                log.warning(f"[{i+1}/{len(subset)}] {ds_id}: baseline not found")
                failed += 1
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

        # Truncate paper text to leave room for examples
        example_overhead = sum(
            len(e["paper_summary"]) + len(json.dumps(e["extraction"])) + 200
            for e in examples
        )
        max_paper_chars = MAX_PDF_CHARS - example_overhead - 5000  # buffer for schema+instructions
        if len(full_text) > max_paper_chars:
            full_text = full_text[:max_paper_chars]

        user_prompt = build_fewshot_prompt(full_text, examples)

        if args.dry_run:
            log.info(f"[{i+1}/{len(subset)}] {ds_id}: paper={len(full_text)}, prompt={len(user_prompt)} chars")
            success += 1
            continue

        log.info(f"[{i+1}/{len(subset)}] {ds_id}: {len(user_prompt)} chars → Claude...")
        try:
            data = call_claude(SYSTEM_PROMPT, user_prompt)

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

        except json.JSONDecodeError as e:
            log.error(f"  JSON parse error: {e}")
            errors.append(f"{ds_id}: JSON parse: {e}")
            failed += 1
        except Exception as e:
            if "429" in str(e) or "rate" in str(e).lower():
                log.warning(f"  Rate limited. Waiting {RATE_LIMIT_DELAY}s...")
                time.sleep(RATE_LIMIT_DELAY)
                continue
            log.error(f"  API error: {e}")
            errors.append(f"{ds_id}: {e}")
            failed += 1

        time.sleep(MIN_DELAY_SECONDS)

    log.info(f"\n--- {condition} Summary ---")
    log.info(f"  Success: {success}, Skipped: {skipped}, Failed: {failed}")
    total_output = success + skipped
    if total_output != len(subset):
        log.warning(f"  ⚠ Input/output mismatch: {len(subset)} input, {total_output} output")
    if errors:
        log.warning(f"  Errors ({len(errors)}): {errors[:5]}")


if __name__ == "__main__":
    main()
