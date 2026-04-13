#!/usr/bin/env python3
"""
Agentic Pipeline:
- Part 1: Retry 9 failed Phase 1 papers
- Part 2: Phase 2 LOCATE (evidence retrieval + null classification)
  Pure text processing from Phase 0/1 outputs. No API calls.
"""

import json
import os
import re
import sys
import time
from pathlib import Path
from collections import Counter, defaultdict

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

PHASE0_DIR = ROOT / "data" / "agentic" / "phase0"
PHASE1_DIR = ROOT / "data" / "agentic" / "phase1"
PHASE2_DIR = ROOT / "data" / "agentic" / "phase2"
PHASE2_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED = ROOT / "data" / "processed"

DUPES = {"CIFAR", "FLORES", "MLS", "MMLU", "MMMU", "MSCOCO", "MathVista", "Visual Genome"}

GROUPS = {
    "G3_collection": ["rai:dataCollection", "rai:dataCollectionType", "rai:dataCollectionTimeframe",
                      "rai:dataCollectionRawData", "rai:dataCollectionMissingData"],
    "G4_annotation": ["rai:dataAnnotationProtocol", "rai:dataAnnotationPlatform",
                      "rai:dataAnnotationAnalysis", "rai:annotationsPerItem",
                      "rai:annotatorDemographics", "rai:machineAnnotationTools"],
    "G5_rai": ["rai:dataBiases", "rai:dataLimitations", "rai:dataSocialImpact",
               "rai:personalSensitiveInformation", "rai:dataUseCases"],
    "G6_processing": ["rai:dataImputationProtocol", "rai:dataManipulationProtocol",
                      "rai:dataPreprocessingProtocol", "rai:dataReleaseMaintenancePlan"],
}

# Map group fields to Phase 0 keyword field names
GROUP_KW_FIELDS = {}
for g, fields in GROUPS.items():
    GROUP_KW_FIELDS[g] = fields


# ═══════════════════════════════════════════════════════════════
# PART 1: RETRY FAILED PHASE 1
# ═══════════════════════════════════════════════════════════════

def retry_phase1():
    """Retry the 9 missing Phase 1 papers."""
    sys.path.insert(0, str(ROOT / "scripts"))
    from agentic_phase1 import process_paper
    P1DIR = PHASE1_DIR

    all_ds = sorted(
        p.parent.name for p in PROCESSED.glob("*/full_pdf_metadata_result.json")
        if p.parent.name not in DUPES
    )
    existing = set(p.stem for p in P1DIR.glob("*.json"))
    missing = [ds for ds in all_ds if ds not in existing]

    if not missing:
        print("Phase 1: all 103 papers already complete")
        return

    print(f"\n{'='*70}")
    print(f"PART 1: RETRY {len(missing)} FAILED PHASE 1 PAPERS")
    print(f"{'='*70}")

    for i, ds_id in enumerate(missing):
        print(f"  [{i+1}/{len(missing)}] {ds_id}...", end=" ", flush=True)
        for attempt in range(3):
            try:
                result, err = process_paper(ds_id, is_dev=False)
                if result is None:
                    print(f"SKIP ({err})")
                    break
                out_path = P1DIR / f"{ds_id}.json"
                with open(out_path, "w") as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)
                print(f"OK ({result['usage']['input']}in/{result['usage']['output']}out)")
                break
            except Exception as e:
                if attempt < 2:
                    wait = 10 * (2 ** attempt)
                    print(f"RETRY({attempt+1})...", end=" ", flush=True)
                    time.sleep(wait)
                else:
                    print(f"FAIL ({str(e)[:50]})")
        time.sleep(5)  # 5-second delay between calls


