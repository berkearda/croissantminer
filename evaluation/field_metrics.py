"""
Field-type-aware evaluation metrics for CroissantMiner.

Three tiers of evaluation:
  1. Constrained fields → exact match after normalization (0 or 1)
  2. Short-text fields → token-level F1 (0.0 to 1.0)
  3. Long-text RAI fields → LLM-as-judge 1-5 scale (normalized to 0-1)
"""

import re
import os
import json
import hashlib
from pathlib import Path
from typing import Optional, Tuple

# ═══════════════════════════════════════════════════════════════════════
# Field categories
# ═══════════════════════════════════════════════════════════════════════

CONSTRAINED_FIELDS = [
    "sc:name", "sc:license", "sc:inLanguage", "cr:isLiveDataset",
    "sc:datePublished", "sc:publisher", "sc:url",
]

SHORT_TEXT_FIELDS = [
    "sc:creator", "cr:citeAs", "sc:description",
]

LONG_TEXT_RAI_FIELDS = [
    "rai:dataCollection", "rai:dataCollectionType", "rai:dataCollectionMissingData",
    "rai:dataCollectionRawData", "rai:dataCollectionTimeframe", "rai:dataImputationProtocol",
    "rai:dataManipulationProtocol", "rai:dataPreprocessingProtocol",
    "rai:dataAnnotationProtocol", "rai:dataAnnotationPlatform", "rai:dataAnnotationAnalysis",
    "rai:annotationsPerItem", "rai:annotatorDemographics", "rai:machineAnnotationTools",
    "rai:dataReleaseMaintenancePlan", "rai:personalSensitiveInformation",
    "rai:dataSocialImpact", "rai:dataBiases", "rai:dataLimitations", "rai:dataUseCases",
]

ALL_30_FIELDS = CONSTRAINED_FIELDS + SHORT_TEXT_FIELDS + LONG_TEXT_RAI_FIELDS


def get_field_category(field_name: str) -> str:
    """Return 'constrained', 'short_text', or 'rai' for a field."""
    if field_name in CONSTRAINED_FIELDS:
        return "constrained"
    elif field_name in SHORT_TEXT_FIELDS:
        return "short_text"
    elif field_name in LONG_TEXT_RAI_FIELDS:
        return "rai"
    return "unknown"


# ═══════════════════════════════════════════════════════════════════════
# Normalizers (reused from llm_evaluator.py)
# ═══════════════════════════════════════════════════════════════════════

_LICENSE_CANON = {}
for _variants, _canon in [
    # CC-BY family
    (["cc-by-4.0", "cc by 4.0", "cc by-4.0", "creative commons 4.0",
      "creative commons attribution 4.0", "creative commons attribution 4.0 license",
      "creative commons attribution 4.0 international",
      "cc-by-4.0 international", "cc by 4.0 international"], "cc-by-4.0"),
    (["cc-by-3.0", "cc by 3.0", "creative commons attribution 3.0",
      "creative commons attribution 3.0 unported"], "cc-by-3.0"),
    # CC-BY-SA
    (["cc-by-sa-4.0", "cc by-sa 4.0", "cc by-sa-4.0", "cc-by-sa 4.0",
      "creative commons attribution-sharealike 4.0",
      "creative commons attribution sharealike 4.0",
      "creative commons attribution-sharealike 4.0 international"], "cc-by-sa-4.0"),
    # CC-BY-NC
    (["cc-by-nc-4.0", "cc by-nc 4.0", "cc by-nc-4.0",
      "creative commons attribution-noncommercial 4.0",
      "creative commons attribution noncommercial 4.0",
      "creative commons attribution-noncommercial 4.0 international"], "cc-by-nc-4.0"),
    # CC-BY-NC-SA
    (["cc-by-nc-sa-4.0", "cc by-nc-sa 4.0",
      "creative commons attribution-noncommercial-sharealike 4.0"], "cc-by-nc-sa-4.0"),
    # CC0 / Public Domain
    (["cc0", "cc0 1.0", "cc0-1.0", "public domain",
      "creative commons zero", "cc zero"], "cc0"),
    # MIT
    (["mit", "mit license", "the mit license", "mit licence"], "mit"),
    # Apache
    (["apache-2.0", "apache 2.0", "apache license 2.0",
      "apache license, version 2.0", "apache license version 2.0",
      "apache-2.0 license"], "apache-2.0"),
    # GPL
    (["gpl-3.0", "gplv3", "gnu gpl v3", "gnu general public license v3",
      "gnu general public license v3.0", "gpl 3.0",
      "gnu general public license version 3"], "gpl-3.0"),
    (["gpl-2.0", "gplv2", "gnu gpl v2", "gpl 2.0"], "gpl-2.0"),
    # BSD
    (["bsd-3-clause", "bsd 3-clause", "3-clause bsd",
      "bsd 3 clause", "new bsd license", "modified bsd license"], "bsd-3-clause"),
    (["bsd-2-clause", "bsd 2-clause", "simplified bsd license"], "bsd-2-clause"),
    # Other
    (["custom", "custom license", "other", "proprietary"], "custom"),
    (["unknown", "unknown license", "not specified"], "unknown"),
]:
    for v in _variants:
        _LICENSE_CANON[v] = _canon

