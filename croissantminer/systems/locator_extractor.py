#!/usr/bin/env python3
"""CroissantMiner LEV (Locate-Extract-Verify) pipeline.

LOCATE  Reuse Phase 1 Gemini-Flash triage (section names per field group) +
        Phase 0 section chunks; build a targeted text buffer per group with
        fallback keyword matching if triage is empty.
EXTRACT Five independent LLM calls (one per field group) with specialist
        system prompts and a {value, evidence} schema.
VERIFY  Cross-document enrichment (HuggingFace + Semantic Scholar), schema
        validation, confidence scoring.

Output schema (canonical):
  {"dataset_id", "model", "extraction" (flat 30 fields), "usage", "valid",
   "_meta": {provenance, pipeline="agentic_lev", extraction_details,
             group_stats, paper_stats, ...}}

Usage:
  python scripts/agentic_lev.py --backbone sonnet-4-5 --paper AI4Math_MathVista
  python scripts/agentic_lev.py --backbone gpt-5.4 --dev-only
  python scripts/agentic_lev.py --backbone sonnet-4-5 --batch   # Anthropic only
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv

from .helpers import (
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
    write_canonical_output,
)

load_dotenv(ROOT / ".env")

SCRIPT_NAME = "scripts/agentic_lev.py"
MAX_TOKENS_GROUP = 4096
MAX_TOKENS_GROUP_V7 = 8192  # increased cap for v7 to avoid evidence-quote truncation
MAX_TOKENS_LOCATOR = 2048
LOCATOR_CHAR_CAP = 200_000  # cap full-paper input to locator at 200K chars
GROUP_CHAR_CAP = 60_000
GROUP_MIN_CONTEXT = 2_000

PHASE0_DIR = ROOT / "data" / "agentic" / "phase0"
PHASE1_DIR = ROOT / "data" / "agentic" / "phase1"

# The paper's dev/test split, for benchmark runs; absent in an installed package.
_SPLIT_FILE = ROOT / "data" / "agentic" / "dev_test_split.json"
SPLIT = json.loads(_SPLIT_FILE.read_text()) if _SPLIT_FILE.exists() else {"dev": [], "test": []}


# ── Field groups and prompts ──────────────────────────────────────
FIELD_GROUPS = {
    "core": {
        "fields": ["name", "description", "url", "license", "creator",
                   "publisher", "datePublished", "inLanguage", "citeAs", "isLiveDataset"],
        "triage_key": None,
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
GROUP_ORDER = ["core", "collection", "annotation", "impact", "processing"]
ALL_FIELDS: list[str] = []
for _g in GROUP_ORDER:
    ALL_FIELDS.extend(FIELD_GROUPS[_g]["fields"])


GROUP_SYSTEM_PROMPTS = {
    "core": """You are an expert at extracting general metadata from ML dataset papers.
Extract ONLY the fields listed below. Use null for any field not explicitly stated in the paper.
Do not guess or fabricate values.

Field definitions:
- name: Dataset name as stated in the paper
- description: Brief description (1-3 sentences)
- url: URL where the dataset can be accessed
- license: Distribution license (e.g., MIT, CC-BY-4.0). Return null if not stated.
- creator: Dataset authors or creating team
- publisher: The organization that funded or released the dataset; this may be a conference or shared task in some cases
- datePublished: The date the dataset was released to users (YYYY or YYYY-MM-DD); may differ from the arxiv submission date
- inLanguage: Content language(s), ISO codes (e.g., "en")
- citeAs: Recommended citation format if provided in the paper. If absent, return null — the pipeline fills this from external sources downstream.
- isLiveDataset: "Yes" if actively updated, "No" if static, null if unknown""",

    "collection": """You are an expert at extracting data collection metadata from ML dataset papers.
Extract ONLY the fields listed below. Use null for any field not explicitly discussed.

Field definitions (from the Croissant RAI specification):
- rai:dataCollection: Description of the data collection process
- rai:dataCollectionType: Choose from: Surveys, Secondary Data analysis, Physical data collection, Direct measurement, Document analysis, Manual Human Curator, Software Collection, Experiments, Web Scraping, Web API, Focus groups, Self-reporting, Customer feedback data, User-generated content data, Passive Data Collection, Others.
  Prefer "Web Scraping" over "Web API" when data was harvested without authenticated endpoints. Prefer "Secondary Data analysis" when data was reused from an existing corpus rather than freshly gathered.
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

Field definitions (from the Croissant RAI specification):
- rai:dataBiases: Description of biases in the dataset, if applicable
- rai:dataLimitations: Known limitations (e.g., data generalization limits, quality issues) and non-recommended uses
- rai:dataSocialImpact: Discussion of social implications, if applicable
- rai:personalSensitiveInformation: Any sensitive human attribute(s) collected as part of this dataset (e.g., gender, socio-economic status, geography, language, age, culture, experience)
- rai:dataUseCases: Dataset use case(s) (e.g., Training, Testing, Validation, Fine-tuning) and usage guidelines
- rai:dataReleaseMaintenancePlan: Versioning information in terms of the updating timeframe, the maintainers, and the deprecation policies""",

    "processing": """You are an expert at extracting data processing metadata from ML dataset papers.
Extract ONLY the fields listed below. Use null for any field not discussed.
Distinguish carefully between: preprocessing (making data ML-ready), manipulation (post-preprocessing changes), and imputation (filling missing values).

Field definitions (from the Croissant RAI specification):
- rai:dataImputationProtocol: How missing values were imputed/filled
- rai:dataManipulationProtocol: Post-preprocessing modifications: augmentation, balancing, sampling
- rai:dataPreprocessingProtocol: Steps to make data ML-ready: filtering, cleaning, normalization""",
}

GROUP_USER_PROMPT = """Extract the following fields from the paper section below.
For each field, provide "value" and "evidence" (a brief quote from the text supporting your extraction).
For null fields: {{"value": null, "evidence": null}}

