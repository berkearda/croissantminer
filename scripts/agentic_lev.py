#!/usr/bin/env python3
"""
CroissantMiner LEV (Locate-Extract-Verify) Agentic Pipeline

Architecture:
  LOCATE:  Reuse Phase 1 triage (Gemini Flash already identified sections per field group)
           + Phase 0 chunks (section-level text with boundaries)
           → Extract targeted section text per field group

  EXTRACT: 5 independent Claude Sonnet calls, each with ONLY relevant sections:
           Call 1: Core metadata (abstract + intro + data availability)
           Call 2: Collection fields (data collection / methods)
           Call 3: Annotation fields (annotation + appendix)
           Call 4: Impact/RAI fields (ethics + limitations + discussion)
           Call 5: Processing fields (preprocessing / methodology)

  VERIFY:  Cross-field consistency + schema validation + enrichment + confidence

Usage:
  python scripts/agentic_lev.py --paper AI4Math_MathVista   # single paper
  python scripts/agentic_lev.py --dev-only                   # 15 dev papers
  python scripts/agentic_lev.py                              # all 103
  python scripts/agentic_lev.py --batch                      # batch mode (50% off)
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

sys.path.insert(0, str(ROOT))
from config import SYSTEM_PROMPT

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════

MODEL = "claude-sonnet-4-5-20250929"
TEMPERATURE = 0
MAX_TOKENS = 4096

RAW_DIR = ROOT / "data" / "raw"
PHASE0_DIR = ROOT / "data" / "agentic" / "phase0"
PHASE1_DIR = ROOT / "data" / "agentic" / "phase1"
OUTPUT_DIR = ROOT / "data" / "agentic" / "lev"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

with open(ROOT / "data" / "agentic" / "dev_test_split.json") as f:
    SPLIT = json.load(f)

with open(ROOT / "data" / "paper_links.json") as f:
    PAPER_LINKS = json.load(f)

SPDX_PATH = ROOT / "experiments" / "validators" / "_spdx_cache.json"
SPDX = {}
if SPDX_PATH.exists():
    with open(SPDX_PATH) as f:
        SPDX = json.load(f)

client = anthropic.Anthropic()

# Field groups mapping
FIELD_GROUPS = {
    "core": {
        "fields": ["name", "description", "url", "license", "creator",
                    "publisher", "datePublished", "inLanguage", "citeAs", "isLiveDataset"],
        "triage_key": None,  # always extract core fields
        "fallback_sections": ["abstract", "introduction", "data availability"],
    },
    "collection": {
        "fields": ["rai:dataCollection", "rai:dataCollectionType",
                    "rai:dataCollectionMissingData", "rai:dataCollectionRawData",
                    "rai:dataCollectionTimeframe"],
        "triage_key": "G3_collection",
        "fallback_sections": ["method", "data collection", "dataset", "corpus"],
    },
    "annotation": {
        "fields": ["rai:dataAnnotationProtocol", "rai:dataAnnotationPlatform",
                    "rai:dataAnnotationAnalysis", "rai:annotationsPerItem",
                    "rai:annotatorDemographics", "rai:machineAnnotationTools"],
        "triage_key": "G4_annotation",
        "fallback_sections": ["annotation", "labeling", "human evaluation", "crowdsourc"],
    },
    "impact": {
        "fields": ["rai:dataBiases", "rai:dataLimitations", "rai:dataSocialImpact",
                    "rai:personalSensitiveInformation", "rai:dataUseCases",
                    "rai:dataReleaseMaintenancePlan"],
        "triage_key": "G5_rai",
        "fallback_sections": ["ethic", "limitation", "broader impact", "discussion", "bias", "social"],
    },
    "processing": {
        "fields": ["rai:dataImputationProtocol", "rai:dataManipulationProtocol",
                    "rai:dataPreprocessingProtocol"],
        "triage_key": "G6_processing",
        "fallback_sections": ["preprocess", "data preparation", "filtering", "cleaning"],
    },
}

ALL_FIELDS = []
for group in ["core", "collection", "annotation", "impact", "processing"]:
    ALL_FIELDS.extend(FIELD_GROUPS[group]["fields"])


# ═══════════════════════════════════════════════════════════════
# LOCATE: Extract targeted section text per field group
# ═══════════════════════════════════════════════════════════════

def extract_paper_text(ds_id):
    """Full paper text for fallback."""
    pdf_path = RAW_DIR / f"{ds_id}.pdf"
    if not pdf_path.exists():
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
    # Strip references
    for pattern in [r'\n\s*References\s*\n', r'\n\s*REFERENCES\s*\n', r'\n\s*Bibliography\s*\n']:
        match = re.search(pattern, text)
        if match and match.start() > len(text) * 0.5:
            text = text[:match.start()]
            break
    return text.strip()


def locate_sections(ds_id, full_text):
    """LOCATE step: use Phase 1 triage + Phase 0 chunks to get targeted text per group."""

    # Load triage (section names per group from Gemini)
    triage = {}
    triage_path = PHASE1_DIR / f"{ds_id}.json"
    if triage_path.exists():
        with open(triage_path) as f:
            triage_data = json.load(f)
        triage = triage_data.get("triage", {})

    # Load Phase 0 chunks (section-level text)
    chunks = []
    phase0_path = PHASE0_DIR / f"{ds_id}.json"
    if phase0_path.exists():
        with open(phase0_path) as f:
            phase0_data = json.load(f)
        chunks = phase0_data.get("chunks", [])

    # Build section index: section_name -> concatenated text
    section_text = defaultdict(str)
    for chunk in chunks:
        section = chunk.get("section", "unknown").strip()
        text = chunk.get("text", "")
        if section and text:
            section_text[section.upper()] += " " + text

    # For each field group, extract targeted sections
    group_texts = {}
    for group_name, group_cfg in FIELD_GROUPS.items():
        triage_key = group_cfg["triage_key"]
        triage_info = triage.get(triage_key, {}) if triage_key else {}
        triage_sections = [s.upper() for s in triage_info.get("sections", [])]
        fallback_keywords = group_cfg["fallback_sections"]

        # Collect matching section texts
        matched_text = []

        # Method 1: Use triage-identified sections
        for triage_sec in triage_sections:
            for sec_name, sec_text in section_text.items():
                if triage_sec in sec_name or sec_name in triage_sec:
                    matched_text.append(sec_text)

        # Method 2: Fallback keyword matching if triage found nothing
        if not matched_text:
            for sec_name, sec_text in section_text.items():
                sec_lower = sec_name.lower()
                if any(kw in sec_lower for kw in fallback_keywords):
                    matched_text.append(sec_text)

        # Core fields always get abstract + intro + first 20% of paper
        if group_name == "core":
            # Add abstract and intro explicitly
            for sec_name, sec_text in section_text.items():
                if any(kw in sec_name.lower() for kw in ["abstract", "introduction", "1 intro"]):
                    if sec_text not in matched_text:
                        matched_text.insert(0, sec_text)
            # Also add first 20% of full paper for things like title, authors
            first_chunk = full_text[:len(full_text) // 5] if full_text else ""
            if first_chunk:
                matched_text.insert(0, first_chunk)

        combined = "\n\n".join(matched_text)

        # Ensure minimum context — if too short, use more of the paper
        if len(combined) < 2000 and full_text:
            # Fallback: use first 50% of paper for this group
            combined = full_text[:len(full_text) // 2]

        # Cap at 60K chars (~15K tokens) per group to keep costs down
        if len(combined) > 60000:
            combined = combined[:60000]

        group_texts[group_name] = combined

    return group_texts, triage


# ═══════════════════════════════════════════════════════════════
# EXTRACT: Targeted Claude calls per field group
# ═══════════════════════════════════════════════════════════════

# Per-group system prompts (focused instructions)
GROUP_SYSTEM_PROMPTS = {
    "core": """You are an expert at extracting general metadata from ML dataset papers.
