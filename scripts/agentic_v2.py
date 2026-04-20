#!/usr/bin/env python3
"""
CroissantMiner Agentic Pipeline V2

Phases:
  0: PDF parse (reuse existing)
  1: Gemini Flash triage (reuse existing)
  2: Full-context Claude extraction with Citations API
  2.5: Self-correction on missed fields
  3: Cross-document enrichment (HuggingFace, Semantic Scholar)
  4: Schema validation + confidence scoring
  5: Merge final output

Usage:
  python scripts/agentic_v2.py                    # all 103 papers
  python scripts/agentic_v2.py --dev-only          # 15 dev papers
  python scripts/agentic_v2.py --paper AI4Math_MathVista  # single paper
  python scripts/agentic_v2.py --no-enrichment     # ablation: skip phase 3
  python scripts/agentic_v2.py --no-verification   # ablation: skip phase 4
  python scripts/agentic_v2.py --no-correction     # ablation: skip phase 2.5
  python scripts/agentic_v2.py --no-progressive    # ablation: extract all 30 at once
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from collections import defaultdict
from pathlib import Path

from croissantminer.pdf.reader import extract_text_from_pdf as _canonical_extract_text
from croissantminer.pdf.processor import clean_text as _canonical_clean_text
import anthropic
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════

MODEL = "claude-sonnet-4-5-20250929"
TEMPERATURE = 0
MAX_TOKENS = 4096

RAW_DIR = ROOT / "data" / "raw"
PHASE1_DIR = ROOT / "data" / "agentic" / "phase1"
OUTPUT_DIR = ROOT / "data" / "agentic" / "v2"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PROCESSED_DIR = ROOT / "data" / "processed"

with open(ROOT / "data" / "agentic" / "dev_test_split.json") as f:
    SPLIT = json.load(f)

with open(ROOT / "data" / "paper_links.json") as f:
    PAPER_LINKS = json.load(f)

# SPDX cache for license normalization
SPDX_PATH = ROOT / "experiments" / "validators" / "_spdx_cache.json"
SPDX = {}
if SPDX_PATH.exists():
    with open(SPDX_PATH) as f:
        SPDX = json.load(f)

client = anthropic.Anthropic()

EASY_FIELDS = [
    "name", "description", "url", "license", "creator",
    "publisher", "datePublished", "inLanguage", "citeAs", "isLiveDataset"
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
    "rai:dataBiases", "rai:dataLimitations", "rai:dataUseCases"
]
ALL_FIELDS = EASY_FIELDS + HARD_FIELDS

# Import the system prompt field definitions from config
sys.path.insert(0, str(ROOT))
from config import SYSTEM_PROMPT


# ═══════════════════════════════════════════════════════════════
# PHASE 0: PDF TEXT EXTRACTION
# ═══════════════════════════════════════════════════════════════

def extract_paper_text(ds_id):
    """Extract and clean text from PDF using PyMuPDF."""
    pdf_path = RAW_DIR / f"{ds_id}.pdf"
    if not pdf_path.exists():
        # Try arxiv ID patterns
        url = PAPER_LINKS.get(ds_id, "")
        m = re.search(r'(\d{4}\.\d{4,5})', url)
        if m:
            for sfx in ["", "v1", "v2", "v3", "v4", "v5"]:
                p = RAW_DIR / f"{m.group(1)}{sfx}.pdf"
                if p.exists():
                    pdf_path = p
                    break
    if not pdf_path.exists():
        return None

    text = _canonical_clean_text(_canonical_extract_text(str(pdf_path)))
    # Strip references section (last ~30-40% after "References" heading)
    ref_patterns = [
        r'\n\s*References\s*\n',
        r'\n\s*REFERENCES\s*\n',
        r'\n\s*Bibliography\s*\n',
    ]
    for pattern in ref_patterns:
        match = re.search(pattern, text)
        if match and match.start() > len(text) * 0.5:
            text = text[:match.start()]
            break

    # Truncate if too long (keep within Claude's context)
    if len(text) > 200000:
        text = text[:200000]

    return text.strip()


# ═══════════════════════════════════════════════════════════════
# PHASE 1: LOAD TRIAGE (from existing Phase 1 results)
# ═══════════════════════════════════════════════════════════════

def load_triage(ds_id):
    """Load Gemini triage predictions for this paper."""
    path = PHASE1_DIR / f"{ds_id}.json"
    if not path.exists():
        return {}
    with open(path) as f:
        data = json.load(f)
    return data.get("triage", {})


# ═══════════════════════════════════════════════════════════════
# PHASE 2: FULL-CONTEXT EXTRACTION (same prompt as single-pass + evidence)
# ═══════════════════════════════════════════════════════════════

# Import the exact same prompts single-pass uses
from config import USER_PROMPT_TEMPLATE

# Enhanced user prompt that also asks for evidence quotes (free, no extra API cost)
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


def parse_json_response(raw_text):
    """Parse JSON from Claude's response, handling markdown fences."""
    raw = raw_text.strip()
    if raw.startswith("```json"):
        raw = raw[7:]
    elif raw.startswith("```"):
        raw = raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]

    first = raw.find("{")
    last = raw.rfind("}")
    if first != -1 and last != -1:
        raw = raw[first:last + 1]

    return json.loads(raw.strip())