def validate_phase1():
    """Validate all 103 Phase 1 outputs."""
    print(f"\n{'='*70}")
    print("PHASE 1 VALIDATION")
    print(f"{'='*70}")

    all_ds = sorted(
        p.parent.name for p in PROCESSED.glob("*/full_pdf_metadata_result.json")
        if p.parent.name not in DUPES
    )

    valid = 0
    issues = []

    for ds_id in all_ds:
        p1_path = PHASE1_DIR / f"{ds_id}.json"
        if not p1_path.exists():
            issues.append((ds_id, "MISSING Phase 1 JSON"))
            continue

        with open(p1_path) as f:
            p1 = json.load(f)

        # Check easy_fields
        ef = p1.get("easy_fields", {})
        expected_ef = {"name", "creator", "publisher", "datePublished", "url",
                       "citeAs", "license", "isLiveDataset", "description", "inLanguage"}
        missing_ef = expected_ef - set(ef.keys())
        if missing_ef:
            issues.append((ds_id, f"Missing easy fields: {missing_ef}"))
            continue

        # Check triage
        triage = p1.get("triage", {})
        for g in GROUPS:
            if g not in triage:
                issues.append((ds_id, f"Missing triage group: {g}"))
                continue
            t = triage[g]
            if t.get("presence") not in ("likely", "unlikely"):
                issues.append((ds_id, f"{g}: invalid presence '{t.get('presence')}'"))
            conf = t.get("confidence", -1)
            if not (0.0 <= conf <= 1.0):
                issues.append((ds_id, f"{g}: confidence {conf} out of range"))

        # Compare against Claude for nulls
        claude_path = PROCESSED / ds_id / "full_pdf_metadata_result.json"
        if claude_path.exists():
            with open(claude_path) as f:
                claude = json.load(f)
            for field in expected_ef:
                cv = claude.get(field)
                ev = ef.get(field)
                if cv and not ev:
                    pass  # Claude had value, Phase 1 null — note but don't block

        valid += 1

    print(f"\n  Phase 1 complete: {valid}/103 valid, {len(issues)} issues")
    if issues:
        for ds_id, issue in issues[:10]:
            print(f"    {ds_id}: {issue}")

    return valid, issues


# ═══════════════════════════════════════════════════════════════
# PART 2: PHASE 2 — LOCATE
# ═══════════════════════════════════════════════════════════════

def retrieve_chunks(phase0_data, group, triage_sections, max_chunks=8):
    """Retrieve relevant chunks for a field group."""
    chunks = phase0_data.get("chunks", [])
    kw_hits = phase0_data.get("keyword_hits", {})

    # Get keyword list for this group's fields
    group_keywords = set()
    for field in GROUP_KW_FIELDS[group]:
        for kw in kw_hits.get(field, {}).get("keywords_found", []):
            group_keywords.add(kw.lower())

    # Score each chunk by keyword overlap
    scored = []
    for chunk in chunks:
        text_lower = chunk["text"].lower()
        score = sum(1 for kw in group_keywords if kw in text_lower)
        scored.append((score, chunk))

    # Take top 5 by keyword overlap
    scored.sort(key=lambda x: -x[0])
    top_kw = [c for s, c in scored[:5] if s > 0]

    # Take chunks from triage-identified sections
    section_chunks = []
    triage_sections_lower = [s.lower() for s in (triage_sections or [])]
    for chunk in chunks:
        chunk_section = chunk.get("section", "").lower()
        for ts in triage_sections_lower:
            if ts in chunk_section or chunk_section in ts:
                section_chunks.append(chunk)
                break

    # Merge and deduplicate
    seen_indices = set()
    merged = []
    for chunk in top_kw + section_chunks:
        idx = chunk.get("chunk_index", id(chunk))
        if idx not in seen_indices:
            seen_indices.add(idx)
            merged.append({
                "text": chunk["text"],
                "section": chunk.get("section", ""),
                "chunk_index": chunk.get("chunk_index", -1),
            })
        if len(merged) >= max_chunks:
            break

    return merged