Extract ONLY the fields listed below. Use null for any field not explicitly stated in the paper.
Do not guess or fabricate values.

Field definitions:
- name: Dataset name as stated in the paper
- description: Brief description (1-3 sentences)
- url: URL where the dataset can be accessed
- license: Distribution license (e.g., MIT, CC-BY-4.0). Return null if not stated.
- creator: Dataset creator(s). Format: "Name1, Name2 (Organization)"
- publisher: Organization that published/funded the dataset. NOT the conference venue.
- datePublished: Dataset release date (YYYY or YYYY-MM-DD). Not the arxiv submission date.
- inLanguage: Content language(s), ISO codes (e.g., "en")
- citeAs: Recommended citation format
- isLiveDataset: "Yes" if actively updated, "No" if static, null if unknown""",

    "collection": """You are an expert at extracting data collection metadata from ML dataset papers.
Extract ONLY the fields listed below. Use null for any field not explicitly discussed.

Field definitions (from the Croissant RAI specification):
- rai:dataCollection: Description of the data collection process
- rai:dataCollectionType: Choose from: Surveys, Secondary Data analysis, Physical data collection, Direct measurement, Document analysis, Manual Human Curator, Software Collection, Experiments, Web Scraping, Web API, Focus groups, Self-reporting, Customer feedback data, User-generated content data, Passive Data Collection, Others
- rai:dataCollectionMissingData: How missing data was handled. Only if explicitly discussed.
- rai:dataCollectionRawData: Description of the raw/source data
- rai:dataCollectionTimeframe: When data was collected (start/end dates)""",

    "annotation": """You are an expert at extracting annotation metadata from ML dataset papers.