def call_claude(paper_text, user_prompt, system_prompt=SYSTEM_PROMPT, max_tokens=MAX_TOKENS):
    """Call Claude with retry logic. Returns (parsed_json, usage)."""
    content = user_prompt % paper_text if "%s" in user_prompt else user_prompt
    backoff = [5, 15, 45]

    for attempt in range(3):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=max_tokens,
                temperature=TEMPERATURE,
                system=system_prompt,
                messages=[{"role": "user", "content": content}]
            )
            result = parse_json_response(response.content[0].text)
            usage = {"input": response.usage.input_tokens, "output": response.usage.output_tokens}
            return result, usage

        except anthropic.RateLimitError as e:
            wait = backoff[attempt] if attempt < len(backoff) else 60
            print(f"    Rate limited (429). Waiting {wait}s... (attempt {attempt + 1}/3)")
            time.sleep(wait)

        except anthropic.APIStatusError as e:
            if e.status_code >= 500:
                wait = backoff[attempt] if attempt < len(backoff) else 60
                print(f"    Server error ({e.status_code}). Waiting {wait}s... (attempt {attempt + 1}/3)")
                time.sleep(wait)
            else:
                raise  # 4xx errors (except 429) are not retryable

        except json.JSONDecodeError as e:
            if attempt < 2:
                print(f"    JSON parse failed: {str(e)[:50]}. Retrying... (attempt {attempt + 1}/3)")
                time.sleep(backoff[attempt])
            else:
                raise  # give up after 3 JSON failures

    raise Exception("All 3 retry attempts failed")


def extract_phase2(paper_text, with_evidence=True):
    """Phase 2: Extract all 30 fields using the same prompt as single-pass.

    If with_evidence=True: use enhanced schema that asks for evidence quotes per field.
    If with_evidence=False: use exact single-pass prompt (for ablation baseline).
    """
    if with_evidence:
        result, usage = call_claude(paper_text, USER_PROMPT_WITH_EVIDENCE, max_tokens=8192)
        # Parse the value/evidence structure
        extraction = {}
        evidence = {}
        for field in ALL_FIELDS:
            entry = result.get(field, {})
            if isinstance(entry, dict):
                extraction[field] = entry.get("value")
                evidence[field] = entry.get("evidence")
            else:
                # Model returned flat value instead of {value, evidence}
                extraction[field] = entry
                evidence[field] = None
        return extraction, evidence, usage
    else:
        # Exact single-pass prompt (ablation baseline)
        result, usage = call_claude(paper_text, USER_PROMPT_TEMPLATE)
        evidence = {f: None for f in ALL_FIELDS}
        return result, evidence, usage


# ═══════════════════════════════════════════════════════════════
# PHASE 2.5: SELF-CORRECTION
# ═══════════════════════════════════════════════════════════════

CORRECTION_PROMPT_TEMPLATE = """You previously extracted metadata from this paper but returned null for the following fields:
{null_fields}

The paper likely discusses these topics based on keyword analysis. Please re-read the paper carefully and try to extract these specific fields. If the information is genuinely not in the paper, return null.

Return ONLY valid JSON with just these keys: {field_keys}"""


def self_correct(paper_text, extraction, triage, usage_tracker):
    """Phase 2.5: Re-extract fields that are null but triage says present."""
    # Find fields where extraction = null but triage suggests presence
    null_but_expected = []
    for field in ALL_FIELDS:
        val = extraction.get(field)
        is_null = val is None or (isinstance(val, str) and val.strip().lower() in ("", "null", "none"))
        if not is_null:
            continue

        # Check triage
        expected = False
        if field in EASY_FIELDS:
            # Easy fields: always try correction (cheap)
            expected = True
        else:
            # Hard fields: check triage groups
            for group_name, group_info in triage.items():
                if group_info.get("presence") in ("likely", "certain"):
                    # Map group to fields
                    group_fields = {
                        "G3_collection": ["rai:dataCollection", "rai:dataCollectionType",
                                         "rai:dataCollectionMissingData", "rai:dataCollectionRawData",
                                         "rai:dataCollectionTimeframe"],
                        "G4_annotation": ["rai:dataAnnotationProtocol", "rai:dataAnnotationPlatform",
                                         "rai:dataAnnotationAnalysis", "rai:annotationsPerItem",
                                         "rai:annotatorDemographics", "rai:machineAnnotationTools"],
                        "G5_rai": ["rai:dataBiases", "rai:dataLimitations", "rai:dataSocialImpact",
                                  "rai:personalSensitiveInformation", "rai:dataUseCases",
                                  "rai:dataReleaseMaintenancePlan"],
                        "G6_processing": ["rai:dataImputationProtocol", "rai:dataManipulationProtocol",
                                         "rai:dataPreprocessingProtocol"],
                    }
                    if field in group_fields.get(group_name, []):
                        expected = True
                        break

        if expected:
            null_but_expected.append(field)

    if not null_but_expected:
        return extraction, 0

    # Re-extract only the missing fields
    null_field_descs = "\n".join(f"- {f}" for f in null_but_expected)
    field_keys = ", ".join(null_but_expected)
    prompt = CORRECTION_PROMPT_TEMPLATE.format(
        null_fields=null_field_descs,
        field_keys=field_keys
    )

    try:
        full_prompt = prompt + "\n\nPAPER TEXT:\n%s"
        corrected, usage = call_claude(paper_text, full_prompt)
        usage_tracker["input"] += usage["input"]
        usage_tracker["output"] += usage["output"]

        # Merge corrections (only overwrite if new value is non-null)
        corrections_applied = 0
        for field in null_but_expected:
            new_val = corrected.get(field)
            if new_val is not None and str(new_val).strip().lower() not in ("", "null", "none"):
                extraction[field] = new_val
                corrections_applied += 1

        return extraction, corrections_applied
    except Exception as e:
        print(f"    Self-correction failed: {e}")
        return extraction, 0


