#!/usr/bin/env python3
"""
Agentic Phase 1 fix: Re-extract 10 easy fields with Claude Sonnet 4.5.
Then update combined extractions.
"""

import json
import os
import re
import sys
import time
from pathlib import Path
from collections import defaultdict

import anthropic
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

PROCESSED = ROOT / "data" / "processed"
PHASE1C_DIR = ROOT / "data" / "agentic" / "phase1_claude"
PHASE1C_DIR.mkdir(parents=True, exist_ok=True)
COMBINED_DIR = ROOT / "data" / "agentic" / "combined"
DUPES = {"CIFAR", "FLORES", "MLS", "MMLU", "MMMU", "MSCOCO", "MathVista", "Visual Genome"}

client = anthropic.Anthropic()
MODEL = "claude-sonnet-4-5-20250929"

EASY_FIELDS = ["name", "creator", "publisher", "datePublished", "url",
               "citeAs", "license", "isLiveDataset", "description", "inLanguage"]

SYSTEM_PROMPT = """You are an expert metadata extraction specialist for ML dataset papers.
Extract ONLY the 10 general metadata fields listed below from the paper text.
Use null if the information is not explicitly stated in the paper.
Do NOT guess or fabricate values.

Return ONLY valid JSON with these 10 keys:
- name: Dataset name as stated in the paper
- creator: Dataset creator(s)/author(s). Use "Name1, Name2 (Organization)" format.
- publisher: Publishing venue or organization
- datePublished: Dataset release date (YYYY or YYYY-MM-DD). Use the dataset release date, not the arxiv submission date.
- url: URL where the dataset can be accessed
- citeAs: Recommended citation format (BibTeX or text)
- license: Distribution license (MIT, CC-BY, Apache, etc.)
- isLiveDataset: "Yes" if actively updated, "No" if static, null if not discussed
- description: Brief description of the dataset (1-3 sentences)
- inLanguage: Content language(s) (ISO codes preferred, e.g., "en")"""

USER_TEMPLATE = """Extract the 10 general metadata fields from this paper.
Return ONLY valid JSON.

PAPER TEXT:
%s"""


def get_paper_text(ds_id):
    from croissantminer.pdf.reader import extract_text_from_pdf as _canonical_extract_text
    from croissantminer.pdf.processor import clean_text as _canonical_clean_text
    raw = ROOT / "data" / "raw"
    with open(ROOT / "data" / "paper_links.json") as f:
        pl = json.load(f)
    for name in [f"{ds_id}.pdf"]:
        p = raw / name
        if p.exists():
            return _canonical_clean_text(_canonical_extract_text(str(p)))
    url = pl.get(ds_id, "")
    m = re.search(r'(\d{4}\.\d{4,5})', url)
    if m:
        for sfx in ["", "v1", "v2", "v3", "v4", "v5"]:
            p = raw / f"{m.group(1)}{sfx}.pdf"
            if p.exists():
                return _canonical_clean_text(_canonical_extract_text(str(p)))
    return None


def extract_easy(ds_id):
    text = get_paper_text(ds_id)
    if not text:
        return None, None

    if len(text) > 300000:
        text = text[:300000]

    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        temperature=0.0,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": USER_TEMPLATE % text}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```json"): raw = raw[7:]
    elif raw.startswith("```"): raw = raw[3:]
    if raw.endswith("```"): raw = raw[:-3]

    result = json.loads(raw.strip())
    for f in EASY_FIELDS:
        result.setdefault(f, None)

    usage = {"input": response.usage.input_tokens, "output": response.usage.output_tokens}
    return result, usage