Extract ONLY the fields listed below. Use null for any field not discussed.
This is ONLY about the labeling/annotation process. Do NOT include data collection or preprocessing.

Field definitions (from the Croissant RAI specification):
- rai:dataAnnotationProtocol: How labels/ratings were created: task, instructions, workforce, QC
- rai:dataAnnotationPlatform: Platform used (e.g., Amazon MTurk, Label Studio)
- rai:dataAnnotationAnalysis: Annotation quality analysis: agreement metrics, validation
- rai:annotationsPerItem: Number of human labels per data item
- rai:annotatorDemographics: Demographics of annotators
- rai:machineAnnotationTools: ML tools used in annotation (e.g., NER tools, auto-labelers)""",

    "impact": """You are an expert at extracting responsible AI metadata from ML dataset papers.
Extract ONLY the fields listed below. Use null for any field not explicitly discussed.
Look in Ethics, Limitations, Broader Impact, and Discussion sections.

IMPORTANT: rai:dataReleaseMaintenancePlan is the most commonly hallucinated field.
Return null unless the paper EXPLICITLY mentions versioning, update schedules, or maintenance plans.
For rai:dataBiases, only extract biases the authors explicitly discuss. No generic bias warnings.

Field definitions (from the Croissant RAI specification):
- rai:dataBiases: Known biases explicitly discussed by the authors
- rai:dataLimitations: Known limitations and non-recommended uses
- rai:dataSocialImpact: Social impact considerations
- rai:personalSensitiveInformation: Sensitive attributes collected (gender, age, geography, etc.)
- rai:dataUseCases: Intended use cases (Training, Testing, Fine-tuning, etc.)
- rai:dataReleaseMaintenancePlan: Versioning, update plans, deprecation. Most likely: null""",

    "processing": """You are an expert at extracting data processing metadata from ML dataset papers.
Extract ONLY the fields listed below. Use null for any field not discussed.
Distinguish carefully between: preprocessing (making data ML-ready), manipulation (post-preprocessing changes), and imputation (filling missing values).

Field definitions (from the Croissant RAI specification):
- rai:dataImputationProtocol: How missing values were imputed/filled
- rai:dataManipulationProtocol: Post-preprocessing modifications: augmentation, balancing, sampling
- rai:dataPreprocessingProtocol: Steps to make data ML-ready: filtering, cleaning, normalization""",
}

# User prompt template per group
GROUP_USER_PROMPT = """Extract the following fields from the paper section below.
For each field, provide "value" and "evidence" (a brief quote from the text supporting your extraction).
For null fields: {{"value": null, "evidence": null}}

Return ONLY valid JSON with these keys: %s

PAPER SECTION:
%s"""


def parse_json_response(raw_text):
    """Parse JSON from Claude's response."""
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


def call_claude(system_prompt, user_prompt, max_tokens=MAX_TOKENS):
    """Call Claude with retry logic."""
    backoff = [5, 15, 45]
    for attempt in range(3):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=max_tokens,
                temperature=TEMPERATURE,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )
            result = parse_json_response(response.content[0].text)
            usage = {"input": response.usage.input_tokens, "output": response.usage.output_tokens}
            return result, usage
        except anthropic.RateLimitError:
            wait = backoff[attempt] if attempt < len(backoff) else 60
            print(f"      Rate limited. Waiting {wait}s... (attempt {attempt + 1}/3)")
            time.sleep(wait)
        except anthropic.APIStatusError as e:
            if e.status_code >= 500:
                wait = backoff[attempt] if attempt < len(backoff) else 60
                print(f"      Server error ({e.status_code}). Waiting {wait}s... (attempt {attempt + 1}/3)")
                time.sleep(wait)
            else:
                raise
        except json.JSONDecodeError:
            if attempt < 2:
                print(f"      JSON parse failed. Retrying... (attempt {attempt + 1}/3)")
                time.sleep(backoff[attempt])
            else:
                raise
    raise Exception("All 3 retry attempts failed")


