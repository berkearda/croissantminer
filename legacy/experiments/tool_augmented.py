#!/usr/bin/env python3
"""
Tool-Augmented Extraction Pipeline

Validates existing extractions using external tools (URL checker, SPDX license
lookup, arXiv metadata, HuggingFace API), then sends a correction prompt to
the LLM for any failures.

Pipeline:
  1. Load existing extraction (Claude baseline)
  2. Run validators on applicable fields
  3. Collect failures into a correction prompt
  4. Call Claude for corrections (if any failures)
  5. Merge corrections, re-validate
  6. Save final output + validation report

Usage:
  python experiments/tool_augmented.py
  python experiments/tool_augmented.py --start 0 --end 50
  python experiments/tool_augmented.py --validate-only   # no correction calls
  python experiments/tool_augmented.py --dry-run
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from config import SYSTEM_PROMPT, MAX_PDF_CHARS
from validation.validate_extraction import validate_extraction, CANONICAL_FIELDS

from experiments.validators.url_validator import validate_url
from experiments.validators.license_validator import validate_license
from experiments.validators.arxiv_validator import validate_arxiv
from experiments.validators.hf_validator import validate_hf_dataset
from experiments.validators.doi_validator import validate_doi

# ═══════════════════════════════════════════════════════════════════════
# Config
# ═══════════════════════════════════════════════════════════════════════

PAPER_LINKS = ROOT / "data" / "paper_links.json"
BASELINE_DIR = ROOT / "data" / "processed"
OUTPUT_DIR = ROOT / "data" / "extractions" / "tool_augmented"
REPORT_DIR = ROOT / "results" / "validation_reports"

MODEL_ID = "claude-sonnet-4-5-20250929"
TEMPERATURE = 0.0
MAX_TOKENS = 4096
MIN_DELAY = 1.5

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("tool_augmented")

# ═══════════════════════════════════════════════════════════════════════
# Correction prompt
# ═══════════════════════════════════════════════════════════════════════

CORRECTION_PROMPT = """You previously extracted metadata from an academic paper. Some fields failed external validation. Please correct ONLY the failed fields.

Original extraction:
{original_json}

Validation failures:
{failures}

Based on the paper text below, provide corrected values for the failed fields ONLY.
Output as a JSON object with only the corrected field names and values.
If a field truly has no information in the paper, return null for that field.

Paper text (relevant sections):
{paper_excerpt}