def main():
    all_ds = sorted(
        p.parent.name for p in PROCESSED.glob("*/full_pdf_metadata_result.json")
        if p.parent.name not in DUPES
    )

    with open(ROOT / "data/agentic/dev_test_split.json") as f:
        split = json.load(f)
    dev_ids = set(split["dev"])

    # ── Extract easy fields with Claude ──
    print(f"{'='*70}")
    print(f"PHASE 1 CLAUDE: Extract 10 easy fields ({len(all_ds)} papers)")
    print(f"{'='*70}")

    total_in = 0; total_out = 0; ok = 0; fail = 0

    for i, ds_id in enumerate(all_ds):
        out_path = PHASE1C_DIR / f"{ds_id}.json"
        if out_path.exists():
            ok += 1
            if (i + 1) % 25 == 0:
                print(f"  [{i+1}/{len(all_ds)}] {ok} OK (skipping existing)")
            continue

        for attempt in range(3):
            try:
                result, usage = extract_easy(ds_id)
                if result is None:
                    print(f"  [{i+1}/{len(all_ds)}] {ds_id} — NO TEXT")
                    fail += 1
                    break

                output = {"dataset_id": ds_id, "easy_fields": result, "usage": usage}
                with open(out_path, "w") as f:
                    json.dump(output, f, indent=2, ensure_ascii=False)

                total_in += usage["input"]
                total_out += usage["output"]
                ok += 1
                break

            except Exception as e:
                if attempt < 2:
                    time.sleep(5 * (2 ** attempt))
                else:
                    print(f"  [{i+1}/{len(all_ds)}] {ds_id} — FAIL ({str(e)[:50]})")
                    fail += 1

        if (i + 1) % 25 == 0:
            print(f"  [{i+1}/{len(all_ds)}] {ok} OK, {fail} failed")
        time.sleep(1)

    print(f"  [{len(all_ds)}/{len(all_ds)}] {ok} OK, {fail} failed")
    cost = total_in / 1e6 * 3.0 + total_out / 1e6 * 15.0
    print(f"  Tokens: {total_in:,} in, {total_out:,} out")
    print(f"  Cost: ${cost:.2f}")

    # ── Update combined extractions ──
    print(f"\n{'='*70}")
    print(f"UPDATING COMBINED EXTRACTIONS")
    print(f"{'='*70}")

    updated = 0
    for ds_id in all_ds:
        p1c_path = PHASE1C_DIR / f"{ds_id}.json"
        combined_path = COMBINED_DIR / f"{ds_id}.json"

        if not p1c_path.exists() or not combined_path.exists():
            continue

        with open(p1c_path) as f:
            p1c = json.load(f)
        with open(combined_path) as f:
            combined = json.load(f)

        for field in EASY_FIELDS:
            val = p1c.get("easy_fields", {}).get(field)
            combined["fields"][field] = {
                "value": val,
                "status": "EASY" if val is not None else "ABSENT",
                "confidence": 1.0,
                "evidence_quote": None,
                "source": "phase1_claude",
            }

        with open(combined_path, "w") as f:
            json.dump(combined, f, indent=2, ensure_ascii=False)
        updated += 1

    print(f"  Updated {updated}/103 combined files")

    # ── Validation ──
    print(f"\n{'='*70}")
    print(f"VALIDATION")
    print(f"{'='*70}")

    # Check 30 fields
    issues = 0
    for ds_id in all_ds:
        cp = COMBINED_DIR / f"{ds_id}.json"
        if cp.exists():
            with open(cp) as f:
                c = json.load(f)
            if len(c.get("fields", {})) != 30:
                issues += 1
    print(f"  30-field check: {len(all_ds) - issues}/{len(all_ds)} pass")

    # Before/after comparison
    print(f"\n  BEFORE (Gemini Flash) vs AFTER (Claude) easy field agreement with single-pass:")
    print(f"  {'Field':<20} {'Gemini→SP':>10} {'Claude→SP':>10} {'Improvement':>12}")
    print(f"  {'-'*55}")

    # Load old Phase 1 (Gemini) for comparison
    PHASE1_DIR = ROOT / "data" / "agentic" / "phase1"

    field_old = defaultdict(lambda: {"agree": 0, "total": 0})
    field_new = defaultdict(lambda: {"agree": 0, "total": 0})
    field_nn = defaultdict(lambda: {"claude_sp": 0, "agentic": 0})

    for ds_id in all_ds:
        claude_path = PROCESSED / ds_id / "full_pdf_metadata_result.json"
        p1_old_path = PHASE1_DIR / f"{ds_id}.json"
        p1c_path = PHASE1C_DIR / f"{ds_id}.json"

        if not claude_path.exists():
            continue

        with open(claude_path) as f:
            claude_sp = json.load(f)

        # Old (Gemini)
        if p1_old_path.exists():
            with open(p1_old_path) as f:
                p1_old = json.load(f)
            for field in EASY_FIELDS:
                cv = str(claude_sp.get(field, "") or "").strip().lower()[:30]
                ov = str(p1_old.get("easy_fields", {}).get(field, "") or "").strip().lower()[:30]
                field_old[field]["total"] += 1
                if cv == ov or (not cv and not ov):
                    field_old[field]["agree"] += 1

        # New (Claude)
        if p1c_path.exists():
            with open(p1c_path) as f:
                p1c = json.load(f)
            for field in EASY_FIELDS:
                cv = str(claude_sp.get(field, "") or "").strip().lower()[:30]
                nv = str(p1c.get("easy_fields", {}).get(field, "") or "").strip().lower()[:30]
                field_new[field]["total"] += 1
                if cv == nv or (not cv and not ov):
                    field_new[field]["agree"] += 1

                # Non-null counts
                if claude_sp.get(field) is not None and str(claude_sp.get(field, "")).strip():
                    field_nn[field]["claude_sp"] += 1
                if p1c.get("easy_fields", {}).get(field) is not None and str(p1c.get("easy_fields", {}).get(field, "")).strip():
                    field_nn[field]["agentic"] += 1

    for field in EASY_FIELDS:
        old_pct = field_old[field]["agree"] / max(field_old[field]["total"], 1) * 100
        new_pct = field_new[field]["agree"] / max(field_new[field]["total"], 1) * 100
        diff = new_pct - old_pct
        print(f"  {field:<20} {old_pct:>9.0f}% {new_pct:>9.0f}% {diff:>+11.0f}pp")

    # Full 30-field comparison
    print(f"\n{'='*70}")
    print(f"FULL 30-FIELD COMPARISON: Updated Agentic vs Claude Single-Pass")
    print(f"{'='*70}")

    ALL_30 = EASY_FIELDS + [
        "rai:dataCollection", "rai:dataCollectionType", "rai:dataCollectionTimeframe",
        "rai:dataCollectionRawData", "rai:dataCollectionMissingData",
        "rai:dataAnnotationProtocol", "rai:dataAnnotationPlatform",
        "rai:dataAnnotationAnalysis", "rai:annotationsPerItem",
        "rai:annotatorDemographics", "rai:machineAnnotationTools",
        "rai:dataBiases", "rai:dataLimitations", "rai:dataSocialImpact",
        "rai:personalSensitiveInformation", "rai:dataUseCases",
        "rai:dataImputationProtocol", "rai:dataManipulationProtocol",
        "rai:dataPreprocessingProtocol", "rai:dataReleaseMaintenancePlan",
    ]

    print(f"\n{'Field':<35} {'ClaudeSP':>8} {'Agentic':>8} {'Agree':>6} {'AG+':>4} {'CL+':>4}")
    print("-" * 70)

    for field in ALL_30:
        cl_nn = 0; ag_nn = 0; agree = 0; ag_only = 0; cl_only = 0; total = 0

        for ds_id in all_ds:
            cp = COMBINED_DIR / f"{ds_id}.json"
            claude_path = PROCESSED / ds_id / "full_pdf_metadata_result.json"
            if not cp.exists() or not claude_path.exists(): continue

            with open(cp) as f:
                ag = json.load(f)
            with open(claude_path) as f:
                claude = json.load(f)

            ag_val = ag.get("fields", {}).get(field, {}).get("value")
            cl_val = claude.get(field)
            ag_has = ag_val is not None and str(ag_val).strip() not in ("", "null", "None")
            cl_has = cl_val is not None and str(cl_val).strip() not in ("", "null", "None")

            total += 1
            if cl_has: cl_nn += 1
            if ag_has: ag_nn += 1
            if ag_has == cl_has: agree += 1
            if ag_has and not cl_has: ag_only += 1
            if cl_has and not ag_has: cl_only += 1

        agree_pct = agree / max(total, 1) * 100
        marker = " **" if abs(ag_nn - cl_nn) > 15 else ""
        print(f"{field:<35} {cl_nn:>8} {ag_nn:>8} {agree_pct:>5.0f}% {ag_only:>4} {cl_only:>4}{marker}")

    # Updated total cost
    print(f"\n{'='*70}")
    print(f"UPDATED PIPELINE COST")
    print(f"{'='*70}")
    print(f"  Phase 0 (local):              $0.00")
    print(f"  Phase 1 Gemini (triage only):  $0.27")
    print(f"  Phase 1 Claude (easy fields):  ${cost:.2f}")
    print(f"  Phase 2 (local):              $0.00")
    print(f"  Phase 3 Claude (hard fields):  $7.47")
    total_cost = 0.27 + cost + 7.47
    print(f"  TOTAL:                         ${total_cost:.2f}")
    print(f"  vs single-pass Claude:         $5.80")
    print(f"  Overhead:                      ${total_cost - 5.80:.2f}")


if __name__ == "__main__":
    main()