Return ONLY valid JSON with these keys: %s

PAPER SECTION:
%s"""


# v2 user prompt: anti-null-bias with few-shot null examples. Phase 3 Fix A
# from the 2026-05-02 V2/LEV iteration plan. Targets failure mode F1
# (null-gold hallucination, ~60%% of LEV-C2 round-0 score=3 cells).
# Variant v5: round-0 prompt + multi-aspect enumeration emphasis (Fix D).
# NOT compounded with Fix A (anti-null prompt) since the v4 compound made things
# significantly worse (Δ=-0.061, p=0.004 reverted). v5 = Fix B (locator gating)
# + Fix D (multi-type enumeration in extractor prompt).
GROUP_USER_PROMPT_V5 = """Extract the following fields from the paper section below.
For each field, provide "value" and "evidence" (a brief quote from the text supporting your extraction).
For null fields: {{"value": null, "evidence": null}}

CRITICAL FOR MULTI-ASPECT FIELDS: be EXHAUSTIVE.

  - rai:dataCollectionType: many datasets combine 2 or 3 collection types.
    List ALL applicable types from the controlled vocabulary, e.g.,
    "Web Scraping | Manual Human Curator | Document analysis", not just the
    primary one.
  - rai:dataLimitations: capture ALL limitations discussed (temporal,
    geographic, quality, scope, generalization, exclusion).
  - rai:dataBiases: capture ALL biases discussed (selection, demographic,
    contamination, source-medium, stylistic, etc.).
  - rai:dataUseCases: list ALL stated use cases (training, testing, validation,
    fine-tuning, benchmarking).

Format multi-aspect values with " | " separator OR comprehensive prose.
Do not omit aspects to keep the answer brief.

Return ONLY valid JSON with these keys: %s

PAPER SECTION:
%s"""


GROUP_USER_PROMPT_V2 = """CRITICAL — DEFAULT TO NULL WHEN UNCERTAIN.

Many Croissant RAI fields are rarely documented in dataset papers. If the
section text does NOT explicitly discuss a field, return null. Do not
generate plausible-sounding content based on what a similar paper might say.
Do not infer from related content. Every non-null extraction must have an
evidence quote that is a near-verbatim sentence from the section text.

EXAMPLE A -- section does NOT discuss the field, so the answer is null:
  Section: "We crowdsourced 10K questions and verified accuracy..."
  Field: rai:dataAnnotationPlatform
  CORRECT: {{"value": null, "evidence": null}}
  WRONG: extracting "Amazon Mechanical Turk" because the section says "crowdsourced"

EXAMPLE B -- section DOES discuss the field, so extract with evidence:
  Section: "Annotations were collected via Amazon Mechanical Turk with 3 workers per item."
  Field: rai:dataAnnotationPlatform
  CORRECT: {{"value": "Amazon Mechanical Turk", "evidence":
    "Annotations were collected via Amazon Mechanical Turk..."}}

EXAMPLE C -- section is silent on imputation, so the field is null:
  Section: "Our dataset contains 50K complete examples."
  Field: rai:dataImputationProtocol
  CORRECT: {{"value": null, "evidence": null}}
  WRONG: extracting any imputation protocol (would be hallucinated)

Now extract the fields below. For each: provide "value" and "evidence" (a
brief quote from the text supporting your extraction). For fields not
discussed in the section: {{"value": null, "evidence": null}}.

Return ONLY valid JSON with these keys: %s

PAPER SECTION:
%s"""

# LEV's specialist prompts differ from the canonical SYSTEM_PROMPT. Hash the
# actual strings the LLM sees so _meta.specialist_prompts_sha256_prefix is an
# honest provenance record (PROMPT_HASH from helpers tracks the canonical
# definitions source, unchanged across LEV-prompt revisions).
SPECIALIST_PROMPTS_HASH = hashlib.sha256(
    json.dumps(
        {"group_system_prompts": GROUP_SYSTEM_PROMPTS,
         "group_user_prompt": GROUP_USER_PROMPT},
        sort_keys=True,
    ).encode()
).hexdigest()[:16]


LICENSE_MAP = {
    "cc-by-4.0": "CC-BY-4.0", "cc by 4.0": "CC-BY-4.0",
    "cc-by-sa-4.0": "CC-BY-SA-4.0", "cc by-sa 4.0": "CC-BY-SA-4.0",
    "cc-by-nc-4.0": "CC-BY-NC-4.0", "cc by-nc 4.0": "CC-BY-NC-4.0",
    "cc-by-nc-sa-4.0": "CC-BY-NC-SA-4.0",
    "cc0-1.0": "CC0-1.0", "cc0": "CC0-1.0", "public domain": "CC0-1.0",
    "mit": "MIT", "mit license": "MIT",
    "apache-2.0": "Apache-2.0", "apache 2.0": "Apache-2.0",
}


# ── Phase 0 / Phase 1 loaders ─────────────────────────────────────
def load_paper_text(ds_id: str) -> str | None:
    text = get_paper_text(ds_id)
    if text is None:
        return None
    return strip_references(text).strip()


def load_triage(ds_id: str) -> dict:
    path = PHASE1_DIR / f"{ds_id}.json"
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f).get("triage", {})


def load_section_text(ds_id: str) -> dict[str, str]:
    path = PHASE0_DIR / f"{ds_id}.json"
    if not path.exists():
        return {}
    with open(path) as f:
        data = json.load(f)
    sections: defaultdict[str, str] = defaultdict(str)
    for chunk in data.get("chunks", []):
        name = str(chunk.get("section", "unknown")).strip().upper()
        text = chunk.get("text", "")
        if name and text:
            sections[name] += " " + text
    return dict(sections)


# ── LOCATE ────────────────────────────────────────────────────────
LOCATOR_SYSTEM_PROMPT = """You are an expert at navigating academic papers about ML datasets. Given a paper's text and a list of available section names, your job is to identify which sections are most relevant for extracting specific groups of metadata fields.

