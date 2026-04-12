#!/usr/bin/env python3
"""
Agentic Pipeline Phase 1: Dev/Test Split + Plan + Triage + Easy Field Extraction.

Step 1: Select 15 dev papers (stratified by length + RAI keyword density)
Step 2: Run Phase 1 on 15 dev papers
Step 3: Validate dev results against Claude baseline
Step 4: If good, run on all 103
Step 5: Summary
"""

import json
import os
import re
import time
from pathlib import Path
from collections import Counter, defaultdict

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

PHASE0_DIR = ROOT / "data" / "agentic" / "phase0"
PHASE1_DIR = ROOT / "data" / "agentic" / "phase1"
PHASE1_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED = ROOT / "data" / "processed"

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = "gemini-2.5-flash"
ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"

DUPES = {"CIFAR", "FLORES", "MLS", "MMLU", "MMMU", "MSCOCO", "MathVista", "Visual Genome"}

EASY_FIELDS = ["name", "creator", "publisher", "datePublished", "url",
               "citeAs", "license", "isLiveDataset", "description", "inLanguage"]

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

# ═══════════════════════════════════════════════════════════════
# STEP 1: DEV/TEST SPLIT
# ═══════════════════════════════════════════════════════════════

def select_dev_papers():
    """Select 15 dev papers stratified by length and RAI keyword density."""
    all_ds = sorted(
        p.parent.name for p in PROCESSED.glob("*/full_pdf_metadata_result.json")
        if p.parent.name not in DUPES
    )

    paper_stats = []
    for ds_id in all_ds:
        p0 = PHASE0_DIR / f"{ds_id}.json"
        if not p0.exists():
            continue
        with open(p0) as f:
            data = json.load(f)

        stats = data["paper_stats"]
        kw = data["keyword_hits"]

        # RAI keyword density = sum of hits across RAI fields
        rai_hits = sum(v.get("total_hits", 0) for k, v in kw.items() if k.startswith("rai:"))

        # Claude null count (proxy for information sparsity)
        claude_path = PROCESSED / ds_id / "full_pdf_metadata_result.json"
        nulls = 0
        if claude_path.exists():
            with open(claude_path) as f:
                claude = json.load(f)
            nulls = sum(1 for v in claude.values() if v is None)

        paper_stats.append({
            "ds_id": ds_id,
            "tokens": stats["total_tokens"],
            "length_cat": stats["paper_length_category"],
            "rai_hits": rai_hits,
            "nulls": nulls,
        })

    # Stratify by length
    short_medium = [p for p in paper_stats if p["tokens"] < 15000]
    medium = [p for p in paper_stats if 15000 <= p["tokens"] < 25000]
    long_papers = [p for p in paper_stats if p["tokens"] >= 25000]

    def pick_diverse(pool, n):
        """Pick n papers maximizing diversity in RAI hits and nulls."""
        if len(pool) <= n:
            return pool
        # Sort by RAI hits, pick from both ends + middle
        pool.sort(key=lambda x: x["rai_hits"])
        result = []
        # Pick highest RAI, lowest RAI, highest nulls, lowest nulls, then fill
        indices = set()
        indices.add(0)  # lowest RAI
        indices.add(len(pool) - 1)  # highest RAI
        pool_by_nulls = sorted(range(len(pool)), key=lambda i: pool[i]["nulls"])
        indices.add(pool_by_nulls[-1])  # most nulls
        indices.add(pool_by_nulls[0])  # fewest nulls
        # Fill remaining evenly spaced
        step = max(1, len(pool) // n)
        for i in range(0, len(pool), step):
            indices.add(i)
            if len(indices) >= n:
                break
        # If still short, add from middle
        while len(indices) < n and len(indices) < len(pool):
            for i in range(len(pool)):
                if i not in indices:
                    indices.add(i)
                    break
        return [pool[i] for i in sorted(indices)[:n]]

    dev_papers = (
        pick_diverse(short_medium, 5) +
        pick_diverse(medium, 5) +
        pick_diverse(long_papers, 5)
    )

    dev_ids = [p["ds_id"] for p in dev_papers]
    test_ids = [p["ds_id"] for p in paper_stats if p["ds_id"] not in set(dev_ids)]

    split = {
        "dev": dev_ids,
        "test": test_ids,
        "selection_criteria": "stratified by length (5 short/medium + 5 medium + 5 long), "
                              "diversity maximized on RAI keyword density and Claude null count",
    }

    split_path = ROOT / "data" / "agentic" / "dev_test_split.json"
    with open(split_path, "w") as f:
        json.dump(split, f, indent=2)

    print(f"DEV/TEST SPLIT: {len(dev_ids)} dev, {len(test_ids)} test")
    print(f"Saved: {split_path}\n")
    print(f"{'Paper':<40} {'Tokens':>7} {'RAI hits':>9} {'Nulls':>6}")
    print("-" * 65)
    for p in dev_papers:
        print(f"{p['ds_id']:<40} {p['tokens']:>7,} {p['rai_hits']:>9} {p['nulls']:>6}")

    return dev_ids, test_ids


# ═══════════════════════════════════════════════════════════════
# STEP 2: PHASE 1 EXTRACTION
# ═══════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """You are a metadata extraction expert for ML dataset papers.
You will receive the full text of an academic paper describing an ML dataset, along with keyword analysis from a preprocessing step.

Output a JSON object with two parts:

PART A — "easy_fields": Extract these 10 fields. Use null if not stated in the paper.
- name: Dataset name
- creator: Dataset creator(s)/author(s)
- publisher: Publishing venue or organization
- datePublished: Release date (YYYY or YYYY-MM-DD)
- url: Dataset access URL
- citeAs: Citation format
- license: Distribution license (MIT, CC-BY, etc.)
- isLiveDataset: "Yes" if actively updated, "No" if static, null if not discussed
- description: Brief description (1-3 sentences)
- inLanguage: Content language(s) (ISO codes preferred)

PART B — "triage": For each of 4 field groups, assess whether the paper contains relevant information.
For each group output:
- presence: "likely" if the paper discusses this topic, "unlikely" if not
- sections: list of section names where this information appears
- confidence: 0.0 to 1.0
- reasoning: one sentence explaining your assessment

Groups:
- G3_collection: data collection methodology, collection type, timeframe, raw data source, missing data
- G4_annotation: annotation protocol, platform, quality analysis, annotations per item, annotator demographics, machine annotation tools
- G5_rai: biases, limitations, social impact, personal/sensitive information, intended use cases
- G6_processing: imputation protocol, manipulation protocol, preprocessing steps, release/maintenance plan

Return ONLY valid JSON. No markdown fences, no explanation outside the JSON."""


def build_user_prompt(paper_text, phase0_data):
    """Build user prompt with Phase 0 keyword context."""
    # Build keyword summary
    kw_lines = []
    kw_hits = phase0_data.get("keyword_hits", {})
    for field in sorted(kw_hits.keys()):
        info = kw_hits[field]
        if info.get("keywords_found"):
            kw_lines.append(f"  {field}: found [{', '.join(info['keywords_found'][:5])}] ({info['total_hits']} hits)")

    kw_context = "\n".join(kw_lines) if kw_lines else "  (no significant keyword matches)"

    return f"""Keyword analysis from preprocessing:
{kw_context}

Use the above as supplementary signal but make your own judgment based on the full paper text below.

PAPER TEXT:
{paper_text}

Extract the 10 easy fields and triage the 4 hard groups. Return JSON with "easy_fields" and "triage" keys."""


def call_gemini(prompt):
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "generationConfig": {"temperature": 0.0, "maxOutputTokens": 8192},
    }
    resp = requests.post(ENDPOINT, params={"key": API_KEY}, json=payload, timeout=180)
    if resp.status_code != 200:
        raise Exception(f"API {resp.status_code}: {resp.text[:200]}")
    data = resp.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    usage = data.get("usageMetadata", {})
    return text, {"input": usage.get("promptTokenCount", 0), "output": usage.get("candidatesTokenCount", 0)}


def parse_json(text):
    text = text.strip()
    if text.startswith("```json"): text = text[7:]
    elif text.startswith("```"): text = text[3:]
    if text.endswith("```"): text = text[:-3]
    return json.loads(text.strip())


def get_paper_text(ds_id):
    import fitz
    raw = ROOT / "data" / "raw"
    with open(ROOT / "data" / "paper_links.json") as f:
        pl = json.load(f)
    for name in [f"{ds_id}.pdf"]:
        p = raw / name
        if p.exists():
            doc = fitz.open(str(p)); text = "\n".join(pg.get_text() for pg in doc); doc.close(); return text
    url = pl.get(ds_id, "")
    m = re.search(r'(\d{4}\.\d{4,5})', url)
    if m:
        for sfx in ["", "v1", "v2", "v3", "v4", "v5"]:
            p = raw / f"{m.group(1)}{sfx}.pdf"
            if p.exists():
                doc = fitz.open(str(p)); text = "\n".join(pg.get_text() for pg in doc); doc.close(); return text
    return None


def validate_result(result):
    issues = []
    ef = result.get("easy_fields", {})
    missing_ef = set(EASY_FIELDS) - set(ef.keys())
    if missing_ef: issues.append(f"Missing easy fields: {missing_ef}")

    triage = result.get("triage", {})
    for g in GROUPS:
        if g not in triage:
            issues.append(f"Missing triage group: {g}")
        else:
            entry = triage[g]
            if entry.get("presence") not in ("likely", "unlikely"):
                issues.append(f"{g}: invalid presence '{entry.get('presence')}'")
            if "confidence" not in entry:
                issues.append(f"{g}: missing confidence")
    return len(issues) == 0, issues


def process_paper(ds_id, is_dev=False):
    """Process one paper through Phase 1."""
    paper_text = get_paper_text(ds_id)
    if not paper_text:
        return None, "NO_TEXT"

    # Truncate very long papers
    if len(paper_text) > 500000:
        paper_text = paper_text[:500000]

    p0_path = PHASE0_DIR / f"{ds_id}.json"
    p0 = json.load(open(p0_path)) if p0_path.exists() else {"keyword_hits": {}}

    prompt = build_user_prompt(paper_text, p0)
    raw_resp, tokens = call_gemini(prompt)
    result = parse_json(raw_resp)

    # Ensure structure
    ef = result.setdefault("easy_fields", {})
    for f in EASY_FIELDS:
        ef.setdefault(f, None)

    triage = result.setdefault("triage", {})
    for g in GROUPS:
        triage.setdefault(g, {"presence": "unknown", "sections": [], "confidence": 0.5, "reasoning": ""})

    valid, issues = validate_result(result)

    output = {
        "dataset_id": ds_id,
        "split": "dev" if is_dev else "test",
        "valid": valid,
        "easy_fields": ef,
        "triage": triage,
        "usage": tokens,
        "issues": issues if issues else None,
    }
    return output, None


# ═══════════════════════════════════════════════════════════════
# STEP 3: VALIDATE AGAINST CLAUDE BASELINE
# ═══════════════════════════════════════════════════════════════

def evaluate_results(paper_ids, label=""):
    """Evaluate Phase 1 results against Claude baseline."""
    # Easy field agreement
    field_agree = defaultdict(lambda: {"exact": 0, "semantic": 0, "total": 0})
    # Triage confusion matrix
    triage_cm = defaultdict(lambda: {"TP": 0, "TN": 0, "FP": 0, "FN": 0})

    for ds_id in paper_ids:
        p1_path = PHASE1_DIR / f"{ds_id}.json"
        claude_path = PROCESSED / ds_id / "full_pdf_metadata_result.json"
        if not p1_path.exists() or not claude_path.exists():
            continue

        with open(p1_path) as f:
            p1 = json.load(f)
        with open(claude_path) as f:
            claude = json.load(f)

        ef = p1.get("easy_fields", {})

        # Easy field comparison
        for field in EASY_FIELDS:
            cv = claude.get(field)
            ev = ef.get(field)
            field_agree[field]["total"] += 1

            cv_str = str(cv or "").strip().lower()
            ev_str = str(ev or "").strip().lower()

            # Exact match (first 30 chars)
            if cv_str[:30] == ev_str[:30]:
                field_agree[field]["exact"] += 1

            # Semantic match (both null, or significant overlap)
            if (not cv_str and not ev_str):
                field_agree[field]["semantic"] += 1
            elif cv_str and ev_str:
                # Token overlap
                cv_tokens = set(cv_str.split()[:10])
                ev_tokens = set(ev_str.split()[:10])
                if cv_tokens and ev_tokens:
                    overlap = len(cv_tokens & ev_tokens) / max(len(cv_tokens), 1)
                    if overlap > 0.3:
                        field_agree[field]["semantic"] += 1

        # Triage evaluation
        triage = p1.get("triage", {})
        for group, fields in GROUPS.items():
            t = triage.get(group, {})
            predicted_present = t.get("presence") == "likely"

            # Ground truth: did Claude extract non-null for ANY field in this group?
            actual_present = any(
                claude.get(f) is not None and str(claude.get(f, "")).strip()
                for f in fields
            )

            if predicted_present and actual_present: triage_cm[group]["TP"] += 1
            elif not predicted_present and not actual_present: triage_cm[group]["TN"] += 1
            elif predicted_present and not actual_present: triage_cm[group]["FP"] += 1
            elif not predicted_present and actual_present: triage_cm[group]["FN"] += 1

    # Print
    print(f"\n  Easy field agreement ({label}, n={len(paper_ids)}):")
    print(f"  {'Field':<20} {'Exact':>8} {'Semantic':>10}")
    print(f"  {'-'*40}")
    for field in EASY_FIELDS:
        info = field_agree[field]
        t = max(info["total"], 1)
        print(f"  {field:<20} {info['exact']/t*100:>7.0f}% {info['semantic']/t*100:>9.0f}%")

    print(f"\n  Triage confusion matrix ({label}):")
    print(f"  {'Group':<20} {'TP':>5} {'TN':>5} {'FP':>5} {'FN':>5} {'Precision':>10} {'Recall':>8}")
    print(f"  {'-'*60}")
    for group in GROUPS:
        cm = triage_cm[group]
        prec = cm["TP"] / max(cm["TP"] + cm["FP"], 1) * 100
        rec = cm["TP"] / max(cm["TP"] + cm["FN"], 1) * 100
        print(f"  {group:<20} {cm['TP']:>5} {cm['TN']:>5} {cm['FP']:>5} {cm['FN']:>5} {prec:>9.0f}% {rec:>7.0f}%")

    return field_agree, triage_cm


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    # Step 1: Dev/Test split
    print("=" * 70)
    print("STEP 1: DEV/TEST SPLIT")
    print("=" * 70)

    split_path = ROOT / "data" / "agentic" / "dev_test_split.json"
    if split_path.exists():
        with open(split_path) as f:
            split = json.load(f)
        dev_ids = split["dev"]
        test_ids = split["test"]
        print(f"Loaded existing split: {len(dev_ids)} dev, {len(test_ids)} test")
    else:
        dev_ids, test_ids = select_dev_papers()

    # Step 2: Run on dev
    print(f"\n{'='*70}")
    print(f"STEP 2: PHASE 1 ON {len(dev_ids)} DEV PAPERS")
    print(f"{'='*70}")

    total_in = 0; total_out = 0; dev_ok = 0; dev_fail = 0

    for i, ds_id in enumerate(dev_ids):
        out_path = PHASE1_DIR / f"{ds_id}.json"
        if out_path.exists():
            print(f"  [{i+1}/{len(dev_ids)}] {ds_id} — SKIP (exists)")
            dev_ok += 1
            continue

        for attempt in range(3):
            try:
                result, err = process_paper(ds_id, is_dev=True)
                if result is None:
                    print(f"  [{i+1}/{len(dev_ids)}] {ds_id} — {err}")
                    dev_fail += 1
                    break

                with open(out_path, "w") as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)

                total_in += result["usage"]["input"]
                total_out += result["usage"]["output"]
                dev_ok += 1

                ef = result["easy_fields"]
                t = result["triage"]
                triage_str = " ".join(f"{g}={t[g]['presence'][0]}" for g in GROUPS)
                print(f"  [{i+1}/{len(dev_ids)}] {ds_id} — OK ({result['usage']['input']}in/{result['usage']['output']}out) name={ef.get('name','?')[:20]} {triage_str}")
                break

            except Exception as e:
                if attempt < 2:
                    wait = 10 * (2 ** attempt) if "429" in str(e) or "503" in str(e) else 3
                    print(f"  [{i+1}/{len(dev_ids)}] {ds_id} — RETRY in {wait}s ({str(e)[:50]})")
                    time.sleep(wait)
                else:
                    print(f"  [{i+1}/{len(dev_ids)}] {ds_id} — FAIL ({str(e)[:60]})")
                    dev_fail += 1

        time.sleep(1)

    print(f"\n  Dev results: {dev_ok} OK, {dev_fail} failed")

    # Step 3: Validate dev
    print(f"\n{'='*70}")
    print(f"STEP 3: VALIDATE DEV RESULTS")
    print(f"{'='*70}")

    dev_agree, dev_cm = evaluate_results(dev_ids, "DEV")

    # Check if dev looks good enough to proceed
    avg_exact = sum(v["exact"] / max(v["total"], 1) for v in dev_agree.values()) / len(EASY_FIELDS) * 100
    avg_prec = sum(dev_cm[g]["TP"] / max(dev_cm[g]["TP"] + dev_cm[g]["FP"], 1) for g in GROUPS) / len(GROUPS) * 100
    print(f"\n  Dev summary: avg exact agreement {avg_exact:.0f}%, avg triage precision {avg_prec:.0f}%")

    if avg_exact < 20:
        print(f"  WARNING: Very low agreement — check prompt quality before running on test set")

    # Step 4: Run on test set
    print(f"\n{'='*70}")
    print(f"STEP 4: PHASE 1 ON {len(test_ids)} TEST PAPERS")
    print(f"{'='*70}")

    test_ok = 0; test_fail = 0

    for i, ds_id in enumerate(test_ids):
        out_path = PHASE1_DIR / f"{ds_id}.json"
        if out_path.exists():
            test_ok += 1
            if (i + 1) % 20 == 0:
                print(f"  [{i+1}/{len(test_ids)}] {test_ok} OK (skipping existing)")
            continue

        for attempt in range(3):
            try:
                result, err = process_paper(ds_id, is_dev=False)
                if result is None:
                    test_fail += 1
                    break

                with open(out_path, "w") as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)

                total_in += result["usage"]["input"]
                total_out += result["usage"]["output"]
                test_ok += 1
                break

            except Exception as e:
                if attempt < 2:
                    wait = 10 * (2 ** attempt) if "429" in str(e) or "503" in str(e) else 3
                    time.sleep(wait)
                else:
                    print(f"  [{i+1}/{len(test_ids)}] {ds_id} — FAIL ({str(e)[:60]})")
                    test_fail += 1

        if (i + 1) % 20 == 0:
            print(f"  [{i+1}/{len(test_ids)}] {test_ok} OK, {test_fail} failed")
        time.sleep(0.5)

    print(f"  [{len(test_ids)}/{len(test_ids)}] {test_ok} OK, {test_fail} failed")

    # Step 5: Full evaluation
    print(f"\n{'='*70}")
    print(f"STEP 5: FULL EVALUATION")
    print(f"{'='*70}")

    print("\n  --- DEV SET ---")
    evaluate_results(dev_ids, "DEV")

    print("\n  --- TEST SET ---")
    test_agree, test_cm = evaluate_results(test_ids, "TEST")

    print("\n  --- ALL 103 ---")
    all_agree, all_cm = evaluate_results(dev_ids + test_ids, "ALL")

    # Triage distribution
    print(f"\n  Triage distribution (all papers):")
    triage_dist = defaultdict(Counter)
    for ds_id in dev_ids + test_ids:
        p1_path = PHASE1_DIR / f"{ds_id}.json"
        if not p1_path.exists(): continue
        with open(p1_path) as f:
            p1 = json.load(f)
        for g in GROUPS:
            pres = p1.get("triage", {}).get(g, {}).get("presence", "?")
            triage_dist[g][pres] += 1

    for g in GROUPS:
        print(f"    {g}: likely={triage_dist[g]['likely']}, unlikely={triage_dist[g]['unlikely']}")

    # Cost
    cost = total_in / 1e6 * 0.075 + total_out / 1e6 * 0.30
    print(f"\n  Total tokens: {total_in:,} in, {total_out:,} out")
    print(f"  Total cost: ${cost:.3f}")

    # Save summary
    summary = {
        "phase": 1,
        "model": MODEL,
        "dev_papers": len(dev_ids),
        "test_papers": len(test_ids),
        "dev_ok": dev_ok,
        "test_ok": test_ok,
        "total_input_tokens": total_in,
        "total_output_tokens": total_out,
        "cost_usd": round(cost, 3),
        "triage_distribution": {g: dict(c) for g, c in triage_dist.items()},
        "easy_field_agreement_all": {
            f: round(v["exact"] / max(v["total"], 1) * 100, 1)
            for f, v in all_agree.items()
        },
        "triage_precision_all": {
            g: round(all_cm[g]["TP"] / max(all_cm[g]["TP"] + all_cm[g]["FP"], 1) * 100, 1)
            for g in GROUPS
        },
        "triage_recall_all": {
            g: round(all_cm[g]["TP"] / max(all_cm[g]["TP"] + all_cm[g]["FN"], 1) * 100, 1)
            for g in GROUPS
        },
    }

    summary_path = ROOT / "results" / "agentic_phase1_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\n  Summary: {summary_path}")
    print(f"  Output: {PHASE1_DIR}")

    # Output count
    jsons = list(PHASE1_DIR.glob("*.json"))
    print(f"  Files: {len(jsons)}/103")


if __name__ == "__main__":
    main()