_LANG_MAP = {
    "en": "english", "eng": "english", "english": "english",
    "de": "german", "deu": "german", "german": "german",
    "fr": "french", "fra": "french", "french": "french",
    "es": "spanish", "spa": "spanish", "spanish": "spanish",
    "it": "italian", "ita": "italian", "italian": "italian",
    "pt": "portuguese", "por": "portuguese", "portuguese": "portuguese",
    "nl": "dutch", "nld": "dutch", "dutch": "dutch",
    "pl": "polish", "pol": "polish", "polish": "polish",
    "zh": "chinese", "zho": "chinese", "chinese": "chinese",
    "ja": "japanese", "jpn": "japanese", "japanese": "japanese",
    "multilingual": "multilingual",
}


def _normalize_license(text):
    t = text.strip().lower()

    # 1. Handle URLs first
    # creativecommons.org/licenses/by-sa/4.0/ → cc-by-sa-4.0
    cc_url = re.search(r'creativecommons\.org/licenses?/([\w-]+)/([\d.]+)', t)
    if cc_url:
        return f"cc-{cc_url.group(1)}-{cc_url.group(2)}"
    # choosealicense.com/licenses/mit/ → mit
    choose_url = re.search(r'choosealicense\.com/licenses?/([\w.-]+)', t)
    if choose_url:
        slug = choose_url.group(1).rstrip("/")
        return _LICENSE_CANON.get(slug, slug)
    # Strip any remaining URLs
    t = re.sub(r'https?://\S+', '', t).strip()

    # 2. Expand "Creative Commons" to CC abbreviation
    t = re.sub(r'creative\s+commons\s+attribution\s*-?\s*non\s*-?\s*commercial\s*-?\s*share\s*-?\s*alike', 'cc-by-nc-sa', t)
    t = re.sub(r'creative\s+commons\s+attribution\s*-?\s*non\s*-?\s*commercial', 'cc-by-nc', t)
    t = re.sub(r'creative\s+commons\s+attribution\s*-?\s*share\s*-?\s*alike', 'cc-by-sa', t)
    t = re.sub(r'creative\s+commons\s+attribution', 'cc-by', t)
    t = re.sub(r'creative\s+commons\s+zero', 'cc0', t)
    t = re.sub(r'creative\s+commons', 'cc-by', t)  # bare "Creative Commons X.0" → assume CC-BY

    # 3. Strip trailing noise
    t = re.sub(r'\s*(licen[sc]e|international|unported)\s*$', '', t).strip()
    t = re.sub(r'^the\s+', '', t).strip()

    # 4. Normalize spacing: "CC BY 4.0" → "cc-by-4.0"
    t = re.sub(r'\bcc\s+by\b', 'cc-by', t)
    t = re.sub(r'\bcc-by\s+', 'cc-by-', t)
    t = re.sub(r'\bcc-by-sa\s+', 'cc-by-sa-', t)
    t = re.sub(r'\bcc-by-nc\s+', 'cc-by-nc-', t)
    t = re.sub(r'\bcc-by-nc-sa\s+', 'cc-by-nc-sa-', t)
    t = re.sub(r'\s+', '-', t).strip("-")

    # 5. Canonical lookup
    canon = _LICENSE_CANON.get(t)
    if canon:
        return canon
    # Fuzzy: check if any known key is a prefix
    for known in sorted(_LICENSE_CANON, key=len, reverse=True):
        if t.startswith(known) or known.startswith(t):
            return _LICENSE_CANON[known]
    return t