def classify_group(group, phase0_data, phase1_data):
    """Classify a field group as PRESENT, IMPLICIT, or ABSENT."""
    triage = phase1_data.get("triage", {}).get(group, {})
    triage_presence = triage.get("presence", "unknown")
    triage_confidence = triage.get("confidence", 0.5)
    triage_sections = triage.get("sections", [])

    # Phase 0 keyword signals
    kw_hits = phase0_data.get("keyword_hits", {})
    total_kw_hits = 0
    keywords_found = []
    for field in GROUP_KW_FIELDS[group]:
        field_kw = kw_hits.get(field, {})
        total_kw_hits += field_kw.get("total_hits", 0)
        keywords_found.extend(field_kw.get("keywords_found", []))
    keywords_found = sorted(set(keywords_found))

    # Retrieve chunks
    retrieved = retrieve_chunks(phase0_data, group, triage_sections)

    # Assess top chunk relevance
    if retrieved:
        top_text = retrieved[0]["text"].lower()
        relevance_score = sum(1 for kw in keywords_found if kw.lower() in top_text)
        top_relevance = "high" if relevance_score >= 3 else ("medium" if relevance_score >= 1 else "low")
    else:
        top_relevance = "none"

    # Classification logic — signal combination, no hardcoded thresholds
    if triage_presence == "likely" and total_kw_hits > 0 and len(retrieved) > 0:
        classification = "PRESENT"
        reasoning = f"Triage says likely (conf={triage_confidence}), {total_kw_hits} keyword hits, {len(retrieved)} chunks retrieved"
    elif triage_presence == "unlikely" and total_kw_hits == 0 and len(retrieved) == 0:
        classification = "ABSENT"
        reasoning = f"Triage says unlikely (conf={triage_confidence}), 0 keyword hits, 0 chunks"
    elif triage_presence == "unlikely" and total_kw_hits == 0:
        classification = "ABSENT"
        reasoning = f"Triage says unlikely and no keywords found, {len(retrieved)} chunks from sections"
    elif triage_presence == "likely" and total_kw_hits == 0:
        classification = "IMPLICIT"
        reasoning = f"Triage says likely but 0 keyword hits — may be implicit mention"
    elif triage_presence == "unlikely" and total_kw_hits > 0:
        classification = "IMPLICIT"
        reasoning = f"Triage says unlikely but {total_kw_hits} keyword hits found — may be false positive or implicit"
    else:
        classification = "IMPLICIT"
        reasoning = f"Mixed signals: triage={triage_presence}, keywords={total_kw_hits}, chunks={len(retrieved)}"

    return {
        "group": group,
        "null_signals": {
            "triage_presence": triage_presence,
            "triage_confidence": triage_confidence,
            "keyword_hits": total_kw_hits,
            "keywords_found": keywords_found[:10],
            "chunks_retrieved": len(retrieved),
            "top_chunk_relevance": top_relevance,
        },
        "classification": classification,
        "reasoning": reasoning,
        "retrieved_chunks": retrieved if classification != "ABSENT" else [],
    }


def process_phase2(ds_id):
    """Process one paper through Phase 2."""
    p0_path = PHASE0_DIR / f"{ds_id}.json"
    p1_path = PHASE1_DIR / f"{ds_id}.json"

    if not p0_path.exists() or not p1_path.exists():
        return None

    with open(p0_path) as f:
        p0 = json.load(f)
    with open(p1_path) as f:
        p1 = json.load(f)

    groups = {}
    for g in GROUPS:
        groups[g] = classify_group(g, p0, p1)

    return {
        "dataset_id": ds_id,
        "groups": groups,
    }


# ═══════════════════════════════════════════════════════════════
# VALIDATION LAYERS
# ═══════════════════════════════════════════════════════════════

def validate_layer1(all_ds):
    """Layer 1: Structural validation."""
    print(f"\n  Layer 1: Structural validation...")
    issues = []
    for ds_id in all_ds:
        p2_path = PHASE2_DIR / f"{ds_id}.json"
        if not p2_path.exists():
            issues.append((ds_id, "MISSING Phase 2 JSON"))
            continue
        with open(p2_path) as f:
            p2 = json.load(f)
        groups = p2.get("groups", {})
        for g in GROUPS:
            if g not in groups:
                issues.append((ds_id, f"Missing group {g}"))
                continue
            entry = groups[g]
            if entry["classification"] not in ("PRESENT", "IMPLICIT", "ABSENT"):
                issues.append((ds_id, f"{g}: invalid classification '{entry['classification']}'"))
            ns = entry.get("null_signals", {})
            for key in ["triage_presence", "triage_confidence", "keyword_hits",
                        "keywords_found", "chunks_retrieved", "top_chunk_relevance"]:
                if key not in ns:
                    issues.append((ds_id, f"{g}: missing null_signals.{key}"))
            if entry["classification"] == "ABSENT" and entry.get("retrieved_chunks"):
                issues.append((ds_id, f"{g}: ABSENT but has retrieved chunks"))
            if entry["classification"] == "PRESENT" and not entry.get("retrieved_chunks"):
                issues.append((ds_id, f"{g}: PRESENT but no retrieved chunks"))

    print(f"    {len(all_ds) - len(issues)}/{len(all_ds)} pass, {len(issues)} issues")
    for ds, issue in issues[:5]:
        print(f"      {ds}: {issue}")
    return issues


