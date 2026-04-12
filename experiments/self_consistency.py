#!/usr/bin/env python3
"""
Self-Consistency Extraction Experiment

Runs extraction k times per paper with temperature=0.7, then merges via voting.

Voting strategy by field type:
  Constrained: majority vote on normalized strings; tie → first extraction
  Short-text:  majority vote on exact strings; tie → longest response
  RAI:         exact voting first; if no majority → longest (most detailed)

Usage:
  python experiments/self_consistency.py --k 3
  python experiments/self_consistency.py --k 5 --start 0 --end 50
  python experiments/self_consistency.py --k 3 --merge-only   # skip API, just re-merge
  python experiments/self_consistency.py --k 3 --dry-run
"""

import argparse
import json
import logging
import os
import re
import sys
import time
from collections import Counter
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
OUTPUT_BASE = ROOT / "data" / "extractions" / "self_consistency"

MODEL_ID = "claude-sonnet-4-5-20250929"
TEMPERATURE = 0.7  # non-zero for diversity
MAX_TOKENS = 4096
MIN_DELAY = 1.0
RATE_LIMIT_DELAY = 60

# Field type classification
CONSTRAINED_FIELDS = frozenset({
    "name", "url", "license", "datePublished", "inLanguage",
    "isLiveDataset", "citeAs", "publisher",
})
SHORT_TEXT_FIELDS = frozenset({"creator", "description"})
# Everything else in CANONICAL_FIELDS is RAI (long text)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("self_consistency")

# ═══════════════════════════════════════════════════════════════════════
# PDF helpers
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
# LLM
# ═══════════════════════════════════════════════════════════════════════