def extract_group(group_name, section_text, fields):
    """EXTRACT step: one Claude call for one field group."""
    system = GROUP_SYSTEM_PROMPTS[group_name]

    # Build field schema for the prompt
    field_schema_parts = []
    for f in fields:
        field_schema_parts.append(f'"{f}": {{"value": "string or null", "evidence": "quote or null"}}')
    schema_str = "{\n  " + ",\n  ".join(field_schema_parts) + "\n}"

    user = GROUP_USER_PROMPT % (schema_str, section_text)

    result, usage = call_claude(system, user)

    # Parse value/evidence structure
    extraction = {}
    evidence = {}
    for field in fields:
        entry = result.get(field, {})
        if isinstance(entry, dict):
            extraction[field] = entry.get("value")
            evidence[field] = entry.get("evidence")
        else:
            extraction[field] = entry
            evidence[field] = None

    return extraction, evidence, usage


# ═══════════════════════════════════════════════════════════════
# VERIFY: Validation + enrichment + confidence
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


def enrich(ds_id, extraction):
    """Cross-document enrichment from HuggingFace and Semantic Scholar."""
    enrichments = {}
    hf_id = ds_id.replace("_", "/", 1)

    # HuggingFace
    try:
        url = f"https://huggingface.co/api/datasets/{hf_id}"
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "CroissantMiner/2.0")
        resp = urllib.request.urlopen(req, timeout=10)
        hf_data = json.loads(resp.read())

        for field, hf_key in [("license", "license"), ("inLanguage", "language")]:
            current = extraction.get(field)
            if not current or str(current).strip().lower() in ("null", "none", ""):
                val = hf_data.get("cardData", {}).get(hf_key)
                if val:
                    enrichments[field] = ", ".join(val) if isinstance(val, list) else str(val)

        if not extraction.get("url") or str(extraction.get("url")).strip().lower() in ("null", "none", ""):
            enrichments["url"] = f"https://huggingface.co/datasets/{hf_id}"
    except Exception:
        pass

    # Semantic Scholar for citeAs
    if not extraction.get("citeAs") or str(extraction.get("citeAs")).strip().lower() in ("null", "none", ""):
        name = extraction.get("name", ds_id)
        if name:
            try:
                query = urllib.parse.quote(str(name))
                url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={query}&limit=1&fields=title,citationStyles"
                req = urllib.request.Request(url)
                req.add_header("User-Agent", "CroissantMiner/2.0")
                resp = urllib.request.urlopen(req, timeout=10)
                data = json.loads(resp.read())
                papers = data.get("data", [])
                if papers:
                    bibtex = papers[0].get("citationStyles", {}).get("bibtex", "")
                    if bibtex:
                        enrichments["citeAs"] = bibtex
            except Exception:
                pass

    for field, val in enrichments.items():
        extraction[field] = val
    return extraction, enrichments


def validate_and_score(extraction, evidence, enrichments, triage):
    """VERIFY step: schema validation + confidence scoring."""
    fields = {}
    for field in ALL_FIELDS:
        val = extraction.get(field)

        # Normalize nulls
        if val is not None and isinstance(val, str) and val.strip().lower() in ("", "null", "none", "n/a", "not applicable", "[null]", "[null - not found in paper]"):
            val = None
        if isinstance(val, list):
            val = ", ".join(str(x) for x in val)
        if field == "license" and val:
            normalized = LICENSE_MAP.get(str(val).strip().lower())
            if normalized:
                val = normalized
        if field == "url" and val and not re.match(r'https?://', str(val)):
            val = f"https://{val}"

        if val is None:
            fields[field] = {"value": None, "confidence": 0.0, "status": "NULL", "source": "absent"}
            continue

        confidence = 0.8
        source = "extraction"

        # Evidence boost
        field_ev = evidence.get(field)
        has_ev = field_ev is not None and str(field_ev).strip() not in ("", "null", "None")
        if has_ev:
            confidence = min(confidence + 0.15, 1.0)

        # Enrichment source
        if field in enrichments:
            source = "enrichment"
            confidence = 0.7

        # Triage alignment penalty
        for group_name, group_cfg in FIELD_GROUPS.items():
            if field in group_cfg["fields"]:
                triage_key = group_cfg["triage_key"]
                if triage_key:
                    triage_info = triage.get(triage_key, {})
                    if triage_info.get("presence") == "unlikely":
                        confidence = min(confidence, 0.5)
                break

        status = "VERIFIED" if confidence >= 0.7 else ("UNCERTAIN" if confidence >= 0.4 else "LOW_CONFIDENCE")

        entry = {"value": val, "confidence": round(confidence, 2), "status": status, "source": source}
        if has_ev:
            entry["evidence"] = field_ev
        fields[field] = entry

    return fields