def validate_layer2(all_ds):
    """Layer 2: Consistency with Phase 0/1."""
    print(f"\n  Layer 2: Consistency validation...")
    flags = []
    for ds_id in all_ds:
        p1_path = PHASE1_DIR / f"{ds_id}.json"
        p2_path = PHASE2_DIR / f"{ds_id}.json"
        p0_path = PHASE0_DIR / f"{ds_id}.json"
        if not all(p.exists() for p in [p1_path, p2_path, p0_path]):
            continue

        with open(p1_path) as f: p1 = json.load(f)
        with open(p2_path) as f: p2 = json.load(f)
        with open(p0_path) as f: p0 = json.load(f)

        for g in GROUPS:
            t_pres = p1.get("triage", {}).get(g, {}).get("presence", "?")
            p2_cls = p2.get("groups", {}).get(g, {}).get("classification", "?")

            kw_hits = sum(
                len(p0.get("keyword_hits", {}).get(f, {}).get("keywords_found", []))
                for f in GROUP_KW_FIELDS[g]
            )

            # Phase 1 likely but Phase 2 ABSENT
            if t_pres == "likely" and p2_cls == "ABSENT":
                flags.append((ds_id, g, "P1=likely but P2=ABSENT"))
            # Phase 0 keywords but Phase 2 ABSENT (potential false positive)
            if kw_hits > 0 and p2_cls == "ABSENT":
                flags.append((ds_id, g, f"P0 has {kw_hits} keywords but P2=ABSENT"))
            # No signals at all but PRESENT
            if kw_hits == 0 and t_pres == "unlikely" and p2_cls == "PRESENT":
                flags.append((ds_id, g, "ERROR: no signals but P2=PRESENT"))

    consistent = len(all_ds) - len(set(ds for ds, _, _ in flags))
    print(f"    Consistency: {consistent}/{len(all_ds)} fully consistent, {len(flags)} flags")
    for ds, g, msg in flags[:5]:
        print(f"      {ds}/{g}: {msg}")
    return flags


def validate_layer3(dev_ids):
    """Layer 3: Ground truth validation (dev papers only)."""
    print(f"\n  Layer 3: Ground truth validation (dev, n={len(dev_ids)})...")
    cm = defaultdict(lambda: {"TP": 0, "TN": 0, "FP": 0, "FN": 0})
    misses = []

    for ds_id in dev_ids:
        p2_path = PHASE2_DIR / f"{ds_id}.json"
        claude_path = PROCESSED / ds_id / "full_pdf_metadata_result.json"
        if not p2_path.exists() or not claude_path.exists():
            continue

        with open(p2_path) as f: p2 = json.load(f)
        with open(claude_path) as f: claude = json.load(f)

        for g, fields in GROUPS.items():
            p2_cls = p2.get("groups", {}).get(g, {}).get("classification", "?")
            predicted_present = p2_cls in ("PRESENT", "IMPLICIT")

            actual_present = any(
                claude.get(f) is not None and str(claude.get(f, "")).strip()
                for f in fields
            )

            if predicted_present and actual_present: cm[g]["TP"] += 1
            elif not predicted_present and not actual_present: cm[g]["TN"] += 1
            elif predicted_present and not actual_present: cm[g]["FP"] += 1
            elif not predicted_present and actual_present:
                cm[g]["FN"] += 1
                misses.append((ds_id, g))

    print(f"\n    {'Group':<20} {'TP':>4} {'TN':>4} {'FP':>4} {'FN':>4} {'Prec':>6} {'Rec':>6}")
    print(f"    {'-'*50}")
    for g in GROUPS:
        c = cm[g]
        prec = c["TP"] / max(c["TP"] + c["FP"], 1) * 100
        rec = c["TP"] / max(c["TP"] + c["FN"], 1) * 100
        print(f"    {g:<20} {c['TP']:>4} {c['TN']:>4} {c['FP']:>4} {c['FN']:>4} {prec:>5.0f}% {rec:>5.0f}%")

    if misses:
        print(f"\n    MISSES ({len(misses)} — Claude had values but we said ABSENT):")
        for ds, g in misses:
            print(f"      {ds}/{g}")
    else:
        print(f"\n    No misses — all Claude non-null groups captured")

    return cm, misses


