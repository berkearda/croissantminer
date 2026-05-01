#!/usr/bin/env python3
"""CroissantMiner Agentic V2 pipeline.

Phases:
  0. PDF parse (PyPDF2 + canonical clean_text + UTF-8 sanitize).
  1. Load Gemini Flash triage (from data/agentic/phase1/<ds_id>.json).
  2. Full-context extraction that also asks for evidence quotes per field.
  2.5 Self-correction pass over fields that are null but triage says present.
  3. Cross-document enrichment (HuggingFace + Semantic Scholar) for gaps.
  4. Schema validation + confidence scoring.
  5. Write canonical output to data/extractions/agentic_v2_<backbone_slug>/.

Output schema (canonical):
  {"dataset_id", "model", "extraction" (flat 30 fields), "usage", "valid",
   "_meta": {provenance, pipeline="agentic_v2", extraction_details: {field:
             {confidence, status, source, evidence}}, paper_stats, ...}}

Usage:
  python scripts/agentic_v2.py --backbone sonnet-4-5
  python scripts/agentic_v2.py --backbone gpt-5.4 --dev-only
  python scripts/agentic_v2.py --backbone sonnet-4-5 --batch   # Anthropic only
"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

from _agentic_helpers import (
    ROOT,
    SYSTEM_PROMPT,
    CANONICAL_FIELDS,
    call_llm,
    estimate_cost,
    fill_canonical,
    get_paper_text,
    meta_block,
    normalize_field_names,
    output_dir_for,
    parse_json_response,
    resolve_backbone,
    strip_references,
)

load_dotenv(ROOT / ".env")

MAX_PAPER_CHARS = 200_000
MAX_TOKENS_EXTRACT = 16384  # was 8192; bumped to clear Gemini 3.x truncation failures (2026-04-30)
MAX_TOKENS_CORRECT = 8192   # was 4096; bumped proportionally
SCRIPT_NAME = "scripts/agentic_v2.py"

PHASE1_DIR = ROOT / "data" / "agentic" / "phase1"

with open(ROOT / "data" / "agentic" / "dev_test_split.json") as f:
    SPLIT = json.load(f)


# ── Field groups (used by triage + self-correction) ───────────────
EASY_FIELDS = [
    "name", "description", "url", "license", "creator",
    "publisher", "datePublished", "inLanguage", "citeAs", "isLiveDataset",
]
HARD_FIELDS = [
    "rai:dataCollection", "rai:dataCollectionType", "rai:dataCollectionMissingData",
    "rai:dataCollectionRawData", "rai:dataCollectionTimeframe",
    "rai:dataImputationProtocol", "rai:dataManipulationProtocol",
    "rai:dataPreprocessingProtocol", "rai:dataAnnotationProtocol",
    "rai:dataAnnotationPlatform", "rai:dataAnnotationAnalysis",
    "rai:annotationsPerItem", "rai:annotatorDemographics",
    "rai:machineAnnotationTools", "rai:dataReleaseMaintenancePlan",
    "rai:personalSensitiveInformation", "rai:dataSocialImpact",
    "rai:dataBiases", "rai:dataLimitations", "rai:dataUseCases",
]
ALL_FIELDS = EASY_FIELDS + HARD_FIELDS

TRIAGE_GROUPS = {
    "G3_collection": [
        "rai:dataCollection", "rai:dataCollectionType",
        "rai:dataCollectionMissingData", "rai:dataCollectionRawData",
        "rai:dataCollectionTimeframe",
    ],
    "G4_annotation": [
        "rai:dataAnnotationProtocol", "rai:dataAnnotationPlatform",
        "rai:dataAnnotationAnalysis", "rai:annotationsPerItem",
        "rai:annotatorDemographics", "rai:machineAnnotationTools",
    ],
    "G5_rai": [
        "rai:dataBiases", "rai:dataLimitations", "rai:dataSocialImpact",
        "rai:personalSensitiveInformation", "rai:dataUseCases",
        "rai:dataReleaseMaintenancePlan",
    ],
    "G6_processing": [
        "rai:dataImputationProtocol", "rai:dataManipulationProtocol",
        "rai:dataPreprocessingProtocol",
    ],
}


# ── V2-specific prompt (asks for {value, evidence} per field) ─────
USER_PROMPT_WITH_EVIDENCE = '''Extract metadata from the following academic paper by matching text to the field descriptions above.

For each non-null field, also provide a brief "evidence" quote: the key sentence(s) from the paper that support your extraction. This helps verify accuracy.

Your output must conform exactly to the following schema. For each field, provide "value" and "evidence":

SCHEMA:
{
  "name": {"value": "string", "evidence": "quote from paper"},
  "description": {"value": "string", "evidence": "quote from paper"},
  "url": {"value": "string", "evidence": "quote from paper"},
  "license": {"value": "string or null", "evidence": "quote or null"},
  "creator": {"value": "string", "evidence": "quote from paper"},
  "publisher": {"value": "string or null", "evidence": "quote or null"},
  "datePublished": {"value": "string (YYYY or YYYY-MM-DD)", "evidence": "quote from paper"},
  "inLanguage": {"value": "string (ISO codes)", "evidence": "quote or null"},
  "citeAs": {"value": "string or null", "evidence": "quote or null"},
  "isLiveDataset": {"value": "Yes/No or null", "evidence": "quote or null"},

  "rai:dataCollection": {"value": "string or null", "evidence": "quote or null"},
  "rai:dataCollectionType": {"value": "string (from recommended values) or null", "evidence": "quote or null"},
  "rai:dataCollectionMissingData": {"value": "string or null", "evidence": "quote or null"},
  "rai:dataCollectionRawData": {"value": "string or null", "evidence": "quote or null"},
  "rai:dataCollectionTimeframe": {"value": "string or null", "evidence": "quote or null"},
  "rai:dataImputationProtocol": {"value": "string or null", "evidence": "quote or null"},
  "rai:dataManipulationProtocol": {"value": "string or null", "evidence": "quote or null"},
  "rai:dataPreprocessingProtocol": {"value": "string or null", "evidence": "quote or null"},
  "rai:dataAnnotationProtocol": {"value": "string or null", "evidence": "quote or null"},
  "rai:dataAnnotationPlatform": {"value": "string or null", "evidence": "quote or null"},
  "rai:dataAnnotationAnalysis": {"value": "string or null", "evidence": "quote or null"},
  "rai:annotationsPerItem": {"value": "string or null", "evidence": "quote or null"},
  "rai:annotatorDemographics": {"value": "string or null", "evidence": "quote or null"},
  "rai:machineAnnotationTools": {"value": "string or null", "evidence": "quote or null"},
  "rai:dataReleaseMaintenancePlan": {"value": "string or null", "evidence": "quote or null"},
  "rai:personalSensitiveInformation": {"value": "string or null", "evidence": "quote or null"},
  "rai:dataSocialImpact": {"value": "string or null", "evidence": "quote or null"},
  "rai:dataBiases": {"value": "string or null", "evidence": "quote or null"},
  "rai:dataLimitations": {"value": "string or null", "evidence": "quote or null"},
  "rai:dataUseCases": {"value": "string or null", "evidence": "quote or null"}
}

For null fields, use: {"value": null, "evidence": null}

PAPER TEXT:
%s

Return ONLY valid JSON matching the schema above. No markdown, no explanations.'''


CORRECTION_PROMPT_TEMPLATE = """You previously extracted metadata from this paper but returned null for the following fields:
{null_fields}