# ═══════════════════════════════════════════════════════════════
# PHASE 3: CROSS-DOCUMENT ENRICHMENT
# ═══════════════════════════════════════════════════════════════

def enrich_from_huggingface(ds_id, extraction):
    """Query HuggingFace API to fill gaps."""
    enrichments = {}

    # Try to find dataset on HuggingFace
    # Dataset IDs in our corpus are like "org_name" format
    hf_id = ds_id.replace("_", "/", 1)

    try:
        url = f"https://huggingface.co/api/datasets/{hf_id}"
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "CroissantMiner/2.0")
        resp = urllib.request.urlopen(req, timeout=10)
        hf_data = json.loads(resp.read())

        # License
        current_license = extraction.get("license")
        if not current_license or str(current_license).strip().lower() in ("null", "none", ""):
            hf_license = hf_data.get("cardData", {}).get("license")
            if hf_license:
                enrichments["license"] = hf_license

        # URL
        current_url = extraction.get("url")
        if not current_url or str(current_url).strip().lower() in ("null", "none", ""):
            enrichments["url"] = f"https://huggingface.co/datasets/{hf_id}"

        # Language
        current_lang = extraction.get("inLanguage")
        if not current_lang or str(current_lang).strip().lower() in ("null", "none", ""):
            hf_lang = hf_data.get("cardData", {}).get("language")
            if hf_lang:
                if isinstance(hf_lang, list):
                    enrichments["inLanguage"] = ", ".join(hf_lang)
                else:
                    enrichments["inLanguage"] = str(hf_lang)

    except Exception:
        pass  # HuggingFace dataset not found or API error

    return enrichments


def enrich_from_semantic_scholar(ds_id, extraction):
    """Query Semantic Scholar to fill citeAs gaps."""
    enrichments = {}

    current_cite = extraction.get("citeAs")
    if current_cite and str(current_cite).strip().lower() not in ("null", "none", ""):
        return enrichments

    # Search by dataset name
    name = extraction.get("name", ds_id)
    if not name:
        return enrichments

    try:
        query = urllib.parse.quote(str(name))
        url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={query}&limit=1&fields=title,citationStyles"
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "CroissantMiner/2.0")
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())

        papers = data.get("data", [])
        if papers:
            cite_styles = papers[0].get("citationStyles", {})
            bibtex = cite_styles.get("bibtex", "")
            if bibtex:
                enrichments["citeAs"] = bibtex

    except Exception:
        pass

    return enrichments


def run_enrichment(ds_id, extraction):
    """Phase 3: Enrich extraction from external sources."""
    all_enrichments = {}

    hf_enrichments = enrich_from_huggingface(ds_id, extraction)
    all_enrichments.update(hf_enrichments)

    ss_enrichments = enrich_from_semantic_scholar(ds_id, extraction)
    all_enrichments.update(ss_enrichments)

    # Apply enrichments
    for field, value in all_enrichments.items():
        extraction[field] = value

    return extraction, all_enrichments


# ═══════════════════════════════════════════════════════════════
# PHASE 4: VALIDATION + CONFIDENCE
# ═══════════════════════════════════════════════════════════════

LICENSE_MAP = {
    "cc-by-4.0": "CC-BY-4.0", "cc by 4.0": "CC-BY-4.0",
    "cc-by-sa-4.0": "CC-BY-SA-4.0", "cc by-sa 4.0": "CC-BY-SA-4.0",
    "cc-by-nc-4.0": "CC-BY-NC-4.0", "cc by-nc 4.0": "CC-BY-NC-4.0",
    "cc-by-nc-sa-4.0": "CC-BY-NC-SA-4.0",
    "cc0-1.0": "CC0-1.0", "cc0": "CC0-1.0", "public domain": "CC0-1.0",
    "mit": "MIT", "mit license": "MIT",
    "apache-2.0": "Apache-2.0", "apache 2.0": "Apache-2.0",
}


def validate_and_score(extraction, evidence, enrichments, corrections_applied, triage):
    """Phase 4: Schema validation and confidence scoring."""
    fields = {}

    for field in ALL_FIELDS:
        val = extraction.get(field)

        # Normalize null variants
        if val is not None and isinstance(val, str) and val.strip().lower() in ("", "null", "none", "n/a", "not applicable", "[null]", "[null - not found in paper]"):
            val = None

        # Normalize list to string (inLanguage)
        if isinstance(val, list):
            val = ", ".join(str(x) for x in val)

        # License normalization
        if field == "license" and val:
            normalized = LICENSE_MAP.get(str(val).strip().lower())
            if normalized:
                val = normalized

        # URL prefix
        if field == "url" and val and not re.match(r'https?://', str(val)):
            val = f"https://{val}"

        # Confidence scoring
        if val is None:
            confidence = 0.0
            status = "NULL"
            source = "absent"
        else:
            confidence = 0.8  # base confidence

            # Boost if evidence quote provided
            field_evidence = evidence.get(field)
            has_evidence = field_evidence is not None and str(field_evidence).strip() not in ("", "null", "None")
            if has_evidence:
                confidence = min(confidence + 0.15, 1.0)

            # Boost/penalize based on source
            source = "extraction"
            if field in enrichments:
                source = "enrichment"
                confidence = 0.7  # enriched values are slightly less certain

            # Triage alignment
            if field in HARD_FIELDS:
                for group_name, group_info in triage.items():
                    group_fields = {
                        "G3_collection": ["rai:dataCollection", "rai:dataCollectionType",
                                         "rai:dataCollectionMissingData", "rai:dataCollectionRawData",
                                         "rai:dataCollectionTimeframe"],
                        "G4_annotation": ["rai:dataAnnotationProtocol", "rai:dataAnnotationPlatform",
                                         "rai:dataAnnotationAnalysis", "rai:annotationsPerItem",
                                         "rai:annotatorDemographics", "rai:machineAnnotationTools"],
                        "G5_rai": ["rai:dataBiases", "rai:dataLimitations", "rai:dataSocialImpact",
                                  "rai:personalSensitiveInformation", "rai:dataUseCases",
                                  "rai:dataReleaseMaintenancePlan"],
                        "G6_processing": ["rai:dataImputationProtocol", "rai:dataManipulationProtocol",
                                         "rai:dataPreprocessingProtocol"],
                    }
                    if field in group_fields.get(group_name, []):
                        if group_info.get("presence") == "unlikely":
                            confidence = min(confidence, 0.5)
                        break

            # Determine status
            if confidence >= 0.7:
                status = "VERIFIED"
            elif confidence >= 0.4:
                status = "UNCERTAIN"
            else:
                status = "LOW_CONFIDENCE"

        fields[field] = {
            "value": val,
            "confidence": round(confidence, 2),
            "status": status,
            "source": source,
        }
        if has_evidence if val is not None else False:
            fields[field]["evidence"] = field_evidence

    return fields