def _normalize_language(text):
    parts = re.split(r'[,;/]\s*|\s+and\s+|\s+', text.strip().lower())
    normalized = set()
    for p in parts:
        p = p.strip().rstrip(".")
        if p in _LANG_MAP:
            normalized.add(_LANG_MAP[p])
        elif p:
            normalized.add(p)
    return frozenset(normalized)


def _extract_year(text):
    m = re.search(r'\b(19|20)\d{2}\b', text)
    return m.group(0) if m else None


def _normalize_boolean(text):
    t = text.strip().lower()
    if t in ("yes", "true", "1"):
        return "true"
    if t in ("no", "false", "0"):
        return "false"
    return t


def _normalize_url(text):
    t = text.strip().lower().rstrip("/")
    t = re.sub(r'^https?://', '', t)
    return t


# ═══════════════════════════════════════════════════════════════════════
# Metric 1: Constrained exact match
# ═══════════════════════════════════════════════════════════════════════

def _normalize_name(text):
    """Normalize dataset name for matching.

    Handles: 'mls_eng_10k' vs 'Multilingual LibriSpeech (MLS)',
    'mmlu' vs 'MMLU (Massive Multitask Language Understanding)'
    """
    t = text.strip().lower()
    # Remove parenthetical content: "MMLU (Massive ...)" → "mmlu"
    t_no_paren = re.sub(r'\s*\(.*?\)\s*', ' ', t).strip()
    # Remove common suffixes
    t_no_paren = re.sub(r'\s*(dataset|benchmark|corpus)\s*$', '', t_no_paren).strip()
    # Replace underscores with spaces
    t_normalized = t_no_paren.replace('_', ' ').replace('-', ' ')
    return t_normalized


def _names_match(pred, gt):
    """Check if dataset names refer to the same thing."""
    p = pred.strip().lower()
    g = gt.strip().lower()

    # Exact match
    if p == g:
        return True

    # One contains the other
    if p in g or g in p:
        return True

    # Normalize and compare
    pn = _normalize_name(pred)
    gn = _normalize_name(gt)
    if pn == gn or pn in gn or gn in pn:
        return True

    # Check if abbreviation matches: "MLS" in "Multilingual LibriSpeech (MLS)"
    # Extract abbreviations from parentheses
    p_abbrev = re.findall(r'\(([A-Z]{2,})\)', pred)
    g_abbrev = re.findall(r'\(([A-Z]{2,})\)', gt)

    # Check if GT abbreviation appears in predicted or vice versa
    for abbr in p_abbrev:
        if abbr.lower() in g.lower():
            return True
    for abbr in g_abbrev:
        if abbr.lower() in p.lower():
            return True

    # Check if GT (often a short ID like "mmlu") is a token in the predicted name
    g_tokens = set(re.findall(r'\w+', g))
    p_tokens = set(re.findall(r'\w+', p))
    if g_tokens and g_tokens.issubset(p_tokens):
        return True
    if p_tokens and p_tokens.issubset(g_tokens):
        return True

    return False