The paper likely discusses these topics based on keyword analysis. Please re-read the paper carefully and try to extract these specific fields. If the information is genuinely not in the paper, return null.

Return ONLY valid JSON with just these keys: {field_keys}

PAPER TEXT:
{paper_text}"""


LICENSE_MAP = {
    "cc-by-4.0": "CC-BY-4.0", "cc by 4.0": "CC-BY-4.0",
    "cc-by-sa-4.0": "CC-BY-SA-4.0", "cc by-sa 4.0": "CC-BY-SA-4.0",
    "cc-by-nc-4.0": "CC-BY-NC-4.0", "cc by-nc 4.0": "CC-BY-NC-4.0",
    "cc-by-nc-sa-4.0": "CC-BY-NC-SA-4.0",
    "cc0-1.0": "CC0-1.0", "cc0": "CC0-1.0", "public domain": "CC0-1.0",
    "mit": "MIT", "mit license": "MIT",
    "apache-2.0": "Apache-2.0", "apache 2.0": "Apache-2.0",
}


# ── Phase 0: PDF text ─────────────────────────────────────────────
def extract_paper_text(ds_id: str) -> str | None:
    text = get_paper_text(ds_id)
    if text is None:
        return None
    text = strip_references(text).strip()
    if len(text) > MAX_PAPER_CHARS:
        text = text[:MAX_PAPER_CHARS]
    return text


# ── Phase 1: triage ───────────────────────────────────────────────
def load_triage(ds_id: str) -> dict:
    path = PHASE1_DIR / f"{ds_id}.json"
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f).get("triage", {})


# ── Phase 2: extract + evidence ───────────────────────────────────
def extract_phase2(cfg, paper_text, with_evidence=True):
    if with_evidence:
        user_content = USER_PROMPT_WITH_EVIDENCE % paper_text
        raw, usage = call_llm(cfg, SYSTEM_PROMPT, user_content, MAX_TOKENS_EXTRACT)
        parsed = parse_json_response(raw)
        extraction: dict = {}
        evidence: dict = {}
        for field in ALL_FIELDS:
            entry = parsed.get(field, {})
            if isinstance(entry, dict):
                extraction[field] = entry.get("value")
                evidence[field] = entry.get("evidence")
            else:
                extraction[field] = entry
                evidence[field] = None
        return extraction, evidence, usage

    # Ablation baseline: reuse single-pass user prompt (flat schema)
    from config import USER_PROMPT_TEMPLATE
    user_content = USER_PROMPT_TEMPLATE % paper_text
    raw, usage = call_llm(cfg, SYSTEM_PROMPT, user_content, MAX_TOKENS_EXTRACT)
    parsed = normalize_field_names(parse_json_response(raw))
    return parsed, {f: None for f in ALL_FIELDS}, usage


# ── Phase 2.5: self-correction ────────────────────────────────────
def _is_null(val) -> bool:
    if val is None:
        return True
    if isinstance(val, str) and val.strip().lower() in ("", "null", "none"):
        return True
    return False


def find_null_but_expected(extraction: dict, triage: dict) -> list[str]:
    missing = []
    for field in ALL_FIELDS:
        if not _is_null(extraction.get(field)):
            continue
        if field in EASY_FIELDS:
            missing.append(field)
            continue
        for group_name, group_fields in TRIAGE_GROUPS.items():
            if field not in group_fields:
                continue
            info = triage.get(group_name, {})
            if info.get("presence") in ("likely", "certain"):
                missing.append(field)
                break
    return missing


def self_correct(cfg, paper_text, extraction, triage):
    null_fields = find_null_but_expected(extraction, triage)
    if not null_fields:
        return extraction, 0, {"input_tokens": 0, "output_tokens": 0}

    prompt = CORRECTION_PROMPT_TEMPLATE.format(
        null_fields="\n".join(f"- {f}" for f in null_fields),
        field_keys=", ".join(null_fields),
        paper_text=paper_text,
    )

    try:
        raw, usage = call_llm(cfg, SYSTEM_PROMPT, prompt, MAX_TOKENS_CORRECT)
        corrected = parse_json_response(raw)
    except Exception as e:
        print(f"    Self-correction failed: {str(e)[:80]}")
        return extraction, 0, {"input_tokens": 0, "output_tokens": 0}

    applied = 0
    for field in null_fields:
        val = corrected.get(field)
        if not _is_null(val):
            extraction[field] = val
            applied += 1
    return extraction, applied, usage


# ── Phase 3: cross-document enrichment ────────────────────────────
def _enrich_huggingface(ds_id: str, extraction: dict) -> dict:
    enrichments: dict = {}
    hf_id = ds_id.replace("_", "/", 1)
    try:
        url = f"https://huggingface.co/api/datasets/{hf_id}"
        req = urllib.request.Request(url, headers={"User-Agent": "CroissantMiner/2.0"})
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        card = data.get("cardData", {}) or {}

        if _is_null(extraction.get("license")):
            lic = card.get("license")
            if lic:
                enrichments["license"] = lic
        if _is_null(extraction.get("url")):
            enrichments["url"] = f"https://huggingface.co/datasets/{hf_id}"
        if _is_null(extraction.get("inLanguage")):
            lang = card.get("language")
            if lang:
                enrichments["inLanguage"] = ", ".join(lang) if isinstance(lang, list) else str(lang)
    except Exception:
        pass
    return enrichments


def _enrich_semantic_scholar(ds_id: str, extraction: dict) -> dict:
    if not _is_null(extraction.get("citeAs")):
        return {}
    name = extraction.get("name") or ds_id
    try:
        q = urllib.parse.quote(str(name))
        url = (f"https://api.semanticscholar.org/graph/v1/paper/search"
               f"?query={q}&limit=1&fields=title,citationStyles")
        req = urllib.request.Request(url, headers={"User-Agent": "CroissantMiner/2.0"})
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        papers = data.get("data", [])
        if papers:
            bibtex = papers[0].get("citationStyles", {}).get("bibtex", "")
            if bibtex:
                return {"citeAs": bibtex}
    except Exception:
        pass
    return {}


def run_enrichment(ds_id: str, extraction: dict) -> tuple[dict, dict]:
    enrichments: dict = {}
    enrichments.update(_enrich_huggingface(ds_id, extraction))
    enrichments.update(_enrich_semantic_scholar(ds_id, extraction))
    for field, val in enrichments.items():
        extraction[field] = val
    return extraction, enrichments


# ── Phase 4: validation + confidence ──────────────────────────────
def validate_and_score(extraction, evidence, enrichments, triage) -> dict:
    details: dict = {}
    for field in ALL_FIELDS:
        val = extraction.get(field)

        if isinstance(val, str) and val.strip().lower() in (
            "", "null", "none", "n/a", "not applicable",
            "[null]", "[null - not found in paper]",
        ):
            val = None
        if isinstance(val, list):
            val = ", ".join(str(x) for x in val)
        if field == "license" and val:
            norm = LICENSE_MAP.get(str(val).strip().lower())
            if norm:
                val = norm
        if field == "url" and val and not re.match(r"https?://", str(val)):
            val = f"https://{val}"

        extraction[field] = val

        if val is None:
            details[field] = {"confidence": 0.0, "status": "NULL", "source": "absent", "evidence": None}
            continue

        confidence = 0.8
        source = "extraction"
        field_ev = evidence.get(field)
        has_ev = field_ev is not None and str(field_ev).strip() not in ("", "null", "None")
        if has_ev:
            confidence = min(confidence + 0.15, 1.0)
        if field in enrichments:
            source = "enrichment"
            confidence = 0.7

        if field in HARD_FIELDS:
            for group_name, group_fields in TRIAGE_GROUPS.items():
                if field in group_fields:
                    if triage.get(group_name, {}).get("presence") == "unlikely":
                        confidence = min(confidence, 0.5)
                    break

        status = ("VERIFIED" if confidence >= 0.7
                  else "UNCERTAIN" if confidence >= 0.4
                  else "LOW_CONFIDENCE")
        details[field] = {
            "confidence": round(confidence, 2),
            "status": status,
            "source": source,
            "evidence": field_ev if has_ev else None,
        }
    return details


# ── Phase 5: save canonical output ────────────────────────────────
def _paper_stats(details: dict) -> dict:
    extracted = sum(1 for d in details.values() if d["status"] != "NULL")
    verified = sum(1 for d in details.values() if d["status"] == "VERIFIED")
    uncertain = sum(1 for d in details.values() if d["status"] == "UNCERTAIN")
    ev = sum(1 for d in details.values() if d.get("evidence"))
    confs = [d["confidence"] for d in details.values() if d["status"] != "NULL"]
    avg = sum(confs) / len(confs) if confs else 0.0
    return {
        "fields_extracted": extracted,
        "fields_null": 30 - extracted,
        "fields_verified": verified,
        "fields_uncertain": uncertain,
        "evidence_count": ev,
        "evidence_coverage": round(ev / max(extracted, 1) * 100, 1),
        "avg_confidence": round(avg, 3),
    }


def save_paper(out_dir: Path, ds_id: str, cfg, extraction, details, usage,
               mode: str, extra_meta: dict) -> dict:
    stats = _paper_stats(details)
    extra = {
        "pipeline": "agentic_v2",
        "extraction_details": details,
        "paper_stats": stats,
        "cost_usd": estimate_cost(cfg, usage, batch_discount=(mode == "batch")),
        "split": "dev" if ds_id in SPLIT["dev"] else "test",
    }
    extra.update(extra_meta)
    meta = meta_block(cfg, SCRIPT_NAME, mode, extra=extra)
    from _agentic_helpers import write_canonical_output
    write_canonical_output(out_dir, ds_id, extraction, usage, cfg, meta)
    return stats


# ── Sequential processing ─────────────────────────────────────────
def process_paper(cfg, ds_id: str, args, out_dir: Path) -> dict | None:
    t0 = time.time()
    paper_text = extract_paper_text(ds_id)
    if not paper_text:
        print(f"  SKIP {ds_id}: no PDF")
        return None

    triage = load_triage(ds_id)

    usage = {"input_tokens": 0, "output_tokens": 0}

    with_evidence = not args.no_verification
    extraction, evidence, ext_usage = extract_phase2(cfg, paper_text, with_evidence)
    usage["input_tokens"] += ext_usage["input_tokens"]
    usage["output_tokens"] += ext_usage["output_tokens"]

    corrections = 0
    if not args.no_correction:
        extraction, corrections, cusage = self_correct(cfg, paper_text, extraction, triage)
        usage["input_tokens"] += cusage["input_tokens"]
        usage["output_tokens"] += cusage["output_tokens"]

    enrichments: dict = {}
    if not args.no_enrichment:
        extraction, enrichments = run_enrichment(ds_id, extraction)

    if args.no_verification:
        details = {
            f: {"confidence": 0.8 if extraction.get(f) is not None else 0.0,
                "status": "EXTRACTED" if extraction.get(f) is not None else "NULL",
                "source": "extraction", "evidence": None}
            for f in ALL_FIELDS
        }
    else:
        details = validate_and_score(extraction, evidence, enrichments, triage)

    extra_meta = {
        "corrections_applied": corrections,
        "enrichments": list(enrichments.keys()),
        "elapsed_seconds": round(time.time() - t0, 1),
        "flags": {
            "correction": not args.no_correction,
            "enrichment": not args.no_enrichment,
            "verification": not args.no_verification,
        },
    }
    return save_paper(out_dir, ds_id, cfg, extraction, details, usage, "realtime", extra_meta)


def run_sequential(cfg, papers, args, out_dir):
    ok = fail = total_extracted = total_verified = 0
    total_usage = {"input_tokens": 0, "output_tokens": 0}

    for i, ds_id in enumerate(papers):
        safe = ds_id.replace("/", "__")
        out_path = out_dir / f"{safe}.json"
        if out_path.exists() and not args.paper:
            ok += 1
            if (i + 1) % 25 == 0:
                print(f"  [{i+1}/{len(papers)}] {ok} done (skipping existing)")
            continue

        try:
            stats = process_paper(cfg, ds_id, args, out_dir)
            if stats is None:
                fail += 1
                continue
            ok += 1
            total_extracted += stats["fields_extracted"]
            total_verified += stats["fields_verified"]
            with open(out_path) as f:
                saved = json.load(f)
            total_usage["input_tokens"] += saved["usage"]["input_tokens"]
            total_usage["output_tokens"] += saved["usage"]["output_tokens"]
            print(f"  [{i+1}/{len(papers)}] {ds_id}: "
                  f"{stats['fields_extracted']}/30 extracted, "
                  f"{stats['fields_verified']} verified, "
                  f"${saved['_meta']['cost_usd']:.3f}, "
                  f"{saved['_meta']['elapsed_seconds']:.0f}s")
        except Exception as e:
            print(f"  [{i+1}/{len(papers)}] {ds_id}: FAILED ({str(e)[:80]})")
            fail += 1
        time.sleep(0.4)

    total_cost = estimate_cost(cfg, total_usage, batch_discount=False)
    total_fields = ok * 30
    print(f"\n{'=' * 70}")
    print(f"SUMMARY — V2 sequential ({cfg['name']})")
    print(f"{'=' * 70}")
    print(f"Papers: {ok} OK, {fail} failed")
    print(f"Fields: {total_extracted}/{total_fields} "
          f"({total_extracted / max(total_fields, 1) * 100:.1f}%)")
    print(f"Verified: {total_verified}/{total_fields}")
    print(f"Tokens: {total_usage['input_tokens']:,} in, "
          f"{total_usage['output_tokens']:,} out")
    print(f"Cost: ${total_cost:.2f}")
    print(f"Output: {out_dir}/")

    summary = {
        "backbone": cfg["model_id"],
        "papers_ok": ok, "papers_failed": fail,
        "total_extracted": total_extracted,
        "total_verified": total_verified,
        "fill_rate": round(total_extracted / max(total_fields, 1) * 100, 1),
        "usage": total_usage, "cost_usd": total_cost,
    }
    with open(out_dir / "_summary.json", "w") as f:
        json.dump(summary, f, indent=2)


# ── Anthropic-only batch mode ─────────────────────────────────────
def _require_anthropic(cfg):
    if cfg["provider"] != "anthropic":
        raise SystemExit(
            f"Batch mode currently supports provider=anthropic only "
            f"(backbone '{cfg['model_id']}' uses provider={cfg['provider']}). "
            f"Run without --batch for sequential execution."
        )


def _sanitize_custom_id(ds_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", ds_id.replace("/", "__"))[:64]


def run_batch(cfg, papers, args, out_dir):
    _require_anthropic(cfg)
    import anthropic
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request

    client = anthropic.Anthropic()
    wave_dir = out_dir / "_batch"
    wave_dir.mkdir(parents=True, exist_ok=True)

    # ── Wave 1: base extraction ──
    wave1_path = wave_dir / "wave1.json"
    if wave1_path.exists():
        wave1 = json.loads(wave1_path.read_text())
    else:
        requests = []
        id_map: dict = {}
        for ds_id in papers:
            safe = ds_id.replace("/", "__")
            if (out_dir / f"{safe}.json").exists():
                continue
            text = extract_paper_text(ds_id)
            if not text:
                print(f"  skip (no PDF): {ds_id}")
                continue
            cid = _sanitize_custom_id(ds_id)
            id_map[cid] = ds_id
            requests.append(Request(
                custom_id=cid,
                params=MessageCreateParamsNonStreaming(
                    model=cfg["model_id"],
                    max_tokens=MAX_TOKENS_EXTRACT,
                    temperature=0.0,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": USER_PROMPT_WITH_EVIDENCE % text}],
                ),
            ))
        if not requests:
            print("  No papers to submit for Wave 1.")
            return
        batch = client.messages.batches.create(requests=requests)
        wave1 = {"batch_id": batch.id, "id_map": id_map,
                 "submitted_at": time.strftime("%Y-%m-%d %H:%M:%S")}
        wave1_path.write_text(json.dumps(wave1, indent=2))
        print(f"  Wave 1 submitted: {batch.id} ({len(requests)} requests)")

    # Poll Wave 1
    while True:
        info = client.messages.batches.retrieve(wave1["batch_id"])
        counts = info.request_counts
        print(f"    Wave 1 {info.processing_status}: "
              f"proc={counts.processing} ok={counts.succeeded} err={counts.errored}")
        if info.processing_status == "ended":
            break
        time.sleep(30)

    # Collect Wave 1 parsed results
    parsed: dict = {}
    for result in client.messages.batches.results(wave1["batch_id"]):
        ds_id = wave1["id_map"].get(result.custom_id, result.custom_id)
        if result.result.type != "succeeded":
            print(f"    Wave 1 FAILED {ds_id}: {result.result.type}")
            continue
        msg = result.result.message
        raw = "".join(getattr(b, "text", "") for b in msg.content)
        usage = {"input_tokens": msg.usage.input_tokens,
                 "output_tokens": msg.usage.output_tokens}
        try:
            data = parse_json_response(raw)
        except Exception as exc:
            print(f"    Wave 1 parse failed {ds_id}: {str(exc)[:60]}")
            continue
        extraction, evidence = {}, {}
        for field in ALL_FIELDS:
            entry = data.get(field, {})
            if isinstance(entry, dict):
                extraction[field] = entry.get("value")
                evidence[field] = entry.get("evidence")
            else:
                extraction[field] = entry
                evidence[field] = None
        parsed[ds_id] = {"extraction": extraction, "evidence": evidence, "usage": usage}

    print(f"  Wave 1 parsed: {len(parsed)} papers")

    # ── Wave 2: corrections batch (optional) ──
    wave2_path = wave_dir / "wave2.json"
    corrections: dict = {}
    if not args.no_correction:
        need: dict = {}
        for ds_id, rec in parsed.items():
            triage = load_triage(ds_id)
            nulls = find_null_but_expected(rec["extraction"], triage)
            if nulls:
                need[ds_id] = nulls
        print(f"  Papers needing corrections: {len(need)}/{len(parsed)}")

        if need and not wave2_path.exists():
            reqs = []
            id_map2: dict = {}
            for ds_id, nulls in need.items():
                text = extract_paper_text(ds_id)
                if not text:
                    continue
                prompt = CORRECTION_PROMPT_TEMPLATE.format(
                    null_fields="\n".join(f"- {f}" for f in nulls),
                    field_keys=", ".join(nulls),
                    paper_text=text,
                )
                cid = _sanitize_custom_id(ds_id)
                id_map2[cid] = ds_id
                reqs.append(Request(
                    custom_id=cid,
                    params=MessageCreateParamsNonStreaming(
                        model=cfg["model_id"],
                        max_tokens=MAX_TOKENS_CORRECT,
                        temperature=0.0,
                        system=SYSTEM_PROMPT,
                        messages=[{"role": "user", "content": prompt}],
                    ),
                ))
            if reqs:
                batch = client.messages.batches.create(requests=reqs)
                wave2 = {"batch_id": batch.id, "id_map": id_map2, "need": need,
                         "submitted_at": time.strftime("%Y-%m-%d %H:%M:%S")}
                wave2_path.write_text(json.dumps(wave2, indent=2))
                print(f"  Wave 2 submitted: {batch.id} ({len(reqs)} requests)")

        if wave2_path.exists():
            wave2 = json.loads(wave2_path.read_text())
            while True:
                info = client.messages.batches.retrieve(wave2["batch_id"])
                counts = info.request_counts
                print(f"    Wave 2 {info.processing_status}: "
                      f"proc={counts.processing} ok={counts.succeeded} err={counts.errored}")
                if info.processing_status == "ended":
                    break
                time.sleep(30)
            for result in client.messages.batches.results(wave2["batch_id"]):
                ds_id = wave2["id_map"].get(result.custom_id, result.custom_id)
                if result.result.type != "succeeded":
                    print(f"    Wave 2 FAILED {ds_id}")
                    continue
                msg = result.result.message
                raw = "".join(getattr(b, "text", "") for b in msg.content)
                usage = {"input_tokens": msg.usage.input_tokens,
                         "output_tokens": msg.usage.output_tokens}
                try:
                    corrected = parse_json_response(raw)
                except Exception:
                    continue
                corrections[ds_id] = {"corrected": corrected,
                                      "nulls": wave2["need"].get(ds_id, []),
                                      "usage": usage}

    # ── Apply corrections + enrichment + validation + save ──
    ok = 0
    for ds_id, rec in parsed.items():
        extraction = rec["extraction"]
        evidence = rec["evidence"]
        usage = dict(rec["usage"])
        applied = 0
        if ds_id in corrections:
            c = corrections[ds_id]
            usage["input_tokens"] += c["usage"]["input_tokens"]
            usage["output_tokens"] += c["usage"]["output_tokens"]
            for field in c["nulls"]:
                val = c["corrected"].get(field)
                if not _is_null(val):
                    extraction[field] = val
                    applied += 1

        enrichments: dict = {}
        if not args.no_enrichment:
            extraction, enrichments = run_enrichment(ds_id, extraction)

        triage = load_triage(ds_id)
        details = validate_and_score(extraction, evidence, enrichments, triage)

        extra_meta = {
            "corrections_applied": applied,
            "enrichments": list(enrichments.keys()),
            "flags": {
                "correction": not args.no_correction,
                "enrichment": not args.no_enrichment,
                "verification": True,
            },
        }
        save_paper(out_dir, ds_id, cfg, extraction, details, usage, "batch", extra_meta)
        ok += 1

    print(f"  Batch pipeline done: {ok} papers written to {out_dir}")


# ── CLI ───────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(description="CroissantMiner Agentic V2 pipeline")
    p.add_argument("--backbone", default="sonnet-4-5",
                   help="Backbone key from scripts/_agentic_helpers.py::MODELS")
    p.add_argument("--dev-only", action="store_true", help="Process only the 15 dev papers")
    p.add_argument("--paper", type=str, help="Process a single paper by dataset_id")
    p.add_argument("--batch", action="store_true",
                   help="Use Anthropic batch API (sonnet-4-5 only)")
    p.add_argument("--no-enrichment", action="store_true", help="Ablation: skip Phase 3")
    p.add_argument("--no-verification", action="store_true", help="Ablation: skip Phase 4")
    p.add_argument("--no-correction", action="store_true", help="Ablation: skip Phase 2.5")
    args = p.parse_args()

    cfg = resolve_backbone(args.backbone)
    out_dir = output_dir_for("v2", args.backbone)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.paper:
        papers = [args.paper]
    elif args.dev_only:
        papers = sorted(SPLIT["dev"])
    else:
        papers = sorted(SPLIT["dev"] + SPLIT["test"])

    print(f"{'=' * 70}")
    print(f"CROISSANTMINER AGENTIC V2 — backbone={args.backbone} ({cfg['name']})")
    print(f"Papers: {len(papers)}  Output: {out_dir}")
    print(f"Flags: correction={'ON' if not args.no_correction else 'OFF'}, "
          f"enrichment={'ON' if not args.no_enrichment else 'OFF'}, "
          f"verification={'ON' if not args.no_verification else 'OFF'}")
    print(f"{'=' * 70}")

    if args.batch:
        run_batch(cfg, papers, args, out_dir)
    else:
        run_sequential(cfg, papers, args, out_dir)


if __name__ == "__main__":
    main()