def call_claude(paper_text: str) -> dict:
    import anthropic
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    if len(paper_text) > MAX_PDF_CHARS:
        paper_text = paper_text[:MAX_PDF_CHARS]

    user_prompt = USER_PROMPT_TEMPLATE % paper_text

    response = client.messages.create(
        model=MODEL_ID,
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
        system=[{"type": "text", "text": SYSTEM_PROMPT}],
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
# Voting / Merging
# ═══════════════════════════════════════════════════════════════════════


def normalize_for_vote(val):
    """Normalize a value for majority voting comparison."""
    if val is None:
        return None
    s = str(val).strip().lower()
    if not s or s in ("null", "none", "n/a"):
        return None
    return s


def value_length(val):
    """Length of a value (for tiebreaking: longer = more detailed)."""
    if val is None:
        return 0
    return len(str(val).strip())


def vote_field(field: str, values: list):
    """Vote across k extractions for a single field.

    Args:
        field: field name
        values: list of k extracted values (may include None)

    Returns:
        (winner, agreement_pct, method)
    """
    k = len(values)
    if k == 0:
        return None, 0, "empty"

    # Normalize for comparison
    normalized = [normalize_for_vote(v) for v in values]
    non_null = [(v, orig) for v, orig in zip(normalized, values) if v is not None]

    # All null → null is the answer
    if not non_null:
        return None, 100.0, "unanimous_null"

    # Count occurrences of each normalized value
    counter = Counter(v for v, _ in non_null)
    most_common_val, most_common_count = counter.most_common(1)[0]
    agreement = most_common_count / k * 100

    # If there's a clear majority
    if most_common_count > k / 2:
        # Return the ORIGINAL (unnormalized) value that matches
        for v, orig in non_null:
            if v == most_common_val:
                return orig, agreement, "majority"

    # No majority — tiebreak depends on field type
    if field in CONSTRAINED_FIELDS:
        # Use the first extraction (deterministic fallback)
        return values[0], agreement, "first_fallback"

    elif field in SHORT_TEXT_FIELDS:
        # Pick the longest non-null response
        best = max(non_null, key=lambda x: value_length(x[1]))
        return best[1], agreement, "longest"

    else:
        # RAI field: pick longest non-null response (most detailed)
        best = max(non_null, key=lambda x: value_length(x[1]))
        return best[1], agreement, "longest"


def merge_extractions(runs: list) -> tuple:
    """Merge k extraction dicts via field-level voting.

    Returns:
        (merged_dict, agreement_report)
    """
    k = len(runs)
    merged = {}
    report = {}

    for field in sorted(CANONICAL_FIELDS):
        values = [run.get(field) for run in runs]
        winner, agreement, method = vote_field(field, values)
        merged[field] = winner
        report[field] = {
            "agreement_pct": round(agreement, 1),
            "method": method,
            "unique_values": len(set(normalize_for_vote(v) for v in values)),
            "non_null_count": sum(1 for v in values if normalize_for_vote(v) is not None),
        }

    return merged, report


# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(description="Self-Consistency Extraction")
    parser.add_argument("--k", required=True, type=int, choices=[3, 5],
                        help="Number of extraction runs per paper")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=None)
    parser.add_argument("--merge-only", action="store_true",
                        help="Skip API calls, just re-merge existing runs")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    k = args.k
    k_dir = OUTPUT_BASE / f"k{k}"

    with open(PAPER_LINKS) as f:
        dataset_ids = sorted(json.load(f).keys())
    subset = dataset_ids[args.start:args.end]

    log.info(f"Self-consistency: k={k}, temperature={TEMPERATURE}")
    log.info(f"Datasets: {len(subset)}")

    # ── Phase 1: Generate k runs ──
    if not args.merge_only:
        for run_idx in range(k):
            run_dir = k_dir / f"run_{run_idx}"
            run_dir.mkdir(parents=True, exist_ok=True)

            log.info(f"\n{'='*60}")
            log.info(f"Run {run_idx + 1}/{k}")
            log.info(f"{'='*60}")

            success = 0
            skipped = 0
            failed = 0

            for i, ds_id in enumerate(subset):
                out_file = run_dir / f"{ds_id}.json"
                if out_file.exists():
                    skipped += 1
                    continue

                pdf_path = find_pdf(ds_id)
                if not pdf_path:
                    failed += 1
                    continue

                try:
                    full_text = extract_text_from_pdf(pdf_path)
                except Exception:
                    failed += 1
                    continue

                if args.dry_run:
                    log.info(f"  [{i+1}/{len(subset)}] {ds_id}: {len(full_text)} chars")
                    success += 1
                    continue

                log.info(f"  [{i+1}/{len(subset)}] {ds_id} (run {run_idx+1})...")
                try:
                    data = call_claude(full_text)
                    valid, errs = validate_extraction(data, ds_id)
                    if not valid:
                        for field in CANONICAL_FIELDS:
                            data.setdefault(field, None)
                        data = {kk: v for kk, v in data.items() if kk in CANONICAL_FIELDS}

                    with open(out_file, "w") as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                    success += 1

                except json.JSONDecodeError:
                    failed += 1
                except Exception as e:
                    if "429" in str(e) or "rate" in str(e).lower():
                        log.warning(f"  Rate limited. Waiting {RATE_LIMIT_DELAY}s...")
                        time.sleep(RATE_LIMIT_DELAY)
                        continue
                    failed += 1

                time.sleep(MIN_DELAY)

            log.info(f"  Run {run_idx+1}: {success} success, {skipped} cached, {failed} failed")

    # ── Phase 2: Merge via voting ──
    log.info(f"\n{'='*60}")
    log.info(f"Merging {k} runs via field-level voting")
    log.info(f"{'='*60}")

    merged_dir = k_dir / "merged"
    merged_dir.mkdir(parents=True, exist_ok=True)

    field_agreements = {f: [] for f in sorted(CANONICAL_FIELDS)}
    merged_count = 0
    incomplete = 0

    for ds_id in subset:
        # Load all k runs
        runs = []
        for run_idx in range(k):
            run_file = k_dir / f"run_{run_idx}" / f"{ds_id}.json"
            if run_file.exists():
                with open(run_file) as f:
                    runs.append(json.load(f))

        if len(runs) < 2:
            log.warning(f"  {ds_id}: only {len(runs)}/{k} runs available, skipping merge")
            incomplete += 1
            continue

        merged, report = merge_extractions(runs)

        # Save merged output
        with open(merged_dir / f"{ds_id}.json", "w") as f:
            json.dump(merged, f, indent=2, ensure_ascii=False)

        # Save per-dataset agreement report
        with open(merged_dir / f"{ds_id}_agreement.json", "w") as f:
            json.dump(report, f, indent=2)

        # Accumulate field-level agreement stats
        for field, info in report.items():
            field_agreements[field].append(info["agreement_pct"])

        merged_count += 1

    # ── Agreement Report ──
    log.info(f"\nMerged: {merged_count} datasets, {incomplete} incomplete")
    log.info(f"\nPer-field agreement across {k} runs:")
    log.info(f"{'Field':<45} {'Mean%':>6} {'Min%':>6} {'Unanimous':>10}")
    log.info("-" * 72)

    summary = {}
    for field in sorted(field_agreements.keys()):
        vals = field_agreements[field]
        if not vals:
            continue
        import numpy as np
        mean_agr = np.mean(vals)
        min_agr = min(vals)
        unanimous = sum(1 for v in vals if v == 100.0)
        pct_unanimous = unanimous / len(vals) * 100

        ftype = "C" if field in CONSTRAINED_FIELDS else "S" if field in SHORT_TEXT_FIELDS else "R"
        log.info(f"  {field:<43} {mean_agr:>5.1f}% {min_agr:>5.1f}% {pct_unanimous:>8.0f}% ({unanimous}/{len(vals)})")

        summary[field] = {
            "type": ftype,
            "mean_agreement": round(mean_agr, 1),
            "min_agreement": round(min_agr, 1),
            "pct_unanimous": round(pct_unanimous, 1),
            "n_datasets": len(vals),
        }

    # Category averages
    log.info(f"\nBy field type:")
    for ftype, label in [("C", "Constrained"), ("S", "Short-text"), ("R", "RAI")]:
        type_vals = [s["mean_agreement"] for s in summary.values() if s["type"] == ftype]
        if type_vals:
            import numpy as np
            log.info(f"  {label:<15} mean={np.mean(type_vals):.1f}%, "
                     f"unanimous={np.mean([s['pct_unanimous'] for s in summary.values() if s['type']==ftype]):.0f}%")

    # Save summary
    with open(k_dir / "agreement_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    log.info(f"\nSaved: {k_dir}/agreement_summary.json")


if __name__ == "__main__":
    main()