# ═══════════════════════════════════════════════════════════════
# MAIN PIPELINE
# ═══════════════════════════════════════════════════════════════

def process_paper(ds_id):
    """Run full LEV pipeline on one paper."""
    t0 = time.time()
    total_usage = {"input": 0, "output": 0}

    # Get full paper text (for fallback)
    full_text = extract_paper_text(ds_id)
    if not full_text:
        print(f"  SKIP: no PDF for {ds_id}")
        return None

    # LOCATE: get targeted section text per group
    group_texts, triage = locate_sections(ds_id, full_text)

    # EXTRACT: 5 independent Claude calls
    all_extraction = {}
    all_evidence = {}
    group_stats = {}

    for group_name in ["core", "collection", "annotation", "impact", "processing"]:
        section_text = group_texts.get(group_name, "")
        fields = FIELD_GROUPS[group_name]["fields"]

        if not section_text.strip():
            # No relevant sections found — set all fields to null
            for f in fields:
                all_extraction[f] = None
                all_evidence[f] = None
            group_stats[group_name] = {"tokens_in": 0, "tokens_out": 0, "section_chars": 0}
            continue

        try:
            extraction, evidence, usage = extract_group(group_name, section_text, fields)
            all_extraction.update(extraction)
            all_evidence.update(evidence)
            total_usage["input"] += usage["input"]
            total_usage["output"] += usage["output"]
            group_stats[group_name] = {
                "tokens_in": usage["input"],
                "tokens_out": usage["output"],
                "section_chars": len(section_text),
            }
        except Exception as e:
            print(f"    {group_name} FAILED: {str(e)[:50]}")
            for f in fields:
                all_extraction[f] = None
                all_evidence[f] = None
            group_stats[group_name] = {"error": str(e)[:80]}

        time.sleep(0.3)  # rate limit between calls

    # VERIFY: enrichment + validation + confidence
    all_extraction, enrichments = enrich(ds_id, all_extraction)
    fields = validate_and_score(all_extraction, all_evidence, enrichments, triage)

    # Stats
    elapsed = time.time() - t0
    extracted = sum(1 for f in fields.values() if f["status"] != "NULL")
    verified = sum(1 for f in fields.values() if f["status"] == "VERIFIED")
    with_ev = sum(1 for f in fields.values() if f.get("evidence") is not None)
    cost = total_usage["input"] / 1e6 * 3.0 + total_usage["output"] / 1e6 * 15.0

    # Save
    out_dir = OUTPUT_DIR / ds_id
    out_dir.mkdir(parents=True, exist_ok=True)

    output = {
        "paper_id": ds_id,
        "split": "dev" if ds_id in SPLIT["dev"] else "test",
        "fields": fields,
        "paper_stats": {
            "fields_extracted": extracted,
            "fields_null": 30 - extracted,
            "fields_verified": verified,
            "avg_confidence": round(sum(f["confidence"] for f in fields.values() if f["status"] != "NULL") / max(extracted, 1), 3),
        },
        "_meta": {
            "model": MODEL,
            "temperature": TEMPERATURE,
            "pipeline": "lev",
            "usage": total_usage,
            "cost_usd": round(cost, 4),
            "enrichments": list(enrichments.keys()),
            "evidence_count": with_ev,
            "evidence_coverage": round(with_ev / max(extracted, 1) * 100, 1),
            "group_stats": group_stats,
            "elapsed_seconds": round(elapsed, 1),
        }
    }

    with open(out_dir / "full_result.json", "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # Flat extraction for evaluation
    flat = {field: fields[field]["value"] for field in ALL_FIELDS}
    with open(out_dir / "extraction.json", "w") as f:
        json.dump(flat, f, indent=2, ensure_ascii=False)

    return output



# ═══════════════════════════════════════════════════════════════
# BATCH MODE
# ═══════════════════════════════════════════════════════════════

def run_batch(papers):
    """Run LEV pipeline using batch API for all extraction calls."""
    import urllib.parse

    print(f"  Step 1: LOCATE — extracting section text for {len(papers)} papers...")
    paper_data = {}  # ds_id -> (group_texts, triage, full_text)
    for ds_id in papers:
        if (OUTPUT_DIR / ds_id / "full_result.json").exists():
            continue
        full_text = extract_paper_text(ds_id)
        if not full_text:
            continue
        group_texts, triage = locate_sections(ds_id, full_text)
        paper_data[ds_id] = (group_texts, triage, full_text)

    print(f"  Located sections for {len(paper_data)} papers")

    if not paper_data:
        print("  No papers to process!")
        return

    # Step 2: Build batch requests (5 groups × N papers)
    print(f"  Step 2: EXTRACT — building batch requests...")
    requests = []
    safe_to_ds = {}

    for ds_id, (group_texts, triage, full_text) in paper_data.items():
        safe_ds = re.sub(r'[^a-zA-Z0-9_-]', '_', ds_id)[:50]
        safe_to_ds[safe_ds] = ds_id

        for group_name in ["core", "collection", "annotation", "impact", "processing"]:
            section_text = group_texts.get(group_name, "")
            if not section_text.strip():
                continue

            fields = FIELD_GROUPS[group_name]["fields"]
            system = GROUP_SYSTEM_PROMPTS[group_name]

            field_schema_parts = []
            for f in fields:
                field_schema_parts.append(f'"{f}": {{"value": "string or null", "evidence": "quote or null"}}')
            schema_str = "{\n  " + ",\n  ".join(field_schema_parts) + "\n}"
            user = GROUP_USER_PROMPT % (schema_str, section_text)

            custom_id = f"{safe_ds}___{group_name}"
            if len(custom_id) > 64:
                custom_id = custom_id[:64]

            requests.append({
                "custom_id": custom_id,
                "params": {
                    "model": MODEL,
                    "max_tokens": MAX_TOKENS,
                    "temperature": TEMPERATURE,
                    "system": [{"type": "text", "text": system}],
                    "messages": [{"role": "user", "content": user}]
                }
            })

    print(f"  Submitting batch: {len(requests)} requests ({len(paper_data)} papers × 5 groups)")

    batch = client.messages.batches.create(requests=requests)
    print(f"  Batch ID: {batch.id}")

    # Save metadata
    with open(OUTPUT_DIR / "_batch.json", "w") as f:
        json.dump({
            "batch_id": batch.id,
            "safe_to_ds": safe_to_ds,
            "request_count": len(requests),
            "submitted_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }, f, indent=2)

    # Poll
    print(f"  Waiting for batch to complete...")
    while True:
        time.sleep(30)
        batch = client.messages.batches.retrieve(batch.id)
        counts = batch.request_counts
        done = counts.succeeded + counts.errored + counts.expired
        print(f"    {batch.processing_status}: {done}/{len(requests)} done "
              f"(ok={counts.succeeded}, err={counts.errored})")
        if batch.processing_status == "ended":
            break

    # Step 3: Retrieve and reassemble results
    print(f"\n  Step 3: Retrieving results...")
    group_results = {}  # ds_id -> {group_name: (extraction, evidence, usage)}
    total_usage = {"input": 0, "output": 0}

    for result in client.messages.batches.results(batch.id):
        cid = result.custom_id
        parts = cid.split("___")
        if len(parts) != 2:
            continue
        safe_ds, group_name = parts
        ds_id = safe_to_ds.get(safe_ds, safe_ds)

        if result.result.type == "succeeded":
            msg = result.result.message
            usage = {"input": msg.usage.input_tokens, "output": msg.usage.output_tokens}
            total_usage["input"] += usage["input"]
            total_usage["output"] += usage["output"]

            try:
                parsed = parse_json_response(msg.content[0].text)
                fields = FIELD_GROUPS[group_name]["fields"]
                extraction = {}
                evidence = {}
                for field in fields:
                    entry = parsed.get(field, {})
                    if isinstance(entry, dict):
                        extraction[field] = entry.get("value")
                        evidence[field] = entry.get("evidence")
                    else:
                        extraction[field] = entry
                        evidence[field] = None

                if ds_id not in group_results:
                    group_results[ds_id] = {}
                group_results[ds_id][group_name] = (extraction, evidence, usage)
            except Exception as e:
                print(f"    Parse failed: {ds_id}/{group_name}: {str(e)[:40]}")
        else:
            print(f"    Failed: {ds_id}/{group_name}")

    print(f"  Retrieved results for {len(group_results)} papers")

    # Step 4: VERIFY — merge groups, enrich, validate, save
    print(f"\n  Step 4: VERIFY — enrichment + validation...")
    ok = fail = total_extracted = total_verified = 0

    for i, ds_id in enumerate(sorted(paper_data.keys())):
        if (OUTPUT_DIR / ds_id / "full_result.json").exists():
            ok += 1
            continue

        groups = group_results.get(ds_id, {})
        group_texts, triage, full_text = paper_data[ds_id]

        all_extraction = {}
        all_evidence = {}
        group_stats = {}
        paper_usage = {"input": 0, "output": 0}

        for group_name in ["core", "collection", "annotation", "impact", "processing"]:
            fields = FIELD_GROUPS[group_name]["fields"]
            if group_name in groups:
                ext, ev, usage = groups[group_name]
                all_extraction.update(ext)
                all_evidence.update(ev)
                paper_usage["input"] += usage["input"]
                paper_usage["output"] += usage["output"]
                group_stats[group_name] = {
                    "tokens_in": usage["input"], "tokens_out": usage["output"],
                    "section_chars": len(group_texts.get(group_name, "")),
                }
            else:
                for f in fields:
                    all_extraction[f] = None
                    all_evidence[f] = None
                group_stats[group_name] = {"skipped": True}

        # Enrichment
        all_extraction, enrichments = enrich(ds_id, all_extraction)

        # Validation
        fields = validate_and_score(all_extraction, all_evidence, enrichments, triage)

        # Stats
        extracted = sum(1 for f in fields.values() if f["status"] != "NULL")
        verified = sum(1 for f in fields.values() if f["status"] == "VERIFIED")
        with_ev = sum(1 for f in fields.values() if f.get("evidence") is not None)
        cost = paper_usage["input"] / 1e6 * 1.5 + paper_usage["output"] / 1e6 * 7.5

        # Save
        out_dir = OUTPUT_DIR / ds_id
        out_dir.mkdir(parents=True, exist_ok=True)

        output = {
            "paper_id": ds_id,
            "split": "dev" if ds_id in SPLIT["dev"] else "test",
            "fields": fields,
            "paper_stats": {
                "fields_extracted": extracted, "fields_null": 30 - extracted,
                "fields_verified": verified,
                "avg_confidence": round(sum(f["confidence"] for f in fields.values() if f["status"] != "NULL") / max(extracted, 1), 3),
            },
            "_meta": {
                "model": MODEL, "temperature": TEMPERATURE, "pipeline": "lev",
                "usage": paper_usage, "cost_usd": round(cost, 4),
                "enrichments": list(enrichments.keys()),
                "evidence_count": with_ev,
                "evidence_coverage": round(with_ev / max(extracted, 1) * 100, 1),
                "group_stats": group_stats, "batch_mode": True,
            }
        }
        with open(out_dir / "full_result.json", "w") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        flat = {field: fields[field]["value"] for field in ALL_FIELDS}
        with open(out_dir / "extraction.json", "w") as f:
            json.dump(flat, f, indent=2, ensure_ascii=False)

        ok += 1
        total_extracted += extracted
        total_verified += verified

        if (i + 1) % 25 == 0:
            print(f"    [{i+1}/{len(paper_data)}] {ok} processed")

    # Summary
    batch_cost = total_usage["input"] / 1e6 * 1.5 + total_usage["output"] / 1e6 * 7.5
    total_fields = ok * 30

    print(f"\n{'=' * 70}")
    print(f"LEV BATCH PIPELINE COMPLETE")
    print(f"{'=' * 70}")
    print(f"Papers: {ok} OK, {fail} failed")
    print(f"Fields: {total_extracted}/{total_fields} ({total_extracted/max(total_fields,1)*100:.1f}%)")
    print(f"Verified: {total_verified}/{total_fields} ({total_verified/max(total_fields,1)*100:.1f}%)")
    print(f"Tokens: {total_usage['input']:,} in, {total_usage['output']:,} out")
    print(f"Cost: ${batch_cost:.2f} (batch pricing)")

    summary = {
        "papers_ok": ok, "papers_failed": fail,
        "total_extracted": total_extracted, "total_verified": total_verified,
        "fill_rate": round(total_extracted / max(total_fields, 1) * 100, 1),
        "usage": total_usage, "cost_usd": round(batch_cost, 2),
        "batch_mode": True,
    }
    with open(OUTPUT_DIR / "_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    return summary



def main():
    parser = argparse.ArgumentParser(description="CroissantMiner LEV Agentic Pipeline")
    parser.add_argument("--dev-only", action="store_true", help="Process only 15 dev papers")
    parser.add_argument("--paper", type=str, help="Process a single paper")
    parser.add_argument("--batch", action="store_true", help="Use batch API (half price)")
    args = parser.parse_args()

    if args.paper:
        papers = [args.paper]
    elif args.dev_only:
        papers = sorted(SPLIT["dev"])
    else:
        papers = sorted(SPLIT["dev"] + SPLIT["test"])

    if args.batch:
        print(f"{'=' * 70}")
        print(f"LEV PIPELINE — BATCH MODE")
        print(f"{'=' * 70}")
        print(f"Papers: {len(papers)}")
        print(f"{'=' * 70}")
        run_batch(papers)
        return

    print(f"{'=' * 70}")
    print(f"CROISSANTMINER LEV PIPELINE (Locate-Extract-Verify)")
    print(f"{'=' * 70}")
    print(f"Papers: {len(papers)}")
    print(f"Architecture: 5 targeted Claude calls per paper")
    print(f"{'=' * 70}")

    total_usage = {"input": 0, "output": 0}
    ok = fail = total_extracted = total_verified = 0

    for i, ds_id in enumerate(papers):
        out_path = OUTPUT_DIR / ds_id / "full_result.json"
        if out_path.exists() and not args.paper:
            ok += 1
            if (i + 1) % 25 == 0:
                print(f"  [{i+1}/{len(papers)}] {ok} done (skipping existing)")
            continue

        try:
            result = process_paper(ds_id)
            if result:
                ok += 1
                stats = result["paper_stats"]
                meta = result["_meta"]
                total_usage["input"] += meta["usage"]["input"]
                total_usage["output"] += meta["usage"]["output"]
                total_extracted += stats["fields_extracted"]
                total_verified += stats["fields_verified"]
                print(f"  [{i+1}/{len(papers)}] {ds_id}: {stats['fields_extracted']}/30, "
                      f"${meta['cost_usd']:.3f}, ev={meta['evidence_coverage']:.0f}%, "
                      f"{meta['elapsed_seconds']:.0f}s")
            else:
                fail += 1
        except Exception as e:
            print(f"  [{i+1}/{len(papers)}] {ds_id}: FAILED ({str(e)[:60]})")
            fail += 1

        time.sleep(0.3)

    total_cost = total_usage["input"] / 1e6 * 3.0 + total_usage["output"] / 1e6 * 15.0
    total_fields = ok * 30

    print(f"\n{'=' * 70}")
    print(f"SUMMARY")
    print(f"{'=' * 70}")
    print(f"Papers: {ok} OK, {fail} failed")
    print(f"Fields: {total_extracted}/{total_fields} ({total_extracted/max(total_fields,1)*100:.1f}%)")
    print(f"Verified: {total_verified}/{total_fields} ({total_verified/max(total_fields,1)*100:.1f}%)")
    print(f"Cost: ${total_cost:.2f}")
    print(f"Output: {OUTPUT_DIR}/")

    summary = {
        "papers_ok": ok, "papers_failed": fail,
        "total_extracted": total_extracted, "total_verified": total_verified,
        "fill_rate": round(total_extracted / max(total_fields, 1) * 100, 1),
        "usage": total_usage, "cost_usd": round(total_cost, 2),
    }
    with open(OUTPUT_DIR / "_summary.json", "w") as f:
        json.dump(summary, f, indent=2)


if __name__ == "__main__":
    main()
