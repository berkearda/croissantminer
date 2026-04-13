#!/usr/bin/env python3
"""
Agentic Pipeline Phase 3: Targeted Schema-Guided Extraction.
Uses Claude Sonnet 4.5 on retrieved chunks (not full paper).
"""

import json
import os
import re
import sys
import time
from pathlib import Path
from collections import Counter, defaultdict

import anthropic
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

PHASE2_DIR = ROOT / "data" / "agentic" / "phase2"
PHASE3_DIR = ROOT / "data" / "agentic" / "phase3"
PHASE3_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED = ROOT / "data" / "processed"

DUPES = {"CIFAR", "FLORES", "MLS", "MMLU", "MMMU", "MSCOCO", "MathVista", "Visual Genome"}

GROUPS = {
    "G3_collection": {
        "fields": ["dataCollection", "dataCollectionType", "dataCollectionTimeframe",
                   "dataCollectionRawData", "dataCollectionMissingData"],
        "definitions": {
            "dataCollection": "Description of the data collection process.",
            "dataCollectionType": "Collection type(s): Surveys, Secondary Data analysis, Web Scraping, Manual Human Curator, Software Collection, Experiments, Web API, etc.",
            "dataCollectionTimeframe": "Timeframe (start and end date) of the collection process.",
            "dataCollectionRawData": "Description of the raw/source data.",
            "dataCollectionMissingData": "Description of missing data, if discussed.",
        },
    },
    "G4_annotation": {
        "fields": ["dataAnnotationProtocol", "dataAnnotationPlatform", "dataAnnotationAnalysis",
                   "annotationsPerItem", "annotatorDemographics", "machineAnnotationTools"],
        "definitions": {
            "dataAnnotationProtocol": "How annotations (labels, ratings) were created. Annotator instructions, workforce type, quality control.",
            "dataAnnotationPlatform": "Platform used for human annotation (e.g., Amazon MTurk, Prolific, Scale AI).",
            "dataAnnotationAnalysis": "Analysis of annotation quality (inter-annotator agreement, disagreement resolution).",
            "annotationsPerItem": "Number of human labels per dataset item.",
            "annotatorDemographics": "Demographics of annotators (background, qualifications, location).",
            "machineAnnotationTools": "ML tools used for automated annotation (e.g., NER tools, OCR, classifiers).",
        },
    },
    "G5_rai": {
        "fields": ["dataBiases", "dataLimitations", "dataSocialImpact",
                   "personalSensitiveInformation", "dataUseCases"],
        "definitions": {
            "dataBiases": "Known biases explicitly discussed by the authors. Do NOT invent generic bias warnings.",
            "dataLimitations": "Known limitations, caveats, non-recommended uses.",
            "dataSocialImpact": "Social impact discussion, if applicable.",
            "personalSensitiveInformation": "Sensitive human attributes collected (gender, age, race, location, etc.).",
            "dataUseCases": "Intended use cases (Training, Testing, Evaluation, Fine-tuning, etc.).",
        },
    },
    "G6_processing": {
        "fields": ["dataImputationProtocol", "dataManipulationProtocol",
                   "dataPreprocessingProtocol", "dataReleaseMaintenancePlan"],
        "definitions": {
            "dataImputationProtocol": "How missing/incomplete data were imputed or filled.",
            "dataManipulationProtocol": "Post-collection manipulation (augmentation, oversampling, synthetic generation).",
            "dataPreprocessingProtocol": "Steps to prepare data for ML (filtering, cleaning, tokenization, dedup).",
            "dataReleaseMaintenancePlan": "Versioning, update schedule, maintenance team, deprecation plans. Return null unless EXPLICITLY discussed.",
        },
    },
}

client = anthropic.Anthropic()
MODEL = "claude-sonnet-4-5-20250929"


def build_group_prompt(group_key, group_info, chunks, null_signals):
    """Build targeted extraction prompt for one group."""
    fields = group_info["fields"]
    defs = group_info["definitions"]

    field_block = "\n".join(f"- rai:{f}: {defs[f]}" for f in fields)

    evidence = "\n\n".join(
        f"[Section: {c.get('section', 'Unknown')}]\n{c['text']}"
        for c in chunks
    )

    signals_block = (
        f"Triage: {null_signals.get('triage_presence', '?')} "
        f"(confidence {null_signals.get('triage_confidence', '?')})\n"
        f"Keywords found: {null_signals.get('keywords_found', [])}\n"
        f"Classification: {null_signals.get('classification', '?')}"
    )

    schema = ", ".join(f'"{f}": {{...}}' for f in fields)

    return f"""You are extracting Croissant RAI metadata from an ML dataset paper.
Below are the most relevant passages for the following fields.

FIELDS TO EXTRACT:
{field_block}

EVIDENCE PASSAGES:
{evidence}

NULL SIGNALS:
{signals_block}

INSTRUCTIONS:
1. Extract each field's value from the evidence passages. Use null if genuinely absent.
2. For each non-null field, provide evidence_quote: the exact sentence supporting your extraction.
3. Classify each field as: PRESENT (explicitly stated), IMPLICIT (inferred), or ABSENT (not discussed).
4. Do NOT fabricate information. If passages don't contain the info, return null.

Return JSON:
{{{schema}}}

Each field object: {{"value": "..." or null, "status": "PRESENT"|"IMPLICIT"|"ABSENT", "confidence": 0.0-1.0, "evidence_quote": "..." or null}}

Return ONLY valid JSON."""