def score_constrained(predicted: str, groundtruth: str, field_name: str) -> float:
    """Exact match after field-specific normalization. Returns 0.0 or 1.0."""
    p = predicted.strip()
    g = groundtruth.strip()

    if field_name in ("sc:name",):
        return 1.0 if _names_match(p, g) else 0.0

    if field_name in ("sc:license",):
        return 1.0 if _normalize_license(p) == _normalize_license(g) else 0.0

    if field_name in ("sc:inLanguage",):
        return 1.0 if _normalize_language(p) == _normalize_language(g) else 0.0

    if field_name in ("sc:datePublished",):
        py = _extract_year(p)
        gy = _extract_year(g)
        if py and gy:
            return 1.0 if py == gy else 0.0
        return 1.0 if p.lower() == g.lower() else 0.0

    if field_name in ("cr:isLiveDataset",):
        return 1.0 if _normalize_boolean(p) == _normalize_boolean(g) else 0.0

    if field_name in ("sc:url",):
        return 1.0 if _normalize_url(p) == _normalize_url(g) else 0.0

    if field_name in ("sc:publisher",):
        # Publisher: check if key tokens overlap (fuzzy)
        p_tokens = set(re.findall(r'\w+', p.lower()))
        g_tokens = set(re.findall(r'\w+', g.lower()))
        if p_tokens and g_tokens:
            overlap = len(p_tokens & g_tokens) / min(len(p_tokens), len(g_tokens))
            return 1.0 if overlap >= 0.5 else 0.0
        return 1.0 if p.lower() == g.lower() else 0.0

    # Default: case-insensitive exact match
    return 1.0 if p.lower() == g.lower() else 0.0


# ═══════════════════════════════════════════════════════════════════════
# Metric 2: Token-level F1
# ═══════════════════════════════════════════════════════════════════════

def _tokenize(text: str) -> list:
    """Lowercase, split on whitespace and punctuation."""
    return re.findall(r'\w+', text.lower())


def score_token_f1(predicted: str, groundtruth: str) -> float:
    """Token-level F1 between predicted and groundtruth. Returns 0.0 to 1.0."""
    pred_tokens = _tokenize(predicted)
    gt_tokens = _tokenize(groundtruth)

    if not pred_tokens and not gt_tokens:
        return 1.0
    if not pred_tokens or not gt_tokens:
        return 0.0

    pred_set = set(pred_tokens)
    gt_set = set(gt_tokens)
    common = pred_set & gt_set

    if not common:
        return 0.0

    precision = len(common) / len(pred_set)
    recall = len(common) / len(gt_set)
    f1 = 2 * precision * recall / (precision + recall)
    return f1


# ═══════════════════════════════════════════════════════════════════════
# Metric 3: LLM-as-judge (1-5 scale)
# ═══════════════════════════════════════════════════════════════════════

_JUDGE_PROMPT = """You are evaluating metadata extraction quality for ML dataset documentation.

Ground truth metadata value:
{gt_value}

Extracted metadata value:
{extraction_value}

Field being evaluated: {field_name}

Rate the extraction quality on a 1-5 scale:
1 = Completely wrong, irrelevant, or fabricated information
2 = Mentions the correct topic but mostly incorrect or misleading
3 = Captures some key information but missing important details
4 = Captures most key information with only minor omissions
5 = Fully captures the essential information from the ground truth

Output ONLY a single integer (1, 2, 3, 4, or 5)."""

_judge_cache = {}
_CACHE_FILE = Path("results/field_type_eval/llm_judge_cache.json")


def _load_cache():
    global _judge_cache
    if _CACHE_FILE.exists() and not _judge_cache:
        with open(_CACHE_FILE) as f:
            _judge_cache = json.load(f)


def _save_cache():
    _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_CACHE_FILE, "w") as f:
        json.dump(_judge_cache, f, indent=2, ensure_ascii=False)