# ═══════════════════════════════════════════════════════════════
# PHASE 5: MERGE + SAVE
# ═══════════════════════════════════════════════════════════════

def merge_and_save(ds_id, fields, usage, meta):
    """Phase 5: Produce final output."""
    # Paper-level stats
    extracted = sum(1 for f in fields.values() if f["status"] != "NULL")
    null_count = sum(1 for f in fields.values() if f["status"] == "NULL")
    verified = sum(1 for f in fields.values() if f["status"] == "VERIFIED")
    uncertain = sum(1 for f in fields.values() if f["status"] == "UNCERTAIN")
    confs = [f["confidence"] for f in fields.values() if f["status"] != "NULL"]
    avg_conf = sum(confs) / max(len(confs), 1)

    output = {
        "paper_id": ds_id,
        "split": "dev" if ds_id in SPLIT["dev"] else "test",
        "fields": fields,
        "paper_stats": {
            "fields_extracted": extracted,
            "fields_null": null_count,
            "fields_verified": verified,
            "fields_uncertain": uncertain,
            "avg_confidence": round(avg_conf, 3),
        },
        "_meta": {
            "model": MODEL,
            "temperature": TEMPERATURE,
            "pipeline": "agentic_v2",
            "usage": usage,
            "cost_usd": round(usage["input"] / 1e6 * 3.0 + usage["output"] / 1e6 * 15.0, 4),
            **meta,
        }
    }

    # Also save a flat 30-field JSON for evaluation compatibility
    flat = {}
    for field in ALL_FIELDS:
        flat[field] = fields[field]["value"]

    out_dir = OUTPUT_DIR / ds_id
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(out_dir / "full_result.json", "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    with open(out_dir / "extraction.json", "w") as f:
        json.dump(flat, f, indent=2, ensure_ascii=False)

    return output


# ═══════════════════════════════════════════════════════════════
# MAIN PIPELINE
# ═══════════════════════════════════════════════════════════════

def process_paper(ds_id, args):
    """Run full V2 pipeline on one paper."""
    t0 = time.time()
    usage = {"input": 0, "output": 0}

    # Phase 0: Get paper text
    paper_text = extract_paper_text(ds_id)
    if not paper_text:
        print(f"  SKIP: no PDF for {ds_id}")
        return None

    # Phase 1: Load triage
    triage = load_triage(ds_id)

    # Phase 2: Extract with evidence quotes
    with_evidence = not args.no_verification  # evidence is part of verification
    extraction, evidence, ext_usage = extract_phase2(paper_text, with_evidence=with_evidence)
    usage["input"] += ext_usage["input"]
    usage["output"] += ext_usage["output"]

    # Phase 2.5: Self-correction
    corrections = 0
    if not args.no_correction:
        extraction, corrections = self_correct(paper_text, extraction, triage, usage)

    # Phase 3: Cross-document enrichment
    enrichments = {}
    if not args.no_enrichment:
        extraction, enrichments = run_enrichment(ds_id, extraction)

    # Phase 4: Validation + confidence
    if args.no_verification:
        # Skip verification: just normalize and return with default confidence
        fields = {}
        for field in ALL_FIELDS:
            val = extraction.get(field)
            if val is not None and isinstance(val, str) and val.strip().lower() in ("", "null", "none"):
                val = None
            fields[field] = {
                "value": val,
                "confidence": 0.8 if val is not None else 0.0,
                "status": "EXTRACTED" if val is not None else "NULL",
                "source": "extraction",
            }
    else:
        fields = validate_and_score(extraction, evidence, enrichments, corrections, triage)

    # Phase 5: Merge and save
    elapsed = time.time() - t0
    # Count evidence coverage
    non_null = sum(1 for f in ALL_FIELDS if fields[f]["status"] != "NULL")
    with_ev = sum(1 for f in ALL_FIELDS if fields[f].get("evidence") is not None)
    meta = {
        "corrections_applied": corrections,
        "enrichments": list(enrichments.keys()),
        "evidence_count": with_ev,
        "evidence_coverage": round(with_ev / max(non_null, 1) * 100, 1),
        "with_evidence": with_evidence,
        "elapsed_seconds": round(elapsed, 1),
    }
    output = merge_and_save(ds_id, fields, usage, meta)

    return output


def run_batch_extraction(papers, with_evidence=True):
    """Wave 1: Submit all base extractions as a batch job.

    Returns batch_id. Call check_batch() to poll for results.
    Uses Anthropic Message Batches API for 50% cost discount.
    """
    prompt_template = USER_PROMPT_WITH_EVIDENCE if with_evidence else USER_PROMPT_TEMPLATE
    max_tok = 8192 if with_evidence else MAX_TOKENS

    requests = []
    skipped = []
    for ds_id in papers:
        # Skip if already done
        if (OUTPUT_DIR / ds_id / "full_result.json").exists():
            skipped.append(ds_id)
            continue

        paper_text = extract_paper_text(ds_id)
        if not paper_text:
            print(f"  SKIP: no PDF for {ds_id}")
            continue

        content = prompt_template % paper_text

        # Sanitize custom_id: batch API requires ^[a-zA-Z0-9_-]{1,64}$
        safe_id = re.sub(r'[^a-zA-Z0-9_-]', '_', ds_id)[:64]

        requests.append({
            "custom_id": safe_id,
            "params": {
                "model": MODEL,
                "max_tokens": max_tok,
                "temperature": TEMPERATURE,
                "system": [{"type": "text", "text": SYSTEM_PROMPT}],
                "messages": [{"role": "user", "content": content}]
            }
        })

    if skipped:
        print(f"  Skipped {len(skipped)} already-done papers")

    if not requests:
        print("  No papers to process!")
        return None

    print(f"  Submitting batch of {len(requests)} papers...")
    batch = client.messages.batches.create(requests=requests)
    print(f"  Batch ID: {batch.id}")
    print(f"  Status: {batch.processing_status}")
    print(f"  Estimated completion: ~1 hour (max 24 hours)")

    # Save batch ID for later retrieval
    # Build safe_id -> ds_id mapping for result retrieval
    id_map = {}
    for r in requests:
        # Find original ds_id from the safe custom_id
        pass
    # We stored ds_id in the loop, rebuild from papers list
    safe_to_ds = {}
    for ds_id in papers:
        safe = re.sub(r'[^a-zA-Z0-9_-]', '_', ds_id)[:64]
        safe_to_ds[safe] = ds_id

    batch_info = {
        "batch_id": batch.id,
        "papers": [r["custom_id"] for r in requests],
        "safe_to_ds": safe_to_ds,
        "skipped": skipped,
        "submitted_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "with_evidence": with_evidence,
        "estimated_cost_usd": len(requests) * 0.10,
    }
    with open(OUTPUT_DIR / "_batch_wave1.json", "w") as f:
        json.dump(batch_info, f, indent=2)

    return batch.id


def check_batch(batch_id=None):
    """Check batch status and retrieve results if done."""
    if batch_id is None:
        batch_path = OUTPUT_DIR / "_batch_wave1.json"
        if not batch_path.exists():
            print("No batch found. Run with --batch first.")
            return False
        with open(batch_path) as f:
            batch_info = json.load(f)
        batch_id = batch_info["batch_id"]

    batch = client.messages.batches.retrieve(batch_id)
    counts = batch.request_counts
    print(f"Batch {batch_id}:")
    print(f"  Status: {batch.processing_status}")
    print(f"  Processing: {counts.processing}, Succeeded: {counts.succeeded}, "
          f"Errored: {counts.errored}, Expired: {counts.expired}")

    if batch.processing_status != "ended":
        print(f"  Not done yet. Check again later.")
        return False

    # Load safe_to_ds mapping
    batch_path = OUTPUT_DIR / "_batch_wave1.json"
    safe_to_ds = {}
    if batch_path.exists():
        with open(batch_path) as f:
            bi = json.load(f)
        safe_to_ds = bi.get("safe_to_ds", {})

    # Retrieve results
    print(f"\n  Retrieving results...")
    ok = 0
    fail = 0
    for result in client.messages.batches.results(batch_id):
        safe_id = result.custom_id
        ds_id = safe_to_ds.get(safe_id, safe_id)  # map back to original
        if result.result.type == "succeeded":
            msg = result.result.message
            raw_text = msg.content[0].text
            usage = {"input": msg.usage.input_tokens, "output": msg.usage.output_tokens}

            out_dir = OUTPUT_DIR / ds_id
            out_dir.mkdir(parents=True, exist_ok=True)
            with open(out_dir / "_batch_raw.json", "w") as f:
                json.dump({"raw_text": raw_text, "usage": usage}, f, indent=2)
            ok += 1
        else:
            print(f"  FAILED: {ds_id} — {result.result.error}")
            fail += 1

    print(f"\n  Retrieved: {ok} OK, {fail} failed")
    print(f"  Raw results saved to {OUTPUT_DIR}/*/\_batch_raw.json")
    print(f"  Next: run with --batch-continue to apply self-correction + enrichment + validation")
    return True


def find_null_but_expected(extraction, triage):
    """Identify fields that are null but triage says present."""
    null_but_expected = []
    for field in ALL_FIELDS:
        val = extraction.get(field)
        is_null = val is None or (isinstance(val, str) and val.strip().lower() in ("", "null", "none"))
        if not is_null:
            continue
        expected = field in EASY_FIELDS  # always try easy fields
        if not expected:
            for group_name, group_info in triage.items():
                if group_info.get("presence") in ("likely", "certain"):
                    group_fields = {
                        "G3_collection": ["rai:dataCollection", "rai:dataCollectionType",
                                         "rai:dataCollectionMissingData", "rai:dataCollectionRawData",
                                         "rai:dataCollectionTimeframe"],
                        "G4_annotation": ["rai:dataAnnotationProtocol", "rai:dataAnnotationPlatform",
                                         "rai:dataAnnotationAnalysis", "rai:annotationsPerItem",
                                         "rai:annotatorDemographics", "rai:machineAnnotationTools"],
                        "G5_rai": ["rai:dataBiases", "rai:dataLimitations", "rai:dataSocialImpact",
                                  "rai:personalSensitiveInformation", "rai:dataUseCases",
                                  "rai:dataReleaseMaintenancePlan"],
                        "G6_processing": ["rai:dataImputationProtocol", "rai:dataManipulationProtocol",
                                         "rai:dataPreprocessingProtocol"],
                    }
                    if field in group_fields.get(group_name, []):
                        expected = True
                        break
        if expected:
            null_but_expected.append(field)
    return null_but_expected


def batch_continue(papers, args):
    """Wave 2+3: Parse Wave 1 results, batch self-correction, then enrich + validate."""
    with open(OUTPUT_DIR / "_batch_wave1.json") as f:
        batch_info = json.load(f)
    with_evidence = batch_info.get("with_evidence", True)

    # ── Step 1: Parse all Wave 1 results ──
    print("  Step 1: Parsing Wave 1 results...")
    parsed_results = {}  # ds_id -> (extraction, evidence, usage)
    for ds_id in papers:
        if (OUTPUT_DIR / ds_id / "full_result.json").exists():
            continue  # already done
        raw_path = OUTPUT_DIR / ds_id / "_batch_raw.json"
        if not raw_path.exists():
            continue
        try:
            with open(raw_path) as f:
                batch_raw = json.load(f)
            parsed = parse_json_response(batch_raw["raw_text"])
            extraction = {}
            evidence = {}
            for field in ALL_FIELDS:
                entry = parsed.get(field, {})
                if isinstance(entry, dict):
                    extraction[field] = entry.get("value")
                    evidence[field] = entry.get("evidence")
                else:
                    extraction[field] = entry
                    evidence[field] = None
            parsed_results[ds_id] = (extraction, evidence, batch_raw["usage"])
        except Exception as e:
            print(f"    {ds_id}: parse failed ({str(e)[:50]})")

    print(f"  Parsed {len(parsed_results)} papers")

    # ── Step 2: Identify papers needing correction ──
    correction_needed = {}  # ds_id -> null_but_expected fields
    if not args.no_correction:
        for ds_id, (extraction, evidence, usage) in parsed_results.items():
            triage = load_triage(ds_id)
            null_fields = find_null_but_expected(extraction, triage)
            if null_fields:
                correction_needed[ds_id] = null_fields

    print(f"  Papers needing correction: {len(correction_needed)}/{len(parsed_results)}")

    # ── Step 3: Submit Wave 2 batch (corrections) ──
    wave2_batch_id = None
    if correction_needed:
        print(f"\n  Step 2: Submitting Wave 2 batch ({len(correction_needed)} correction calls)...")
        requests = []
        for ds_id, null_fields in correction_needed.items():
            paper_text = extract_paper_text(ds_id)
            if not paper_text:
                continue
            null_field_descs = "\n".join(f"- {f}" for f in null_fields)
            field_keys = ", ".join(null_fields)
            prompt = CORRECTION_PROMPT_TEMPLATE.format(
                null_fields=null_field_descs,
                field_keys=field_keys
            )
            full_prompt = prompt + "\n\nPAPER TEXT:\n" + paper_text
            if len(full_prompt) > 800000:
                full_prompt = prompt + "\n\nPAPER TEXT:\n" + paper_text[:600000]

            safe_id = re.sub(r'[^a-zA-Z0-9_-]', '_', ds_id)[:64]
            requests.append({
                "custom_id": safe_id,
                "params": {
                    "model": MODEL,
                    "max_tokens": MAX_TOKENS,
                    "temperature": TEMPERATURE,
                    "system": [{"type": "text", "text": SYSTEM_PROMPT}],
                    "messages": [{"role": "user", "content": full_prompt}]
                }
            })

        if requests:
            # Build safe->ds mapping for Wave 2
            w2_safe_to_ds = {}
            for ds_id in correction_needed:
                safe = re.sub(r'[^a-zA-Z0-9_-]', '_', ds_id)[:64]
                w2_safe_to_ds[safe] = ds_id

            batch = client.messages.batches.create(requests=requests)
            wave2_batch_id = batch.id
            print(f"  Batch ID: {wave2_batch_id}")

            with open(OUTPUT_DIR / "_batch_wave2.json", "w") as f:
                json.dump({"batch_id": wave2_batch_id, "papers": list(correction_needed.keys()),
                          "safe_to_ds": w2_safe_to_ds,
                          "submitted_at": time.strftime("%Y-%m-%d %H:%M:%S")}, f, indent=2)

            # Poll until done
            print(f"  Waiting for Wave 2 batch to complete...")
            while True:
                time.sleep(30)
                batch = client.messages.batches.retrieve(wave2_batch_id)
                counts = batch.request_counts
                print(f"    Status: {batch.processing_status} "
                      f"(processing={counts.processing}, done={counts.succeeded}, err={counts.errored})")
                if batch.processing_status == "ended":
                    break

            # Retrieve correction results
            print(f"  Retrieving Wave 2 results...")
            corrections_data = {}
            for result in client.messages.batches.results(wave2_batch_id):
                safe_id = result.custom_id
                ds_id = w2_safe_to_ds.get(safe_id, safe_id)
                if result.result.type == "succeeded":
                    msg = result.result.message
                    try:
                        corrected = parse_json_response(msg.content[0].text)
                        corrections_data[ds_id] = {
                            "corrected": corrected,
                            "usage": {"input": msg.usage.input_tokens, "output": msg.usage.output_tokens}
                        }
                    except Exception:
                        print(f"    {ds_id}: correction parse failed")
                else:
                    print(f"    {ds_id}: correction FAILED")
            print(f"  Wave 2 corrections retrieved: {len(corrections_data)}")
    else:
        print(f"  No corrections needed, skipping Wave 2 batch")
        corrections_data = {}

    # ── Step 4: Apply corrections + enrichment + validation + save ──
    print(f"\n  Step 3: Applying enrichment + validation...")
    total_usage = {"input": 0, "output": 0}
    ok = fail = total_extracted = total_verified = 0

    for i, ds_id in enumerate(papers):
        if (OUTPUT_DIR / ds_id / "full_result.json").exists():
            ok += 1
            continue
        if ds_id not in parsed_results:
            continue

        extraction, evidence, w1_usage = parsed_results[ds_id]
        usage = {"input": w1_usage["input"], "output": w1_usage["output"]}

        # Apply corrections
        corrections = 0
        if ds_id in corrections_data:
            corr = corrections_data[ds_id]
            usage["input"] += corr["usage"]["input"]
            usage["output"] += corr["usage"]["output"]
            for field in correction_needed.get(ds_id, []):
                new_val = corr["corrected"].get(field)
                if new_val is not None and str(new_val).strip().lower() not in ("", "null", "none"):
                    extraction[field] = new_val
                    corrections += 1

        # Enrichment (free)
        enrichments = {}
        if not args.no_enrichment:
            extraction, enrichments = run_enrichment(ds_id, extraction)

        # Validation
        triage = load_triage(ds_id)
        fields = validate_and_score(extraction, evidence, enrichments, corrections, triage)

        # Save
        non_null = sum(1 for f in ALL_FIELDS if fields[f]["status"] != "NULL")
        with_ev = sum(1 for f in ALL_FIELDS if fields[f].get("evidence") is not None)
        meta = {
            "corrections_applied": corrections,
            "enrichments": list(enrichments.keys()),
            "evidence_count": with_ev,
            "evidence_coverage": round(with_ev / max(non_null, 1) * 100, 1),
            "with_evidence": with_evidence,
            "batch_mode": True,
            "elapsed_seconds": 0,
        }
        output = merge_and_save(ds_id, fields, usage, meta)

        ok += 1
        stats = output["paper_stats"]
        total_usage["input"] += usage["input"]
        total_usage["output"] += usage["output"]
        total_extracted += stats["fields_extracted"]
        total_verified += stats["fields_verified"]

        if (i + 1) % 25 == 0:
            print(f"    [{i+1}/{len(papers)}] {ok} processed")

    # Summary
    w1_cost = sum(parsed_results[d][2]["input"] for d in parsed_results) / 1e6 * 1.5 + \
              sum(parsed_results[d][2]["output"] for d in parsed_results) / 1e6 * 7.5
    w2_cost = sum(c["usage"]["input"] for c in corrections_data.values()) / 1e6 * 1.5 + \
              sum(c["usage"]["output"] for c in corrections_data.values()) / 1e6 * 7.5
    total_cost = w1_cost + w2_cost
    total_fields = ok * 30

    print(f"\n{'=' * 70}")
    print(f"V2 BATCH PIPELINE COMPLETE")
    print(f"{'=' * 70}")
    print(f"Papers: {ok} OK, {fail} failed")
    print(f"Fields: {total_extracted}/{total_fields} ({total_extracted/max(total_fields,1)*100:.1f}%)")
    print(f"Verified: {total_verified}/{total_fields} ({total_verified/max(total_fields,1)*100:.1f}%)")
    print(f"Cost: Wave 1 ${w1_cost:.2f} + Wave 2 ${w2_cost:.2f} = ${total_cost:.2f} (batch pricing)")

    summary = {
        "papers_ok": ok, "papers_failed": fail,
        "total_extracted": total_extracted, "total_verified": total_verified,
        "fill_rate": round(total_extracted / max(total_fields, 1) * 100, 1),
        "usage": total_usage,
        "cost_wave1": round(w1_cost, 2), "cost_wave2": round(w2_cost, 2),
        "cost_total": round(total_cost, 2),
        "corrections_submitted": len(correction_needed),
        "corrections_applied": sum(1 for d in corrections_data if d in parsed_results),
    }
    with open(OUTPUT_DIR / "_summary.json", "w") as f:
        json.dump(summary, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="CroissantMiner Agentic V2 Pipeline")
    parser.add_argument("--dev-only", action="store_true", help="Process only 15 dev papers")
    parser.add_argument("--paper", type=str, help="Process a single paper by dataset_id")
    parser.add_argument("--batch", action="store_true", help="Submit base extractions as batch (half price)")
    parser.add_argument("--batch-check", action="store_true", help="Check batch status and retrieve results")
    parser.add_argument("--batch-continue", action="store_true", help="Process batch results (correction + enrichment)")
    parser.add_argument("--no-enrichment", action="store_true", help="Ablation: skip Phase 3 enrichment")
    parser.add_argument("--no-verification", action="store_true", help="Ablation: skip Phase 4 verification")
    parser.add_argument("--no-correction", action="store_true", help="Ablation: skip Phase 2.5 self-correction")
    parser.add_argument("--no-progressive", action="store_true", help="Ablation: extract all 30 fields at once")
    args = parser.parse_args()

    # Determine which papers to process
    if args.paper:
        papers = [args.paper]
    elif args.dev_only:
        papers = sorted(SPLIT["dev"])
    else:
        papers = sorted(SPLIT["dev"] + SPLIT["test"])

    # ── Batch mode routing ──
    if args.batch_check:
        check_batch()
        return

    if args.batch:
        print(f"{'=' * 70}")
        print(f"CROISSANTMINER V2 — FULL BATCH PIPELINE")
        print(f"{'=' * 70}")
        print(f"Papers: {len(papers)}")
        print(f"Estimated cost: ~${len(papers) * 0.18:.2f} (batch pricing)")
        print(f"Estimated time: ~2 hours (Wave 1 + Wave 2)")
        print(f"{'=' * 70}")

        # Wave 1: Submit base extractions
        print(f"\n{'─' * 70}")
        print(f"WAVE 1: Base extraction ({len(papers)} papers)")
        print(f"{'─' * 70}")
        batch_id = run_batch_extraction(papers, with_evidence=not args.no_verification)
        if batch_id is None:
            print("No papers to process.")
            return

        # Poll Wave 1
        print(f"\n  Waiting for Wave 1 to complete...")
        while True:
            time.sleep(30)
            batch = client.messages.batches.retrieve(batch_id)
            counts = batch.request_counts
            print(f"    {batch.processing_status}: processing={counts.processing}, "
                  f"done={counts.succeeded}, err={counts.errored}")
            if batch.processing_status == "ended":
                break

        # Download Wave 1 results
        check_batch(batch_id)

        # Wave 2+3: Correction batch + enrichment + validation
        print(f"\n{'─' * 70}")
        print(f"WAVE 2+3: Self-correction + enrichment + validation")
        print(f"{'─' * 70}")
        batch_continue(papers, args)
        return

    if args.batch_continue:
        print(f"{'=' * 70}")
        print(f"BATCH MODE — Resume from Wave 1 results")
        print(f"{'=' * 70}")
        batch_continue(papers, args)
        return

    # ── Regular (sequential) mode ──
    print(f"{'=' * 70}")
    print(f"CROISSANTMINER AGENTIC V2 PIPELINE")
    print(f"{'=' * 70}")
    print(f"Papers: {len(papers)}")
    print(f"Mode: Sequential (use --batch for 50% cost discount)")
    print(f"Flags: correction={'ON' if not args.no_correction else 'OFF'}, "
          f"enrichment={'ON' if not args.no_enrichment else 'OFF'}, "
          f"verification={'ON' if not args.no_verification else 'OFF'}")
    print(f"{'=' * 70}")

    # Process
    total_usage = {"input": 0, "output": 0}
    ok = 0
    fail = 0
    total_extracted = 0
    total_verified = 0

    for i, ds_id in enumerate(papers):
        # Skip if already done
        out_path = OUTPUT_DIR / ds_id / "full_result.json"
        if out_path.exists() and not args.paper:
            ok += 1
            if (i + 1) % 25 == 0:
                print(f"  [{i+1}/{len(papers)}] {ok} done (skipping existing)")
            continue

        try:
            result = process_paper(ds_id, args)
            if result:
                ok += 1
                stats = result["paper_stats"]
                meta = result["_meta"]
                total_usage["input"] += meta["usage"]["input"]
                total_usage["output"] += meta["usage"]["output"]
                total_extracted += stats["fields_extracted"]
                total_verified += stats["fields_verified"]
                print(f"  [{i+1}/{len(papers)}] {ds_id}: {stats['fields_extracted']}/30 extracted, "
                      f"{stats['fields_verified']} verified, ${meta['cost_usd']:.3f}, "
                      f"{meta['elapsed_seconds']:.0f}s")
            else:
                fail += 1
        except Exception as e:
            print(f"  [{i+1}/{len(papers)}] {ds_id}: FAILED ({str(e)[:60]})")
            fail += 1

        time.sleep(0.5)  # rate limit

    # Summary
    total_cost = total_usage["input"] / 1e6 * 3.0 + total_usage["output"] / 1e6 * 15.0
    total_fields = ok * 30

    print(f"\n{'=' * 70}")
    print(f"SUMMARY")
    print(f"{'=' * 70}")
    print(f"Papers: {ok} OK, {fail} failed")
    print(f"Fields: {total_extracted}/{total_fields} extracted ({total_extracted / max(total_fields, 1) * 100:.1f}%)")
    print(f"Verified: {total_verified}/{total_fields} ({total_verified / max(total_fields, 1) * 100:.1f}%)")
    print(f"Tokens: {total_usage['input']:,} in, {total_usage['output']:,} out")
    print(f"Cost: ${total_cost:.2f}")
    print(f"Output: {OUTPUT_DIR}/")

    # Save summary
    summary = {
        "papers_ok": ok,
        "papers_failed": fail,
        "total_extracted": total_extracted,
        "total_verified": total_verified,
        "total_fields": total_fields,
        "fill_rate": round(total_extracted / max(total_fields, 1) * 100, 1),
        "usage": total_usage,
        "cost_usd": round(total_cost, 2),
        "flags": {
            "progressive": not args.no_progressive,
            "correction": not args.no_correction,
            "enrichment": not args.no_enrichment,
            "verification": not args.no_verification,
        }
    }
    with open(OUTPUT_DIR / "_summary.json", "w") as f:
        json.dump(summary, f, indent=2)


if __name__ == "__main__":
    main()