def validate_layer4(dev_ids):
    """Layer 4: Chunk quality (3 papers, detailed)."""
    print(f"\n  Layer 4: Chunk quality inspection (3 papers)...")

    # Pick 1 short, 1 medium, 1 long from dev
    samples = []
    for ds_id in dev_ids:
        p0_path = PHASE0_DIR / f"{ds_id}.json"
        if not p0_path.exists(): continue
        with open(p0_path) as f:
            p0 = json.load(f)
        tokens = p0["paper_stats"]["total_tokens"]
        samples.append((ds_id, tokens))

    samples.sort(key=lambda x: x[1])
    picks = [samples[0], samples[len(samples)//2], samples[-1]]

    for ds_id, tokens in picks:
        p2_path = PHASE2_DIR / f"{ds_id}.json"
        if not p2_path.exists(): continue
        with open(p2_path) as f:
            p2 = json.load(f)

        print(f"\n    {ds_id} ({tokens:,} tokens):")
        for g in GROUPS:
            entry = p2["groups"].get(g, {})
            cls = entry.get("classification", "?")
            chunks = entry.get("retrieved_chunks", [])
            if cls == "PRESENT" and chunks:
                print(f"      {g} [{cls}]: {len(chunks)} chunks")
                for j, chunk in enumerate(chunks[:2]):
                    text_preview = chunk["text"][:150].replace("\n", " ")
                    print(f"        chunk {j}: [{chunk.get('section','')}] {text_preview}...")
            else:
                print(f"      {g} [{cls}]: {len(chunks)} chunks")


def validate_layer5(all_ds):
    """Layer 5: Statistics validation."""
    print(f"\n  Layer 5: Statistics validation...")
    dist = defaultdict(Counter)

    for ds_id in all_ds:
        p2_path = PHASE2_DIR / f"{ds_id}.json"
        if not p2_path.exists(): continue
        with open(p2_path) as f:
            p2 = json.load(f)
        for g in GROUPS:
            cls = p2.get("groups", {}).get(g, {}).get("classification", "?")
            dist[g][cls] += 1

    print(f"\n    {'Group':<20} {'PRESENT':>8} {'IMPLICIT':>9} {'ABSENT':>7}")
    print(f"    {'-'*48}")
    total_present = 0
    total_absent = 0
    suspicious = []
    for g in GROUPS:
        p = dist[g]["PRESENT"]
        i = dist[g]["IMPLICIT"]
        a = dist[g]["ABSENT"]
        total_present += p + i
        total_absent += a
        print(f"    {g:<20} {p:>8} {i:>9} {a:>7}")
        if a == 0:
            suspicious.append(f"{g}: 0 ABSENT (suspicious)")
        if p + i == 0:
            suspicious.append(f"{g}: 0 PRESENT/IMPLICIT (suspicious)")

    print(f"\n    Total PRESENT+IMPLICIT: {total_present}, ABSENT: {total_absent}")
    if total_present > total_absent:
        print(f"    CHECK: PRESENT > ABSENT — expected for most ML papers")
    if suspicious:
        print(f"    FLAGS:")
        for s in suspicious:
            print(f"      {s}")

    return dist


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    all_ds = sorted(
        p.parent.name for p in PROCESSED.glob("*/full_pdf_metadata_result.json")
        if p.parent.name not in DUPES
    )

    # Load dev/test split
    split_path = ROOT / "data" / "agentic" / "dev_test_split.json"
    with open(split_path) as f:
        split = json.load(f)
    dev_ids = split["dev"]
    test_ids = split["test"]

    # ── Part 1: Retry Phase 1 ──
    retry_phase1()
    p1_valid, p1_issues = validate_phase1()

    if p1_valid < 103:
        print(f"\n  WARNING: Only {p1_valid}/103 Phase 1 papers valid. Proceeding with available papers.")

    # ── Part 2: Phase 2 on DEV papers first ──
    print(f"\n{'='*70}")
    print(f"PART 2: PHASE 2 LOCATE — DEV SET ({len(dev_ids)} papers)")
    print(f"{'='*70}")

    for i, ds_id in enumerate(dev_ids):
        result = process_phase2(ds_id)
        if result is None:
            print(f"  [{i+1}/{len(dev_ids)}] {ds_id} — SKIP (missing P0/P1)")
            continue
        out_path = PHASE2_DIR / f"{ds_id}.json"
        with open(out_path, "w") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        groups_str = " ".join(f"{g}={result['groups'][g]['classification'][0]}" for g in GROUPS)
        print(f"  [{i+1}/{len(dev_ids)}] {ds_id} — {groups_str}")

    # ── Validation on DEV ──
    print(f"\n{'='*70}")
    print(f"VALIDATION — DEV SET")
    print(f"{'='*70}")

    validate_layer1(dev_ids)
    validate_layer2(dev_ids)
    validate_layer3(dev_ids)
    validate_layer4(dev_ids)
    validate_layer5(dev_ids)

    # ── Phase 2 on TEST papers ──
    print(f"\n{'='*70}")
    print(f"PHASE 2 LOCATE — TEST SET ({len(test_ids)} papers)")
    print(f"{'='*70}")

    for i, ds_id in enumerate(test_ids):
        result = process_phase2(ds_id)
        if result is None:
            continue
        out_path = PHASE2_DIR / f"{ds_id}.json"
        with open(out_path, "w") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        if (i + 1) % 20 == 0:
            print(f"  [{i+1}/{len(test_ids)}] processed")

    print(f"  [{len(test_ids)}/{len(test_ids)}] done")

    # ── Full validation ──
    print(f"\n{'='*70}")
    print(f"FULL VALIDATION — ALL 103 PAPERS")
    print(f"{'='*70}")

    l1 = validate_layer1(all_ds)
    l2 = validate_layer2(all_ds)
    cm, misses = validate_layer3(dev_ids)
    dist = validate_layer5(all_ds)

    # ── Summary ──
    total_present = sum(dist[g]["PRESENT"] + dist[g]["IMPLICIT"] for g in GROUPS)
    total_absent = sum(dist[g]["ABSENT"] for g in GROUPS)
    total_groups = len(all_ds) * 4
    avg_chunks = 0
    chunk_count = 0
    for ds_id in all_ds:
        p2_path = PHASE2_DIR / f"{ds_id}.json"
        if not p2_path.exists(): continue
        with open(p2_path) as f:
            p2 = json.load(f)
        for g in GROUPS:
            entry = p2.get("groups", {}).get(g, {})
            if entry.get("classification") in ("PRESENT", "IMPLICIT"):
                avg_chunks += len(entry.get("retrieved_chunks", []))
                chunk_count += 1
    avg_chunks = avg_chunks / max(chunk_count, 1)

    print(f"\n{'='*70}")
    print(f"PHASE 2 SUMMARY")
    print(f"{'='*70}")
    print(f"  Papers processed: {len(list(PHASE2_DIR.glob('*.json')))}/103")
    print(f"  Total group evaluations: {total_groups}")
    print(f"  PRESENT+IMPLICIT: {total_present} ({total_present/total_groups*100:.0f}%)")
    print(f"  ABSENT: {total_absent} ({total_absent/total_groups*100:.0f}%)")
    print(f"  Phase 3 savings: {total_absent} group-paper combinations skipped")
    print(f"  Avg chunks per PRESENT group: {avg_chunks:.1f}")
    print(f"  Structural issues: {len(l1)}")
    print(f"  Consistency flags: {len(l2)}")
    print(f"  Dev misses: {len(misses)}")

    summary = {
        "phase": 2,
        "papers_processed": len(list(PHASE2_DIR.glob("*.json"))),
        "distribution": {g: dict(dist[g]) for g in GROUPS},
        "total_present_implicit": total_present,
        "total_absent": total_absent,
        "phase3_savings": total_absent,
        "avg_chunks_per_present": round(avg_chunks, 1),
        "structural_issues": len(l1),
        "consistency_flags": len(l2),
        "dev_misses": len(misses),
        "dev_confusion_matrix": {g: dict(cm[g]) for g in GROUPS},
    }
    summary_path = ROOT / "results" / "agentic_phase2_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\n  Summary: {summary_path}")


if __name__ == "__main__":
    main()