def score_llm_judge(
    predicted: str,
    groundtruth: str,
    field_name: str,
) -> Tuple[int, float]:
    """LLM-as-judge 1-5 score. Returns (raw_1_5, normalized_0_1)."""
    _load_cache()

    cache_key = hashlib.md5(f"{field_name}::{predicted}::{groundtruth}".encode()).hexdigest()
    if cache_key in _judge_cache:
        raw = _judge_cache[cache_key]["score"]
        return raw, (raw - 1) / 4

    prompt = _JUDGE_PROMPT.format(
        gt_value=groundtruth[:1500],
        extraction_value=predicted[:1500],
        field_name=field_name,
    )

    try:
        from openai import OpenAI
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).parent.parent / '.env')

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=5,
        )
        answer = response.choices[0].message.content.strip()
        # Extract integer from response
        match = re.search(r'[1-5]', answer)
        raw = int(match.group()) if match else 3

    except Exception as e:
        print(f"    Judge error for {field_name}: {e}")
        raw = 3  # Default to middle

    _judge_cache[cache_key] = {
        "score": raw,
        "field": field_name,
        "predicted_preview": predicted[:100],
        "gt_preview": groundtruth[:100],
    }

    # Periodic save
    if len(_judge_cache) % 20 == 0:
        _save_cache()

    return raw, (raw - 1) / 4


# ═══════════════════════════════════════════════════════════════════════
# Unified scorer
# ═══════════════════════════════════════════════════════════════════════

def score_field(predicted: Optional[str], groundtruth: Optional[str], field_name: str) -> dict:
    """Score a single field using the appropriate metric for its type.

    Returns:
        {
            "field": field_name,
            "category": "constrained" | "short_text" | "rai",
            "score": float (0-1),
            "raw_score": varies by type,
            "metric": "exact_match" | "token_f1" | "llm_judge",
            "skipped": bool,
            "reason": str,
        }
    """
    cat = get_field_category(field_name)

    # Handle nulls
    gt_empty = groundtruth is None or not str(groundtruth).strip()
    gt_unknown = (not gt_empty and str(groundtruth).strip().lower()
                  in ("unknown", "n/a", "none", "null", "not disclosed", "na"))
    pred_empty = predicted is None or not str(predicted).strip()

    if gt_empty or gt_unknown:
        return {
            "field": field_name, "category": cat, "score": None,
            "raw_score": None, "metric": "skipped", "skipped": True,
            "reason": "No usable GT"
        }

    if pred_empty:
        return {
            "field": field_name, "category": cat, "score": 0.0,
            "raw_score": 0, "metric": "missing", "skipped": False,
            "reason": "Extraction is null but GT has value"
        }

    p = str(predicted).strip()
    g = str(groundtruth).strip()

    if cat == "constrained":
        s = score_constrained(p, g, field_name)
        return {
            "field": field_name, "category": cat, "score": s,
            "raw_score": s, "metric": "exact_match", "skipped": False,
            "reason": "Match" if s == 1.0 else "No match after normalization"
        }

    elif cat == "short_text":
        f1 = score_token_f1(p, g)
        return {
            "field": field_name, "category": cat, "score": f1,
            "raw_score": f1, "metric": "token_f1", "skipped": False,
            "reason": f"Token F1 = {f1:.3f}"
        }

    elif cat == "rai":
        raw, normalized = score_llm_judge(p, g, field_name)
        return {
            "field": field_name, "category": cat, "score": normalized,
            "raw_score": raw, "metric": "llm_judge", "skipped": False,
            "reason": f"LLM judge: {raw}/5"
        }

    else:
        return {
            "field": field_name, "category": "unknown", "score": 0.0,
            "raw_score": 0, "metric": "unknown", "skipped": False,
            "reason": "Unknown field category"
        }


def finalize_cache():
    """Call after all evaluations to save the LLM judge cache."""
    _save_cache()