Return ONLY valid JSON with the corrected fields. No markdown, no explanation."""

# ═══════════════════════════════════════════════════════════════════════
# Validation orchestration
# ═══════════════════════════════════════════════════════════════════════


def run_validators(extraction: dict, paper_url: str) -> dict:
    """Run all applicable validators on an extraction.

    Returns:
        {field: {validator: str, result: dict, passed: bool, message: str}}
    """
    results = {}

    # URL validation
    url_val = extraction.get("url")
    if url_val and str(url_val).strip():
        vr = validate_url(str(url_val))
        results["url"] = {
            "validator": "url_reachability",
            "result": vr,
            "passed": vr["valid"],
            "message": vr["error"] or "OK",
        }

    # License validation (SPDX)
    license_val = extraction.get("license")
    if license_val and str(license_val).strip():
        vr = validate_license(str(license_val))
        results["license"] = {
            "validator": "spdx_license",
            "result": vr,
            "passed": vr["valid"],
            "message": vr["suggestion"] or ("Valid SPDX: " + (vr["spdx_id"] or "")),
        }

    # arXiv cross-check (datePublished, creator)
    if paper_url and "arxiv.org" in paper_url:
        vr = validate_arxiv(paper_url)
        if vr["valid"]:
            # Check datePublished
            extracted_date = extraction.get("datePublished")
            if extracted_date and vr["published"]:
                arxiv_year = vr["published"][:4]
                if arxiv_year not in str(extracted_date):
                    results["datePublished"] = {
                        "validator": "arxiv_crosscheck",
                        "result": vr,
                        "passed": False,
                        "message": f"Extracted '{extracted_date}' but arXiv says published {vr['published']}",
                    }
                else:
                    results["datePublished"] = {
                        "validator": "arxiv_crosscheck",
                        "result": vr,
                        "passed": True,
                        "message": f"Year matches arXiv ({arxiv_year})",
                    }

    # citeAs — DOI check (only if it looks like it has a DOI)
    cite_val = extraction.get("citeAs")
    if cite_val and "10." in str(cite_val):
        vr = validate_doi(str(cite_val))
        results["citeAs"] = {
            "validator": "doi_resolution",
            "result": vr,
            "passed": vr["valid"],
            "message": vr["error"] or f"DOI resolves: {vr.get('resolved_title', '')[:60]}",
        }

    return results


def build_correction_prompt(extraction: dict, failures: dict, paper_text: str) -> str:
    """Build a correction prompt from validation failures."""
    failure_lines = []
    for field, info in failures.items():
        failure_lines.append(f"- {field}: {info['message']}")
        if info["result"].get("suggestion"):
            failure_lines.append(f"  Suggestion: {info['result']['suggestion']}")

    # Use first 5000 chars of paper as context (relevant sections)
    excerpt = paper_text[:5000] if paper_text else "[paper text not available]"

    return CORRECTION_PROMPT.format(
        original_json=json.dumps(
            {f: extraction.get(f) for f in failures.keys()},
            indent=2, ensure_ascii=False
        ),
        failures="\n".join(failure_lines),
        paper_excerpt=excerpt,
    )


def call_correction(prompt: str) -> dict:
    """Call Claude for field corrections."""
    import anthropic
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    response = client.messages.create(
        model=MODEL_ID,
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
        system=[{"type": "text", "text": "You are correcting metadata extraction errors based on validation feedback."}],
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    if "```json" in raw:
        raw = raw.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in raw:
        raw = raw.split("```", 1)[1].split("```", 1)[0].strip()

    return json.loads(raw)


# ═══════════════════════════════════════════════════════════════════════
# PDF helper
# ═══════════════════════════════════════════════════════════════════════


def load_paper_text(ds_id: str) -> str:
    """Load paper text for a dataset (for correction prompt context)."""
    from croissantminer.pdf.reader import extract_text_from_pdf as _canonical_extract_text
    from croissantminer.pdf.processor import clean_text as _canonical_clean_text
    RAW_DIR = ROOT / "data" / "raw"
    BENCHMARK_MAP = {
        "CIFAR_30field": "2404.00498v2", "FLORES_30field": "2106.03193v1",
        "MLS_30field": "2012.03411v2", "MMLU_30field": "2009.03300v3",
        "MMMU_30field": "2311.16502v4", "MSCOCO_30field": "1405.0312v3",
        "MathVista_30field": "2310.02255v3", "Visual_Genome_30field": "1602.07332v1",
    }

    pdf_path = RAW_DIR / f"{ds_id}.pdf"
    if not pdf_path.exists() and ds_id in BENCHMARK_MAP:
        for base in [RAW_DIR, ROOT / "data"]:
            p = base / f"{BENCHMARK_MAP[ds_id]}.pdf"
            if p.exists():
                pdf_path = p
                break

    if not pdf_path.exists():
        return ""

    text = _canonical_clean_text(_canonical_extract_text(pdf_path))
    return text


# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(description="Tool-Augmented Pipeline")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=None)
    parser.add_argument("--validate-only", action="store_true",
                        help="Run validators only, no correction calls")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    with open(PAPER_LINKS) as f:
        paper_links = json.load(f)
    dataset_ids = sorted(paper_links.keys())
    subset = dataset_ids[args.start:args.end]

    log.info(f"Tool-Augmented Pipeline")
    log.info(f"Datasets: {len(subset)}")
    log.info(f"Mode: {'validate-only' if args.validate_only else 'validate + correct'}")

    total_validated = 0
    total_failures = 0
    total_corrected = 0
    total_skipped = 0
    all_reports = {}

    for i, ds_id in enumerate(subset):
        out_file = OUTPUT_DIR / f"{ds_id}.json"

        # Cache
        if out_file.exists() and not args.validate_only:
            total_skipped += 1
            continue

        # Load baseline extraction
        baseline = BASELINE_DIR / ds_id / "full_pdf_metadata_result.json"
        if not baseline.exists():
            log.warning(f"[{i+1}/{len(subset)}] {ds_id}: no baseline extraction")
            continue

        with open(baseline) as f:
            extraction = json.load(f)

        paper_url = paper_links.get(ds_id, "")

        if args.dry_run:
            log.info(f"[{i+1}/{len(subset)}] {ds_id}: would validate {len(extraction)} fields")
            total_validated += 1
            continue

        # Run validators
        log.info(f"[{i+1}/{len(subset)}] {ds_id}: validating...")
        validation_results = run_validators(extraction, paper_url)
        total_validated += 1

        # Collect failures
        failures = {f: r for f, r in validation_results.items() if not r["passed"]}
        passes = {f: r for f, r in validation_results.items() if r["passed"]}

        n_checked = len(validation_results)
        n_failed = len(failures)
        n_passed = len(passes)

        for f, r in passes.items():
            log.info(f"  ✓ {f}: {r['message'][:60]}")
        for f, r in failures.items():
            log.info(f"  ✗ {f}: {r['message'][:60]}")
            total_failures += 1

        # Store report
        all_reports[ds_id] = {
            "checked": n_checked,
            "passed": n_passed,
            "failed": n_failed,
            "results": {f: {k: v for k, v in r.items() if k != "result"}
                        for f, r in validation_results.items()},
        }

        if args.validate_only:
            continue

        # Correct if failures
        final = dict(extraction)
        if failures:
            log.info(f"  → {n_failed} failures, sending correction prompt...")
            try:
                paper_text = load_paper_text(ds_id)
                prompt = build_correction_prompt(extraction, failures, paper_text)
                corrections = call_correction(prompt)

                # Merge corrections (only for failed fields, only canonical)
                for field, new_val in corrections.items():
                    if field in failures and field in CANONICAL_FIELDS:
                        old_val = final.get(field)
                        final[field] = new_val
                        log.info(f"  ↻ {field}: '{str(old_val)[:30]}' → '{str(new_val)[:30]}'")
                        total_corrected += 1

                time.sleep(MIN_DELAY)

            except Exception as e:
                log.error(f"  Correction failed: {e}")

        # Validate final output
        valid, errs = validate_extraction(final, ds_id)
        if not valid:
            for field in CANONICAL_FIELDS:
                final.setdefault(field, None)
            final = {k: v for k, v in final.items() if k in CANONICAL_FIELDS}

        # Save
        with open(out_file, "w") as f:
            json.dump(final, f, indent=2, ensure_ascii=False)

    # Save validation reports
    report_path = REPORT_DIR / "tool_validation_report.json"
    with open(report_path, "w") as f:
        json.dump(all_reports, f, indent=2, ensure_ascii=False)

    # Summary
    log.info(f"\n{'='*60}")
    log.info(f"SUMMARY")
    log.info(f"{'='*60}")
    log.info(f"  Validated: {total_validated}")
    log.info(f"  Skipped (cached): {total_skipped}")
    log.info(f"  Total field failures: {total_failures}")
    log.info(f"  Fields corrected: {total_corrected}")
    log.info(f"  Reports: {report_path}")

    if total_validated != len(subset) - total_skipped:
        log.warning(f"  ⚠ Input/output mismatch")

    # Aggregate failure stats
    if all_reports:
        from collections import Counter
        field_fails = Counter()
        for ds_report in all_reports.values():
            for field, info in ds_report.get("results", {}).items():
                if not info["passed"]:
                    field_fails[field] += 1

        if field_fails:
            log.info(f"\n  Failure breakdown by field:")
            for field, count in field_fails.most_common():
                log.info(f"    {field}: {count} failures")


if __name__ == "__main__":
    main()