def call_claude(prompt):
    """Call Claude Sonnet 4.5."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        temperature=0.0,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text
    usage = {
        "input": response.usage.input_tokens,
        "output": response.usage.output_tokens,
    }
    return text, usage


def parse_json(text):
    text = text.strip()
    if text.startswith("```json"): text = text[7:]
    elif text.startswith("```"): text = text[3:]
    if text.endswith("```"): text = text[:-3]
    return json.loads(text.strip())


def extract_group(group_key, group_info, phase2_group):
    """Extract fields for one group using Claude."""
    classification = phase2_group.get("classification", "ABSENT")
    chunks = phase2_group.get("retrieved_chunks", [])
    null_signals = phase2_group.get("null_signals", {})

    # Skip ABSENT groups
    if classification == "ABSENT" or not chunks:
        result = {}
        for f in group_info["fields"]:
            result[f] = {"value": None, "status": "ABSENT", "confidence": 0.95, "evidence_quote": None}
        return result, {"input": 0, "output": 0}

    prompt = build_group_prompt(group_key, group_info, chunks, null_signals)
    raw, usage = call_claude(prompt)
    result = parse_json(raw)

    # Ensure all fields present
    for f in group_info["fields"]:
        if f not in result:
            result[f] = {"value": None, "status": "ABSENT", "confidence": 0.5, "evidence_quote": None}
        else:
            entry = result[f]
            entry.setdefault("value", None)
            entry.setdefault("status", "ABSENT" if entry["value"] is None else "PRESENT")
            entry.setdefault("confidence", 0.5)
            entry.setdefault("evidence_quote", None)

    return result, usage


def process_paper_phase3(ds_id):
    """Run Phase 3 on one paper."""
    p2_path = PHASE2_DIR / f"{ds_id}.json"
    if not p2_path.exists():
        return None

    with open(p2_path) as f:
        p2 = json.load(f)

    all_fields = {}
    total_usage = {"input": 0, "output": 0}

    for group_key, group_info in GROUPS.items():
        p2_group = p2.get("groups", {}).get(group_key, {})

        result, usage = extract_group(group_key, group_info, p2_group)

        # Prefix fields with rai:
        for f in group_info["fields"]:
            all_fields[f"rai:{f}"] = result.get(f, {"value": None, "status": "ABSENT", "confidence": 0.5, "evidence_quote": None})

        total_usage["input"] += usage["input"]
        total_usage["output"] += usage["output"]

    return {
        "dataset_id": ds_id,
        "extractions": all_fields,
        "usage": total_usage,
    }


# ═══════════════════════════════════════════════════════════════
# VALIDATION
# ═══════════════════════════════════════════════════════════════

def validate_structural(ds_ids):
    """Layer 1: Structural validation."""
    print("\n  Layer 1: Structural...")
    issues = []
    for ds_id in ds_ids:
        p3_path = PHASE3_DIR / f"{ds_id}.json"
        if not p3_path.exists():
            issues.append((ds_id, "MISSING"))
            continue
        with open(p3_path) as f:
            p3 = json.load(f)
        for field_key, entry in p3.get("extractions", {}).items():
            if not isinstance(entry, dict):
                issues.append((ds_id, f"{field_key}: not a dict"))
                continue
            for key in ["value", "status", "confidence", "evidence_quote"]:
                if key not in entry:
                    issues.append((ds_id, f"{field_key}: missing '{key}'"))
            status = entry.get("status", "")
            val = entry.get("value")
            if status in ("PRESENT", "IMPLICIT") and val is None:
                issues.append((ds_id, f"{field_key}: status={status} but value is null"))
            if status == "ABSENT" and val is not None:
                issues.append((ds_id, f"{field_key}: status=ABSENT but has value"))
            if val is not None and not entry.get("evidence_quote"):
                pass  # Warn but don't block
    print(f"    {len(ds_ids) - len(set(d for d,_ in issues))}/{len(ds_ids)} clean, {len(issues)} issues")
    for d, i in issues[:5]:
        print(f"      {d}: {i}")
    return issues


def validate_evidence(ds_ids):
    """Layer 2: Evidence grounding."""
    print("\n  Layer 2: Evidence grounding...")
    total_quotes = 0
    verified = 0
    ungrounded = []

    for ds_id in ds_ids:
        p3_path = PHASE3_DIR / f"{ds_id}.json"
        p2_path = PHASE2_DIR / f"{ds_id}.json"
        if not p3_path.exists() or not p2_path.exists():
            continue
        with open(p3_path) as f:
            p3 = json.load(f)
        with open(p2_path) as f:
            p2 = json.load(f)

        # Collect all chunk text
        all_chunk_text = ""
        for g in p2.get("groups", {}).values():
            for chunk in g.get("retrieved_chunks", []):
                all_chunk_text += chunk.get("text", "") + " "
        all_chunk_lower = all_chunk_text.lower()

        for field_key, entry in p3.get("extractions", {}).items():
            quote = entry.get("evidence_quote")
            if quote and entry.get("value") is not None:
                total_quotes += 1
                # Check if quote appears in chunks (fuzzy: first 40 chars)
                quote_start = quote[:40].lower().strip()
                if quote_start in all_chunk_lower:
                    verified += 1
                else:
                    ungrounded.append((ds_id, field_key, quote[:60]))

    print(f"    {verified}/{total_quotes} quotes verified, {len(ungrounded)} ungrounded")
    for d, f, q in ungrounded[:3]:
        print(f"      {d}/{f}: '{q}...'")
    return verified, total_quotes, ungrounded


def validate_vs_claude(dev_ids):
    """Layer 3: Compare with single-pass Claude."""
    print("\n  Layer 3: vs Claude baseline (dev)...")
    field_agree = defaultdict(lambda: {"both_null": 0, "both_val": 0, "p3_only": 0, "claude_only": 0, "total": 0})

    for ds_id in dev_ids:
        p3_path = PHASE3_DIR / f"{ds_id}.json"
        claude_path = PROCESSED / ds_id / "full_pdf_metadata_result.json"
        if not p3_path.exists() or not claude_path.exists():
            continue
        with open(p3_path) as f:
            p3 = json.load(f)
        with open(claude_path) as f:
            claude = json.load(f)

        for field_key, entry in p3.get("extractions", {}).items():
            p3_val = entry.get("value")
            claude_val = claude.get(field_key)
            claude_has = claude_val is not None and str(claude_val).strip()
            p3_has = p3_val is not None and str(p3_val).strip()

            field_agree[field_key]["total"] += 1
            if not claude_has and not p3_has:
                field_agree[field_key]["both_null"] += 1
            elif claude_has and p3_has:
                field_agree[field_key]["both_val"] += 1
            elif p3_has and not claude_has:
                field_agree[field_key]["p3_only"] += 1
            elif claude_has and not p3_has:
                field_agree[field_key]["claude_only"] += 1

    print(f"    {'Field':<35} {'Both':>5} {'BothN':>6} {'P3only':>7} {'Claude':>7}")
    print(f"    {'-'*60}")
    for f in sorted(field_agree.keys()):
        a = field_agree[f]
        t = max(a["total"], 1)
        print(f"    {f:<35} {a['both_val']:>5} {a['both_null']:>6} {a['p3_only']:>7} {a['claude_only']:>7}")
    return field_agree


def validate_distribution(ds_ids):
    """Layer 4: Ternary classification distribution."""
    print("\n  Layer 4: Classification distribution...")
    dist = defaultdict(Counter)
    for ds_id in ds_ids:
        p3_path = PHASE3_DIR / f"{ds_id}.json"
        if not p3_path.exists(): continue
        with open(p3_path) as f:
            p3 = json.load(f)
        for field_key, entry in p3.get("extractions", {}).items():
            dist[field_key][entry.get("status", "?")] += 1

    print(f"    {'Field':<35} {'PRESENT':>8} {'IMPLICIT':>9} {'ABSENT':>7}")
    print(f"    {'-'*60}")
    flags = []
    for f in sorted(dist.keys()):
        p = dist[f]["PRESENT"]
        i = dist[f]["IMPLICIT"]
        a = dist[f]["ABSENT"]
        print(f"    {f:<35} {p:>8} {i:>9} {a:>7}")
        if a == 0:
            flags.append(f"{f}: 0 ABSENT")
    if flags:
        print(f"    FLAGS: {', '.join(flags[:3])}")
    return dist


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    all_ds = sorted(
        p.parent.name for p in PROCESSED.glob("*/full_pdf_metadata_result.json")
        if p.parent.name not in DUPES
    )

    split_path = ROOT / "data" / "agentic" / "dev_test_split.json"
    with open(split_path) as f:
        split = json.load(f)
    dev_ids = split["dev"]
    test_ids = split["test"]

    # ── DEV SET ──
    print(f"{'='*70}")
    print(f"PHASE 3 EXTRACT — DEV SET ({len(dev_ids)} papers)")
    print(f"{'='*70}")

    total_in = 0; total_out = 0; dev_ok = 0

    for i, ds_id in enumerate(dev_ids):
        out_path = PHASE3_DIR / f"{ds_id}.json"
        if out_path.exists():
            print(f"  [{i+1}/{len(dev_ids)}] {ds_id} — SKIP (exists)")
            dev_ok += 1
            continue

        for attempt in range(3):
            try:
                result = process_paper_phase3(ds_id)
                if result is None:
                    print(f"  [{i+1}/{len(dev_ids)}] {ds_id} — SKIP (no P2)")
                    break
                with open(out_path, "w") as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)
                total_in += result["usage"]["input"]
                total_out += result["usage"]["output"]
                n_extracted = sum(1 for v in result["extractions"].values() if v.get("value") is not None)
                print(f"  [{i+1}/{len(dev_ids)}] {ds_id} — {n_extracted}/20 fields extracted ({result['usage']['input']}in/{result['usage']['output']}out)")
                dev_ok += 1
                break
            except Exception as e:
                if attempt < 2:
                    time.sleep(5 * (2 ** attempt))
                else:
                    print(f"  [{i+1}/{len(dev_ids)}] {ds_id} — FAIL ({str(e)[:60]})")
        time.sleep(3)

    # ── DEV VALIDATION ──
    print(f"\n{'='*70}")
    print(f"DEV VALIDATION")
    print(f"{'='*70}")

    validate_structural(dev_ids)
    validate_evidence(dev_ids)
    validate_vs_claude(dev_ids)
    validate_distribution(dev_ids)

    cost = total_in / 1e6 * 3.0 + total_out / 1e6 * 15.0
    print(f"\n  Dev cost: ${cost:.3f} ({total_in:,} in, {total_out:,} out)")
    print(f"\n  Waiting for review before proceeding to test set...")
    print(f"  To continue, re-run with --full flag")

    # Check if --full flag
    if "--full" not in sys.argv:
        return

    # ── TEST SET ──
    print(f"\n{'='*70}")
    print(f"PHASE 3 EXTRACT — TEST SET ({len(test_ids)} papers)")
    print(f"{'='*70}")

    test_ok = 0
    for i, ds_id in enumerate(test_ids):
        out_path = PHASE3_DIR / f"{ds_id}.json"
        if out_path.exists():
            test_ok += 1
            if (i + 1) % 20 == 0:
                print(f"  [{i+1}/{len(test_ids)}] {test_ok} OK (skipping existing)")
            continue

        for attempt in range(3):
            try:
                result = process_paper_phase3(ds_id)
                if result is None:
                    break
                with open(out_path, "w") as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)
                total_in += result["usage"]["input"]
                total_out += result["usage"]["output"]
                test_ok += 1
                break
            except Exception as e:
                if attempt < 2:
                    time.sleep(5 * (2 ** attempt))
                else:
                    print(f"  [{i+1}/{len(test_ids)}] {ds_id} — FAIL ({str(e)[:60]})")
        if (i + 1) % 20 == 0:
            print(f"  [{i+1}/{len(test_ids)}] {test_ok} OK")
        time.sleep(3)

    print(f"  [{len(test_ids)}/{len(test_ids)}] {test_ok} OK")

    # ── FULL VALIDATION ──
    print(f"\n{'='*70}")
    print(f"FULL VALIDATION")
    print(f"{'='*70}")

    validate_structural(all_ds)
    validate_evidence(all_ds)
    validate_vs_claude(dev_ids)
    validate_distribution(all_ds)

    total_cost = total_in / 1e6 * 3.0 + total_out / 1e6 * 15.0
    print(f"\n{'='*70}")
    print(f"PHASE 3 SUMMARY")
    print(f"{'='*70}")
    p3_count = len(list(PHASE3_DIR.glob("*.json")))
    print(f"  Papers: {p3_count}/103")
    print(f"  Tokens: {total_in:,} in, {total_out:,} out")
    print(f"  Cost: ${total_cost:.2f}")

    summary = {
        "phase": 3,
        "model": MODEL,
        "papers_processed": p3_count,
        "total_input_tokens": total_in,
        "total_output_tokens": total_out,
        "cost_usd": round(total_cost, 2),
    }
    with open(ROOT / "results" / "agentic_phase3_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"  Summary: results/agentic_phase3_summary.json")


if __name__ == "__main__":
    main()