You will return a JSON object with one entry per field group, listing the section names (from the provided list, exact match) that contain content relevant to that group, plus a presence indicator.

Be precise: only include sections that genuinely discuss the topic. If no section discusses a group, return an empty list and presence="unlikely". If discussion is brief or scattered, mark presence="possible". If a clearly dedicated section exists, mark presence="likely"."""


LOCATOR_USER_TEMPLATE = """Paper text (may be truncated for length):

{paper_text}

Available section names in this paper (use these EXACTLY — they are case-sensitive, do not paraphrase):
{section_list}

Identify relevant sections for each of these field groups:

- G3_collection: How the data was collected — sources, methodology, raw data, timeframe, missing data handling.
- G4_annotation: Annotation procedures — labeling protocols, annotator demographics, annotation platforms (MTurk, Label Studio, etc.), per-item annotation counts, machine annotation tools, annotation analysis / quality metrics.
- G5_rai: Responsible-AI considerations — biases, limitations, ethical issues, social impact, sensitive personal information, intended use cases, release maintenance plan.
- G6_processing: Data processing — preprocessing steps, data manipulation/transformation, imputation of missing values.

Return JSON only, in this exact schema:
{{
  "G3_collection": {{"sections": ["EXACT_SECTION_NAME_1", ...], "presence": "likely"|"possible"|"unlikely"}},
  "G4_annotation": {{"sections": [...], "presence": "..."}},
  "G5_rai": {{"sections": [...], "presence": "..."}},
  "G6_processing": {{"sections": [...], "presence": "..."}}
}}"""


def locate_with_llm(cfg, ds_id: str, full_text: str) -> tuple[dict, dict]:
    """LLM-based locator: replaces precomputed Phase 1 Gemini-Flash triage.

    Calls the locator LLM with the full paper text + the list of available
    section names from PHASE0 chunks; the LLM returns a triage dict in the
    same format as load_triage() so the rest of the pipeline is unchanged.

    Returns (triage_dict, usage_dict). On failure, returns ({}, usage) and
    locate_sections() will fall back to keyword-based section selection.
    """
    sections = load_section_text(ds_id)
    section_names = sorted(sections.keys())

    if not section_names:
        return {}, {"input_tokens": 0, "output_tokens": 0}

    section_list = "\n".join(f"- {n}" for n in section_names)
    paper_text = full_text[:LOCATOR_CHAR_CAP]
    user = LOCATOR_USER_TEMPLATE.format(
        paper_text=paper_text,
        section_list=section_list,
    )

    try:
        raw, usage = call_llm(cfg, LOCATOR_SYSTEM_PROMPT, user, MAX_TOKENS_LOCATOR)
        parsed = parse_json_response(raw)
    except Exception as e:
        print(f"    {ds_id}/locator FAILED: {str(e)[:80]} — falling back to keyword search")
        return {}, {"input_tokens": 0, "output_tokens": 0}

    # Normalize: ensure section names match available ones (uppercase compare)
    name_to_canonical = {n.upper(): n for n in section_names}
    triage: dict = {}
    for group_key in ("G3_collection", "G4_annotation", "G5_rai", "G6_processing"):
        entry = parsed.get(group_key, {})
        if not isinstance(entry, dict):
            continue
        raw_sections = entry.get("sections", [])
        if not isinstance(raw_sections, list):
            raw_sections = []
        # Map each LLM-returned name to a canonical section name; drop unknowns.
        canonical_sections: list[str] = []
        for s in raw_sections:
            key = str(s).upper().strip()
            if key in name_to_canonical:
                canonical_sections.append(name_to_canonical[key])
            else:
                # Fuzzy match: substring either way
                for known_upper, known in name_to_canonical.items():
                    if key in known_upper or known_upper in key:
                        canonical_sections.append(known)
                        break
        presence = entry.get("presence", "possible")
        if presence not in ("likely", "possible", "unlikely"):
            presence = "possible"
        triage[group_key] = {"sections": canonical_sections, "presence": presence}

    return triage, usage


def locate_sections_v7(ds_id: str, full_text: str,
                       triage_override: dict | None = None) -> tuple[dict[str, str], dict]:
    """v7 locator output assembly. Fixes 1, 4, 5, 6, 9 from the 2026-05-02 audit:

      1. Stricter section matching — prefer exact upper-case match before
         substring fallback. Reduces wrong-section pickups.
      4. Deduplicate matched sections — never include the same paragraph twice.
      5. Preserve paper order — sections appear in document order, not match
         loop order. Helps the model reason about earlier/later context.
      6. Section metadata in input — each section is prefixed with
         "=== Section: NAME ===" so the extractor can reference positions.
      9. Core-group hack removed — abstract/intro are added via the same
         exact/substring match path; no special prepend of full-text fifth.
    """
    triage = triage_override if triage_override is not None else load_triage(ds_id)
    sections = load_section_text(ds_id)
    section_order = list(sections.keys())  # paper order

    group_texts: dict[str, str] = {}
    for group_name, cfg in FIELD_GROUPS.items():
        triage_key = cfg["triage_key"]
        triage_info = triage.get(triage_key, {}) if triage_key else {}
        triage_sections = [s.upper() for s in triage_info.get("sections", [])]
        fallback = cfg["fallback_sections"]

        # Match step. Build a set of section *names* (not text) to dedup
        # at the section-id level, then assemble in paper order.
        matched_names: set[str] = set()
        # Exact match first
        for target in triage_sections:
            for name in section_order:
                if name == target:
                    matched_names.add(name)
        # Substring match second (target ⊂ name OR name ⊂ target), only for
        # targets that didn't already match exactly.
        unmatched_targets = [t for t in triage_sections
                             if not any(t == n for n in section_order)]
        for target in unmatched_targets:
            for name in section_order:
                if target in name or (len(name) >= 4 and name in target):
                    matched_names.add(name)
        # Keyword fallback if nothing matched
        if not matched_names:
            for name in section_order:
                low = name.lower()
                if any(kw in low for kw in fallback):
                    matched_names.add(name)

        # Core group: also include abstract / introduction by name
        if group_name == "core":
            for name in section_order:
                if any(kw in name.lower() for kw in ("abstract", "introduction", "1 intro")):
                    matched_names.add(name)

        # Assemble in paper order, prefixed with section metadata.
        parts: list[str] = []
        for name in section_order:
            if name in matched_names:
                txt = sections.get(name, "").strip()
                if txt:
                    parts.append(f"=== Section: {name} ===\n{txt}")

        combined = "\n\n".join(parts).strip()
        if len(combined) < GROUP_MIN_CONTEXT and full_text:
            # Fallback: dump first half of paper rather than nothing
            combined = "=== Paper context (locator returned no usable sections) ===\n"
            combined += full_text[: len(full_text) // 2]
        if len(combined) > GROUP_CHAR_CAP:
            combined = combined[:GROUP_CHAR_CAP]
        group_texts[group_name] = combined

    return group_texts, triage


def locate_sections(ds_id: str, full_text: str,
                    triage_override: dict | None = None) -> tuple[dict[str, str], dict]:
    triage = triage_override if triage_override is not None else load_triage(ds_id)
    sections = load_section_text(ds_id)

    group_texts: dict[str, str] = {}
    for group_name, cfg in FIELD_GROUPS.items():
        triage_key = cfg["triage_key"]
        triage_info = triage.get(triage_key, {}) if triage_key else {}
        triage_sections = [s.upper() for s in triage_info.get("sections", [])]
        fallback = cfg["fallback_sections"]

        matched: list[str] = []
        for target in triage_sections:
            for name, text in sections.items():
                if target in name or name in target:
                    matched.append(text)
        if not matched:
            for name, text in sections.items():
                low = name.lower()
                if any(kw in low for kw in fallback):
                    matched.append(text)

        if group_name == "core":
            for name, text in sections.items():
                if any(kw in name.lower() for kw in ("abstract", "introduction", "1 intro")):
                    if text not in matched:
                        matched.insert(0, text)
            if full_text:
                matched.insert(0, full_text[: len(full_text) // 5])

        combined = "\n\n".join(matched).strip()
        if len(combined) < GROUP_MIN_CONTEXT and full_text:
            combined = full_text[: len(full_text) // 2]
        if len(combined) > GROUP_CHAR_CAP:
            combined = combined[:GROUP_CHAR_CAP]
        group_texts[group_name] = combined

    return group_texts, triage


# ── EXTRACT ───────────────────────────────────────────────────────
def _schema_for_group(fields: list[str]) -> str:
    parts = [f'"{f}": {{"value": "string or null", "evidence": "quote or null"}}'
             for f in fields]
    return "{\n  " + ",\n  ".join(parts) + "\n}"


def extract_group_v7(cfg, group_name: str, section_text: str, fields: list[str]):
    """v7 extractor with fixes 7, 8 from the 2026-05-02 audit:

      7. Retry once on JSON parse failure with an explicit schema reminder.
      8. Increased max_tokens from 4096 to 8192 to avoid evidence-quote
         truncation that loses fields silently.

    Uses the v1 round-0 user prompt template (multi-aspect emphasis applies
    via Fix D in v5 only; v7 starts from v1 baseline + locator gating).
    """
    system = GROUP_SYSTEM_PROMPTS[group_name]
    schema = _schema_for_group(fields)
    user = GROUP_USER_PROMPT % (schema, section_text)

    raw, usage = call_llm(cfg, system, user, MAX_TOKENS_GROUP_V7)
    try:
        parsed = parse_json_response(raw)
    except Exception:
        # Retry once with a schema reminder appended
        retry_user = (
            f"Your previous response was not valid JSON. Please try again. "
            f"Return ONLY a valid JSON object with these exact keys: "
            f"{', '.join(fields)}. Each value must follow the schema "
            f"{{\"value\": <string|null>, \"evidence\": <string|null>}}.\n\n"
            f"{user}"
        )
        raw2, usage2 = call_llm(cfg, system, retry_user, MAX_TOKENS_GROUP_V7)
        usage = {"input_tokens": usage["input_tokens"] + usage2["input_tokens"],
                 "output_tokens": usage["output_tokens"] + usage2["output_tokens"]}
        try:
            parsed = parse_json_response(raw2)
        except Exception:
            parsed = {}

    extraction: dict = {}
    evidence: dict = {}
    for field in fields:
        entry = parsed.get(field, {})
        if isinstance(entry, dict):
            extraction[field] = entry.get("value")
            evidence[field] = entry.get("evidence")
        else:
            extraction[field] = entry
            evidence[field] = None
    return extraction, evidence, usage


VERIFY_CORRECT_USER = """You previously extracted some fields from a section but returned NULL for these:
{null_fields}

This was your section context (the same locator output as before):
{section_text}

For each null field above, RE-READ the section carefully and decide:
  - If the section TRULY does not discuss the field, keep it null. Do NOT hallucinate.
  - If the section DOES contain relevant content you missed, extract it now with an evidence quote.

Return JSON: {{"<field_id>": {{"value": "string or null", "evidence": "quote or null"}}, ...}}
ONLY include the fields listed above. No other fields. No prose. JSON only."""


def verify_correct_group(cfg, group_name: str, section_text: str, fields: list[str],
                         current_extraction: dict, current_evidence: dict,
                         triage_presence: str = "possible") -> tuple[dict, dict, dict]:
    """v7 verify+correct phase (Fix 2 from audit).

    Re-checks fields that came back null IF the locator believed the topic
    was 'likely' or 'possible' present in the paper. Skips when locator says
    'unlikely' (Fix B already nulled them anyway). Adds at most 1 extra LLM
    call per group, only when there are nulls worth re-checking.
    """
    if triage_presence == "unlikely":
        return current_extraction, current_evidence, {"input_tokens": 0, "output_tokens": 0}

    null_fields = [f for f in fields
                   if current_extraction.get(f) is None or
                      (isinstance(current_extraction.get(f), str) and
                       not current_extraction[f].strip())]
    if not null_fields:
        return current_extraction, current_evidence, {"input_tokens": 0, "output_tokens": 0}

    system = GROUP_SYSTEM_PROMPTS[group_name]
    user = VERIFY_CORRECT_USER.format(
        null_fields="\n".join(f"  - {f}" for f in null_fields),
        section_text=section_text[:50000],  # cap for verify-prompt
    )
    try:
        raw, usage = call_llm(cfg, system, user, MAX_TOKENS_GROUP_V7)
        parsed = parse_json_response(raw)
    except Exception:
        return current_extraction, current_evidence, {"input_tokens": 0, "output_tokens": 0}

    # Apply only filling (don't overwrite already-filled values)
    for f in null_fields:
        entry = parsed.get(f, {})
        if not isinstance(entry, dict):
            continue
        new_val = entry.get("value")
        if new_val is not None and isinstance(new_val, str) and new_val.strip():
            current_extraction[f] = new_val
            current_evidence[f] = entry.get("evidence")
    return current_extraction, current_evidence, usage


def extract_group(cfg, group_name: str, section_text: str, fields: list[str],
                  prompt_variant: str = "v1"):
    system = GROUP_SYSTEM_PROMPTS[group_name]
    schema = _schema_for_group(fields)
    # v2 and v4 use the anti-null-bias prompt template.
    # v5 uses the multi-aspect enumeration template (NO anti-null wrapping).
    # v6 = v3 prompt (round-0) + tighter section truncation (8K cap, applied below).
    # v3, v4, v5, v6 all apply locator-extractor coupling (in process_paper).
    if prompt_variant == "v5":
        template = GROUP_USER_PROMPT_V5
    elif prompt_variant in ("v2", "v4"):
        template = GROUP_USER_PROMPT_V2
    else:
        template = GROUP_USER_PROMPT
    # v6: tighter section context to focus the extractor on the most-relevant slice.
    if prompt_variant == "v6":
        section_text = section_text[:8000]
    user = template % (schema, section_text)
    raw, usage = call_llm(cfg, system, user, MAX_TOKENS_GROUP)
    parsed = parse_json_response(raw)

    extraction: dict = {}
    evidence: dict = {}
    for field in fields:
        entry = parsed.get(field, {})
        if isinstance(entry, dict):
            extraction[field] = entry.get("value")
            evidence[field] = entry.get("evidence")
        else:
            extraction[field] = entry
            evidence[field] = None
    return extraction, evidence, usage


# ── VERIFY: enrichment + validation ───────────────────────────────
def _is_null(val) -> bool:
    if val is None:
        return True
    if isinstance(val, str) and val.strip().lower() in ("", "null", "none"):
        return True
    return False


def enrich(ds_id: str, extraction: dict) -> tuple[dict, dict]:
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
        if _is_null(extraction.get("inLanguage")):
            lang = card.get("language")
            if lang:
                enrichments["inLanguage"] = ", ".join(lang) if isinstance(lang, list) else str(lang)
        if _is_null(extraction.get("url")):
            enrichments["url"] = f"https://huggingface.co/datasets/{hf_id}"
    except Exception:
        pass

    if _is_null(extraction.get("citeAs")):
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
                    enrichments["citeAs"] = bibtex
        except Exception:
            pass

    for field, val in enrichments.items():
        extraction[field] = val
    return extraction, enrichments


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

        for group_name, gcfg in FIELD_GROUPS.items():
            if field in gcfg["fields"]:
                tk = gcfg["triage_key"]
                if tk and triage.get(tk, {}).get("presence") == "unlikely":
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


# ── Save canonical output ─────────────────────────────────────────
def _paper_stats(details: dict) -> dict:
    extracted = sum(1 for d in details.values() if d["status"] != "NULL")
    verified = sum(1 for d in details.values() if d["status"] == "VERIFIED")
    ev = sum(1 for d in details.values() if d.get("evidence"))
    confs = [d["confidence"] for d in details.values() if d["status"] != "NULL"]
    avg = sum(confs) / len(confs) if confs else 0.0
    return {
        "fields_extracted": extracted,
        "fields_null": 30 - extracted,
        "fields_verified": verified,
        "evidence_count": ev,
        "evidence_coverage": round(ev / max(extracted, 1) * 100, 1),
        "avg_confidence": round(avg, 3),
    }


def save_paper(out_dir: Path, ds_id: str, cfg, extraction, details, usage,
               mode: str, extra_meta: dict):
    stats = _paper_stats(details)
    extra = {
        "pipeline": "agentic_lev",
        "specialist_prompts_sha256_prefix": SPECIALIST_PROMPTS_HASH,
        "extraction_details": details,
        "paper_stats": stats,
        "cost_usd": estimate_cost(cfg, usage, batch_discount=(mode == "batch")),
        "split": "dev" if ds_id in SPLIT["dev"] else "test",
    }
    extra.update(extra_meta)
    meta = meta_block(cfg, SCRIPT_NAME, mode, extra=extra)
    write_canonical_output(out_dir, ds_id, extraction, usage, cfg, meta)
    return stats


# ── Sequential processing ─────────────────────────────────────────
def process_paper(cfg, ds_id: str, out_dir: Path,
                  locator_cfg: dict | None = None,
                  prompt_variant: str = "v1") -> dict | None:
    t0 = time.time()
    full_text = load_paper_text(ds_id)
    if not full_text:
        print(f"  SKIP {ds_id}: no PDF")
        return None

    locator_usage = {"input_tokens": 0, "output_tokens": 0}
    if locator_cfg is not None:
        triage_override, locator_usage = locate_with_llm(locator_cfg, ds_id, full_text)
        if prompt_variant == "v7":
            group_texts, triage = locate_sections_v7(ds_id, full_text, triage_override=triage_override)
        else:
            group_texts, triage = locate_sections(ds_id, full_text, triage_override=triage_override)
    else:
        if prompt_variant == "v7":
            group_texts, triage = locate_sections_v7(ds_id, full_text)
        else:
            group_texts, triage = locate_sections(ds_id, full_text)

    extraction: dict = {}
    evidence: dict = {}
    group_stats: dict = {}
    total_usage = {"input_tokens": 0, "output_tokens": 0}

    skipped_unlikely = 0
    for group_name in GROUP_ORDER:
        section_text = group_texts.get(group_name, "")
        fields = FIELD_GROUPS[group_name]["fields"]

        # Phase 3 Fix B: locator-extractor coupling (variants v3, v4, v5, v6, v7).
        # v4 = +Fix A; v5 = +Fix D (multi-aspect); v6 = +tighter section context;
        # v7 = full implementation cleanup (audit fixes 1-9).
        if prompt_variant in ("v3", "v4", "v5", "v6", "v7"):
            triage_key = FIELD_GROUPS[group_name].get("triage_key")
            if triage_key:
                presence = triage.get(triage_key, {}).get("presence", "possible")
                if presence == "unlikely":
                    for f in fields:
                        extraction[f] = None
                        evidence[f] = None
                    group_stats[group_name] = {"section_chars": len(section_text),
                                               "skipped_unlikely": True}
                    skipped_unlikely += 1
                    continue

        if not section_text.strip():
            for f in fields:
                extraction[f] = None
                evidence[f] = None
            group_stats[group_name] = {"section_chars": 0, "skipped": True}
            continue

        try:
            if prompt_variant == "v7":
                ext, ev, usage = extract_group_v7(cfg, group_name, section_text, fields)
                # v7 verify+correct phase: re-prompt for null fields if locator
                # said the topic was 'likely' or 'possible'.
                triage_key_v7 = FIELD_GROUPS[group_name].get("triage_key")
                presence_v7 = (triage.get(triage_key_v7, {}).get("presence", "possible")
                               if triage_key_v7 else "possible")
                ext, ev, vc_usage = verify_correct_group(
                    cfg, group_name, section_text, fields, ext, ev,
                    triage_presence=presence_v7,
                )
                usage = {"input_tokens": usage["input_tokens"] + vc_usage["input_tokens"],
                         "output_tokens": usage["output_tokens"] + vc_usage["output_tokens"]}
            else:
                ext, ev, usage = extract_group(cfg, group_name, section_text, fields,
                                               prompt_variant=prompt_variant)
        except Exception as e:
            print(f"    {ds_id}/{group_name} FAILED: {str(e)[:60]}")
            for f in fields:
                extraction[f] = None
                evidence[f] = None
            group_stats[group_name] = {"error": str(e)[:80]}
            continue

        extraction.update(ext)
        evidence.update(ev)
        total_usage["input_tokens"] += usage["input_tokens"]
        total_usage["output_tokens"] += usage["output_tokens"]
        group_stats[group_name] = {
            "section_chars": len(section_text),
            "tokens_in": usage["input_tokens"],
            "tokens_out": usage["output_tokens"],
        }
        time.sleep(0.3)

    # Fold locator tokens into total so cost reflects full pipeline.
    total_usage["input_tokens"] += locator_usage["input_tokens"]
    total_usage["output_tokens"] += locator_usage["output_tokens"]

    extraction, enrichments = enrich(ds_id, extraction)
    details = validate_and_score(extraction, evidence, enrichments, triage)

    extra_meta = {
        "group_stats": group_stats,
        "enrichments": list(enrichments.keys()),
        "elapsed_seconds": round(time.time() - t0, 1),
    }
    if locator_cfg is not None:
        extra_meta["locator"] = {
            "backbone_key": locator_cfg.get("backbone_key", "unknown"),
            "model_id": locator_cfg.get("model_id"),
            "provider": locator_cfg.get("provider"),
            "input_tokens": locator_usage["input_tokens"],
            "output_tokens": locator_usage["output_tokens"],
        }
    else:
        extra_meta["locator"] = {"source": "precomputed_phase1_triage"}
    extra_meta["prompt_variant"] = prompt_variant
    extra_meta["skipped_unlikely_groups"] = skipped_unlikely
    return save_paper(out_dir, ds_id, cfg, extraction, details, total_usage, "realtime", extra_meta)


def run_sequential(cfg, papers, args, out_dir, locator_cfg: dict | None = None,
                   prompt_variant: str = "v1"):
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
            stats = process_paper(cfg, ds_id, out_dir, locator_cfg=locator_cfg,
                                  prompt_variant=prompt_variant)
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
                  f"{stats['fields_extracted']}/30, "
                  f"${saved['_meta']['cost_usd']:.3f}, "
                  f"ev={stats['evidence_coverage']:.0f}%, "
                  f"{saved['_meta']['elapsed_seconds']:.0f}s")
        except Exception as e:
            print(f"  [{i+1}/{len(papers)}] {ds_id}: FAILED ({str(e)[:80]})")
            fail += 1
        time.sleep(0.3)

    total_cost = estimate_cost(cfg, total_usage, batch_discount=False)
    total_fields = ok * 30
    print(f"\n{'=' * 70}")
    print(f"SUMMARY — LEV sequential ({cfg['name']})")
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
        "extractor_backbone": cfg["model_id"],
        "locator_backbone": (locator_cfg["model_id"] if locator_cfg else
                             "precomputed_phase1_gemini_flash_triage"),
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


def _sanitize_custom_id(text: str, limit: int = 64) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", text.replace("/", "__"))[:limit]


def run_batch(cfg, papers, out_dir):
    _require_anthropic(cfg)
    import anthropic
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request

    client = anthropic.Anthropic()
    wave_dir = out_dir / "_batch"
    wave_dir.mkdir(parents=True, exist_ok=True)
    batch_meta_path = wave_dir / "batch.json"

    paper_data: dict[str, tuple[dict, dict, str]] = {}
    for ds_id in papers:
        safe = ds_id.replace("/", "__")
        if (out_dir / f"{safe}.json").exists():
            continue
        full_text = load_paper_text(ds_id)
        if not full_text:
            continue
        group_texts, triage = locate_sections(ds_id, full_text)
        paper_data[ds_id] = (group_texts, triage, full_text)

    if not paper_data:
        print("  No papers pending.")
        return

    if batch_meta_path.exists():
        info = json.loads(batch_meta_path.read_text())
        batch_id = info["batch_id"]
        cid_map = info["cid_map"]
    else:
        requests: list = []
        cid_map: dict = {}
        for ds_id, (group_texts, _, _) in paper_data.items():
            safe_ds = _sanitize_custom_id(ds_id, 50)
            for group_name in GROUP_ORDER:
                section_text = group_texts.get(group_name, "")
                if not section_text.strip():
                    continue
                fields = FIELD_GROUPS[group_name]["fields"]
                schema = _schema_for_group(fields)
                user = GROUP_USER_PROMPT % (schema, section_text)
                cid = f"{safe_ds}___{group_name}"[:64]
                cid_map[cid] = {"ds_id": ds_id, "group": group_name}
                requests.append(Request(
                    custom_id=cid,
                    params=MessageCreateParamsNonStreaming(
                        model=cfg["model_id"],
                        max_tokens=MAX_TOKENS_GROUP,
                        temperature=0.0,
                        system=GROUP_SYSTEM_PROMPTS[group_name],
                        messages=[{"role": "user", "content": user}],
                    ),
                ))
        batch = client.messages.batches.create(requests=requests)
        batch_id = batch.id
        batch_meta_path.write_text(json.dumps(
            {"batch_id": batch_id, "cid_map": cid_map,
             "submitted_at": time.strftime("%Y-%m-%d %H:%M:%S")}, indent=2))
        print(f"  Batch submitted: {batch_id} "
              f"({len(requests)} requests, {len(paper_data)} papers × ≤5 groups)")

    while True:
        info = client.messages.batches.retrieve(batch_id)
        counts = info.request_counts
        total_done = counts.succeeded + counts.errored + counts.expired
        print(f"    {info.processing_status}: {total_done} done "
              f"(ok={counts.succeeded}, err={counts.errored})")
        if info.processing_status == "ended":
            break
        time.sleep(30)

    group_results: dict = defaultdict(dict)
    for result in client.messages.batches.results(batch_id):
        meta = cid_map.get(result.custom_id)
        if not meta:
            continue
        ds_id = meta["ds_id"]
        group_name = meta["group"]
        if result.result.type != "succeeded":
            print(f"    FAILED {ds_id}/{group_name}")
            continue
        msg = result.result.message
        raw = "".join(getattr(b, "text", "") for b in msg.content)
        usage = {"input_tokens": msg.usage.input_tokens,
                 "output_tokens": msg.usage.output_tokens}
        try:
            parsed = parse_json_response(raw)
        except Exception:
            print(f"    parse failed {ds_id}/{group_name}")
            continue
        fields = FIELD_GROUPS[group_name]["fields"]
        extraction, evidence = {}, {}
        for field in fields:
            entry = parsed.get(field, {})
            if isinstance(entry, dict):
                extraction[field] = entry.get("value")
                evidence[field] = entry.get("evidence")
            else:
                extraction[field] = entry
                evidence[field] = None
        group_results[ds_id][group_name] = {
            "extraction": extraction, "evidence": evidence, "usage": usage,
        }

    ok = 0
    for ds_id, (group_texts, triage, _) in paper_data.items():
        safe = ds_id.replace("/", "__")
        if (out_dir / f"{safe}.json").exists():
            ok += 1
            continue
        extraction: dict = {}
        evidence: dict = {}
        group_stats: dict = {}
        total_usage = {"input_tokens": 0, "output_tokens": 0}

        groups = group_results.get(ds_id, {})
        for group_name in GROUP_ORDER:
            fields = FIELD_GROUPS[group_name]["fields"]
            if group_name in groups:
                rec = groups[group_name]
                extraction.update(rec["extraction"])
                evidence.update(rec["evidence"])
                total_usage["input_tokens"] += rec["usage"]["input_tokens"]
                total_usage["output_tokens"] += rec["usage"]["output_tokens"]
                group_stats[group_name] = {
                    "section_chars": len(group_texts.get(group_name, "")),
                    "tokens_in": rec["usage"]["input_tokens"],
                    "tokens_out": rec["usage"]["output_tokens"],
                }
            else:
                for f in fields:
                    extraction[f] = None
                    evidence[f] = None
                group_stats[group_name] = {"skipped": True}

        extraction, enrichments = enrich(ds_id, extraction)
        details = validate_and_score(extraction, evidence, enrichments, triage)
        extra_meta = {
            "group_stats": group_stats,
            "enrichments": list(enrichments.keys()),
        }
        save_paper(out_dir, ds_id, cfg, extraction, details, total_usage, "batch", extra_meta)
        ok += 1

    print(f"  Batch pipeline done: {ok} papers written to {out_dir}")


# ── CLI ───────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(description="CroissantMiner LEV (Locate-Extract-Verify) pipeline")
    p.add_argument("--backbone", default=None,
                   help="(Legacy) single backbone for extractor; "
                        "uses precomputed Phase-1 Gemini-Flash triage as locator. "
                        "Mutually exclusive with --extractor-backbone.")
    p.add_argument("--locator-backbone", default=None,
                   help="LLM backbone for the locate step (replaces precomputed triage). "
                        "When set, --extractor-backbone must also be set.")
    p.add_argument("--extractor-backbone", default=None,
                   help="LLM backbone for the 5 extract calls. "
                        "When set, --locator-backbone must also be set.")
    p.add_argument("--dev-only", action="store_true", help="Process only the dev papers")
    p.add_argument("--paper", type=str, help="Process a single paper by dataset_id")
    p.add_argument("--batch", action="store_true",
                   help="Use Anthropic batch API (sonnet-4-5 only); "
                        "currently incompatible with --locator-backbone.")
    p.add_argument("--prompt-variant", default="v1", choices=["v1", "v2", "v3", "v4", "v5", "v6", "v7"],
                   help="v1=round-0; v2=Fix A; v3=Fix B (accepted +0.028); v4=A+B; v5=B+D; v6=B + tighter section; v7=Fix B + 9-item implementation cleanup (audit 2026-05-02): exact-match locator, dedup sections, paper order, section metadata, retry on JSON fail, 8K tokens, verify+correct phase, no core-group hack.")
    args = p.parse_args()

    # CLI validation: either legacy --backbone alone, or both new flags together.
    using_mixed = args.locator_backbone is not None or args.extractor_backbone is not None
    if using_mixed:
        if args.locator_backbone is None or args.extractor_backbone is None:
            raise SystemExit(
                "--locator-backbone and --extractor-backbone must be set together; "
                "use --backbone alone for the legacy precomputed-triage path."
            )
        if args.backbone is not None:
            raise SystemExit(
                "--backbone is mutually exclusive with --locator-backbone/--extractor-backbone."
            )
        if args.batch:
            raise SystemExit(
                "--batch path not yet supported with mixed-backbone LLM locator."
            )
        locator_cfg = dict(resolve_backbone(args.locator_backbone))
        locator_cfg["backbone_key"] = args.locator_backbone
        extractor_cfg = dict(resolve_backbone(args.extractor_backbone))
        extractor_cfg["backbone_key"] = args.extractor_backbone
        cfg = extractor_cfg  # cfg semantics: the model used by extract_group()
        out_dir = (ROOT / "data" / "extractions" /
                   f"agentic_lev_{locator_cfg['output_slug']}_{extractor_cfg['output_slug']}")
        backbone_label = (f"locator={args.locator_backbone} ({locator_cfg['name']}) | "
                          f"extractor={args.extractor_backbone} ({extractor_cfg['name']})")
    else:
        if args.backbone is None:
            args.backbone = "sonnet-4-5"  # restore legacy default
        cfg = dict(resolve_backbone(args.backbone))
        cfg["backbone_key"] = args.backbone
        locator_cfg = None
        out_dir = output_dir_for("lev", args.backbone)
        backbone_label = f"backbone={args.backbone} ({cfg['name']})  locator=precomputed_phase1_triage"
    if not any(PHASE0_DIR.glob("*.json")):
        raise SystemExit("Locator-Extractor needs the section index in data/agentic/phase0/, which is not "
                         "redistributed (it contains the papers' text). Build it with "
                         "python scripts/agentic_phase0.py after downloading the PDFs.")
    if locator_cfg is None and not any(PHASE1_DIR.glob("*.json")):
        raise SystemExit("The --backbone path reads the stored triage in data/agentic/phase1/, which is missing.")
    if args.prompt_variant != "v1":
        out_dir = out_dir.parent / f"{out_dir.name}_{args.prompt_variant}"
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.paper:
        papers = [args.paper]
    elif args.dev_only:
        papers = sorted(SPLIT["dev"])
    else:
        papers = sorted(SPLIT["dev"] + SPLIT["test"])

    print(f"{'=' * 70}")
    print(f"CROISSANTMINER LEV — {backbone_label}")
    print(f"Papers: {len(papers)}  Output: {out_dir}")
    print(f"Architecture: {'1 locator + 5 specialist' if locator_cfg else '5 specialist'} calls per paper (core/collection/annotation/impact/processing)")
    print(f"{'=' * 70}")

    if args.batch:
        run_batch(cfg, papers, out_dir)
    else:
        run_sequential(cfg, papers, args, out_dir, locator_cfg=locator_cfg,
                       prompt_variant=args.prompt_variant)


if __name__ == "__main__":
    main()
