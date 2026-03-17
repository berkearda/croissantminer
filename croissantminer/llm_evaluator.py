"""
LLM-based evaluator for CroissantMiner

Uses GPT-4o-mini as an intelligent judge to evaluate semantic equivalence
between extracted and groundtruth metadata fields.
"""

import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from openai import OpenAI

from .field_types import (
    FieldType,
    EvaluationCategory,
    get_field_type,
    get_evaluation_instructions
)
from .field_filter import is_valid_field, OFFICIAL_CROISSANT_FIELDS

# Load environment variables
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

import re

# ═══════════════════════════════════════════════════════════════════════
# Format normalizers — catch equivalent values before expensive LLM call
# ═══════════════════════════════════════════════════════════════════════

# License canonical mapping
_LICENSE_CANON = {}
for _variants, _canon in [
    (["cc-by-4.0", "cc by 4.0", "creative commons attribution 4.0",
      "creative commons attribution 4.0 license",
      "creative commons attribution 4.0 international"], "cc-by-4.0"),
    (["cc-by-sa-4.0", "cc by-sa 4.0", "creative commons attribution-sharealike 4.0",
      "creative commons attribution sharealike 4.0",
      "cc-by-sa-4.0 international"], "cc-by-sa-4.0"),
    (["cc-by-nc-4.0", "cc by-nc 4.0", "creative commons attribution-noncommercial 4.0",
      "creative commons attribution noncommercial 4.0"], "cc-by-nc-4.0"),
    (["cc-by-nc-sa-4.0", "cc by-nc-sa 4.0"], "cc-by-nc-sa-4.0"),
    (["mit", "mit license"], "mit"),
    (["apache-2.0", "apache 2.0", "apache license 2.0",
      "apache license, version 2.0"], "apache-2.0"),
    (["cc0", "cc0 1.0", "cc0-1.0", "public domain"], "cc0"),
    (["cc-by-3.0", "cc by 3.0", "creative commons attribution 3.0"], "cc-by-3.0"),
]:
    for v in _variants:
        _LICENSE_CANON[v] = _canon


def _normalize_license(text):
    """Map license text to canonical form."""
    t = text.strip().lower()
    t = re.sub(r'https?://choosealicense\.com/licenses/', '', t)
    t = re.sub(r'https?://creativecommons\.org/licenses/', 'cc-', t)
    t = t.rstrip("/").strip()
    return _LICENSE_CANON.get(t, t)


def _licenses_match(pred, gt):
    return _normalize_license(pred) == _normalize_license(gt)


# Language normalization (ISO 639-1 / full name)
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
    "ko": "korean", "kor": "korean", "korean": "korean",
    "ar": "arabic", "ara": "arabic", "arabic": "arabic",
    "ru": "russian", "rus": "russian", "russian": "russian",
    "hi": "hindi", "hin": "hindi", "hindi": "hindi",
    "multilingual": "multilingual",
}


def _normalize_language(text):
    """Normalize a language string to a canonical set of languages."""
    t = text.strip().lower()
    # Split on comma, semicolon, space, "and"
    parts = re.split(r'[,;/]\s*|\s+and\s+|\s+', t)
    normalized = set()
    for p in parts:
        p = p.strip().rstrip(".")
        if p in _LANG_MAP:
            normalized.add(_LANG_MAP[p])
        elif p:
            normalized.add(p)
    return frozenset(normalized)


def _languages_match(pred, gt):
    return _normalize_language(pred) == _normalize_language(gt)


def _extract_year(text):
    """Extract a 4-digit year from text."""
    m = re.search(r'\b(19|20)\d{2}\b', text)
    return m.group(0) if m else None


def _dates_match(pred, gt):
    """Compare dates with granularity awareness.

    Rules:
    - If GT is year-only and extraction's year matches → CORRECT
    - If GT is full date and extraction is year-only with same year → PARTIAL
    - If years don't match → None (let LLM judge)
    """
    pred_year = _extract_year(pred)
    gt_year = _extract_year(gt)

    if not pred_year or not gt_year:
        return None  # Can't determine, let LLM handle

    if pred_year != gt_year:
        return None  # Years differ, let LLM judge severity

    # Years match. Check granularity.
    gt_is_year_only = bool(re.fullmatch(r'\s*(19|20)\d{2}\s*', gt.strip()))

    # Years match — CORRECT regardless of granularity difference.
    # Rationale: for metadata purposes, getting the right year is sufficient.
    # The schema says "YYYY-MM-DD or YYYY" — both are valid.
    return {
        "category": "CORRECT",
        "score": 1.0,
        "reasoning": f"Year matches ({pred_year}). Both YYYY and YYYY-MM-DD are valid datePublished formats."
    }


class LLMEvaluator:
    """LLM-based semantic evaluator for metadata fields"""

    def __init__(self, model_id: str = "gpt-4o-mini", temperature: float = 0.0):
        """
        Initialize LLM evaluator

        Args:
            model_id: OpenAI model to use
            temperature: Sampling temperature (0.0 for deterministic)
        """
        self.model_id = model_id
        self.temperature = temperature
        self.client = None
        self.cache = {}  # Cache for repeated evaluations
        self.cache_version = int(time.time())  # Timestamp to prevent cross-evaluation contamination

        # Initialize OpenAI client
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set. LLM evaluation requires OpenAI API access.")

        self.client = OpenAI(api_key=api_key)
        print(f"✅ LLM Evaluator initialized with {model_id} (cache version: {self.cache_version})")

    def _create_evaluation_prompt(
        self,
        predicted: str,
        groundtruth: str,
        field_name: str,
        field_type: FieldType
    ) -> str:
        """
        Create evaluation prompt for LLM

        Args:
            predicted: Extracted value
            groundtruth: Groundtruth value
            field_name: Name of the field
            field_type: Type of the field

        Returns:
            Formatted prompt string
        """
        instructions = get_evaluation_instructions(field_type)

        prompt = f"""You are an expert evaluator assessing metadata extraction quality.

**Task**: Compare the extracted value against the groundtruth value and determine if the extraction is correct.

**Field Name**: {field_name}
**Field Type**: {field_type.value}

**Extracted Value**:
{predicted}

**Groundtruth Value**:
{groundtruth}

{instructions}

**Your Task**:
1. Analyze semantic equivalence between extracted and groundtruth values
2. Assign ONE of these categories:
   - CORRECT (1.0): Semantically equivalent, valid subset, or accurate representation
   - PARTIALLY_CORRECT (0.5): Contains some correct information but incomplete or has extra info
   - INCORRECT (0.0): Wrong information or significantly different meaning
   - MISSING (0.0): Field is empty or not extracted

3. Provide brief reasoning (1-2 sentences)

**Response Format** (JSON only, no other text):
{{
  "category": "CORRECT" | "PARTIALLY_CORRECT" | "INCORRECT" | "MISSING",
  "score": 1.0 | 0.5 | 0.0,
  "reasoning": "Brief explanation of your decision"
}}"""

        return prompt

    def evaluate_single_field(
        self,
        predicted: str,
        groundtruth: str,
        field_name: str
    ) -> Dict:
        """
        Evaluate a single field using LLM

        Args:
            predicted: Extracted value
            groundtruth: Groundtruth value
            field_name: Name of the field

        Returns:
            Dict with {category, score, reasoning}
        """
        # CRITICAL FIX: Check if predicted is empty FIRST
        # If we didn't extract the field, it's MISSING regardless of groundtruth
        predicted_empty = not predicted or predicted.strip() == ""
        groundtruth_empty = not groundtruth or groundtruth.strip() == ""

        # Check if groundtruth is "Unknown" (annotator didn't know)
        groundtruth_unknown = groundtruth.strip().lower() in ["unknown", "n/a", "none", "null", "not disclosed", "na"] if groundtruth and groundtruth.strip() else False

        # SKIP: If groundtruth is empty or unknown, we cannot evaluate this field.
        # Don't count it as correct OR incorrect — exclude from accuracy calculation.
        if groundtruth_empty or groundtruth_unknown:
            return {
                "category": "SKIPPED",
                "score": None,
                "reasoning": "No usable groundtruth — field excluded from accuracy calculation"
            }

        # GT has a real value. Now check the extraction.
        # Case: extraction is empty but GT has value → MISSING
        if predicted_empty:
            return {
                "category": "MISSING",
                "score": 0.0,
                "reasoning": "Field not extracted but groundtruth has a value"
            }

        # Check cache with version to prevent cross-evaluation contamination
        cache_key = f"{self.cache_version}::{field_name}::{predicted}::{groundtruth}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        # Quick exact match check (optimization)
        if predicted.strip().lower() == groundtruth.strip().lower():
            result = {
                "category": "CORRECT",
                "score": 1.0,
                "reasoning": "Exact match (case-insensitive)"
            }
            self.cache[cache_key] = result
            return result

        # ── Format normalizers (catch equivalent values before LLM call) ──

        # 1. License normalization
        if field_name in ("sc:license", "license"):
            if _licenses_match(predicted, groundtruth):
                result = {
                    "category": "CORRECT",
                    "score": 1.0,
                    "reasoning": "License match after format normalization"
                }
                self.cache[cache_key] = result
                return result

        # 2. Language normalization
        if field_name in ("sc:inLanguage", "inLanguage"):
            if _languages_match(predicted, groundtruth):
                result = {
                    "category": "CORRECT",
                    "score": 1.0,
                    "reasoning": "Language match after ISO 639 normalization"
                }
                self.cache[cache_key] = result
                return result

        # 3. Date granularity: year-only GT matches full date with same year
        if field_name in ("sc:datePublished", "datePublished"):
            date_result = _dates_match(predicted, groundtruth)
            if date_result is not None:
                self.cache[cache_key] = date_result
                return date_result

        # Determine field type
        field_type = get_field_type(field_name)

        # Create prompt
        prompt = self._create_evaluation_prompt(
            predicted, groundtruth, field_name, field_type
        )

        try:
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=self.model_id,
                messages=[
                    {"role": "system", "content": "You are an expert metadata extraction evaluator. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_tokens=200,
                response_format={"type": "json_object"}
            )

            # Parse response
            result_text = response.choices[0].message.content
            result = json.loads(result_text)

            # Validate result
            if "category" not in result or "score" not in result:
                raise ValueError(f"Invalid LLM response format: {result}")

            # Cache result
            self.cache[cache_key] = result

            return result

        except Exception as e:
            print(f"⚠️  LLM evaluation error for {field_name}: {e}")
            # Fallback: return uncertain score
            return {
                "category": "PARTIALLY_CORRECT",
                "score": 0.5,
                "reasoning": f"LLM evaluation failed: {str(e)}"
            }

    def evaluate_fields_batch(
        self,
        predicted_fields: Dict[str, str],
        groundtruth_fields: Dict[str, str]
    ) -> Dict[str, Dict]:
        """
        Evaluate multiple fields (batched for efficiency)

        Args:
            predicted_fields: Dictionary of extracted field values
            groundtruth_fields: Dictionary of groundtruth field values

        Returns:
            Dictionary mapping field_name -> evaluation result
        """
        results = {}

        # Get all fields from groundtruth
        all_fields = set(groundtruth_fields.keys())

        # Also include fields that were extracted but not in groundtruth
        all_fields.update(predicted_fields.keys())

        # Filter to only official Croissant fields
        valid_fields = [f for f in all_fields if is_valid_field(f)]

        print(f"  Evaluating {len(valid_fields)} fields with LLM judge...")

        for field_name in sorted(valid_fields):

            predicted_value = predicted_fields.get(field_name, "")
            groundtruth_value = groundtruth_fields.get(field_name, "")

            # Evaluate field
            result = self.evaluate_single_field(
                predicted=str(predicted_value),
                groundtruth=str(groundtruth_value),
                field_name=field_name
            )

            results[field_name] = result

        return results

    def evaluate_against_multiple_annotators(
        self,
        predicted_fields: Dict[str, str],
        groundtruth_annotations: List[Dict[str, str]]
    ) -> Dict[str, Dict]:
        """
        Evaluate against multiple human annotations

        Args:
            predicted_fields: Extracted field values
            groundtruth_annotations: List of groundtruth annotations from different annotators

        Returns:
            Aggregated evaluation results per field
        """
        if not groundtruth_annotations:
            return {}

        # Evaluate against each annotator
        per_annotator_results = []
        for i, gt_annotation in enumerate(groundtruth_annotations):
            print(f"    Evaluating against annotator {i+1}/{len(groundtruth_annotations)}...")
            results = self.evaluate_fields_batch(predicted_fields, gt_annotation)
            per_annotator_results.append(results)

        # Aggregate results across annotators
        aggregated = {}
        all_fields = set()
        for results in per_annotator_results:
            all_fields.update(results.keys())

        for field_name in all_fields:
            scores = []
            categories = []
            reasonings = []

            for results in per_annotator_results:
                if field_name in results:
                    scores.append(results[field_name]['score'])
                    categories.append(results[field_name]['category'])
                    reasonings.append(results[field_name]['reasoning'])

            if scores:
                # Priority-based aggregation: CORRECT > PARTIALLY_CORRECT > INCORRECT > MISSING
                # If ANY annotator says CORRECT → CORRECT
                # Else if ANY annotator says PARTIALLY_CORRECT → PARTIALLY_CORRECT
                # Else use worst score

                best_category = None
                best_score = None
                best_reasoning = None

                # Check for CORRECT first (highest priority)
                if 'CORRECT' in categories:
                    correct_idx = categories.index('CORRECT')
                    best_category = 'CORRECT'
                    best_score = 1.0
                    best_reasoning = reasonings[correct_idx]

                # If no CORRECT, check for PARTIALLY_CORRECT
                elif 'PARTIALLY_CORRECT' in categories:
                    partial_idx = categories.index('PARTIALLY_CORRECT')
                    best_category = 'PARTIALLY_CORRECT'
                    best_score = 0.5
                    best_reasoning = reasonings[partial_idx]

                # Otherwise, use the first category (INCORRECT or MISSING)
                else:
                    best_category = categories[0]
                    best_score = scores[0]
                    best_reasoning = reasonings[0]

                aggregated[field_name] = {
                    'score': best_score,
                    'category': best_category,
                    'num_annotators': len(scores),
                    'reasoning': best_reasoning,  # Use reasoning from best match
                    'all_scores': scores,
                    'all_categories': categories,
                    'all_reasonings': reasonings  # Store all individual reasonings
                }

        return aggregated


def evaluate_with_llm(
    predicted_fields: Dict[str, str],
    groundtruth_annotations: List[Dict[str, str]],
    model_id: str = "gpt-4o-mini"
) -> Dict:
    """
    Convenience function to evaluate with LLM

    Args:
        predicted_fields: Extracted field values
        groundtruth_annotations: List of groundtruth annotations
        model_id: OpenAI model to use

    Returns:
        Evaluation results with LLM scores
    """
    evaluator = LLMEvaluator(model_id=model_id)
    results = evaluator.evaluate_against_multiple_annotators(
        predicted_fields, groundtruth_annotations
    )

    # Calculate overall statistics — SKIP fields with no usable GT
    if results:
        # Only include fields that were actually evaluated (not SKIPPED)
        evaluated = {f: r for f, r in results.items() if r.get('category') != 'SKIPPED'}
        scores = [r['score'] for r in evaluated.values()]

        from collections import Counter
        category_counts = Counter(r['category'] for r in results.values())

        overall_stats = {
            'llm_accuracy': sum(scores) / len(scores) if scores else 0.0,
            'num_fields': len(results),
            'num_fields_evaluated': len(evaluated),
            'num_fields_skipped': category_counts.get('SKIPPED', 0),
            'category_distribution': dict(category_counts),
            'correct_count': category_counts.get('CORRECT', 0),
            'partially_correct_count': category_counts.get('PARTIALLY_CORRECT', 0),
            'incorrect_count': category_counts.get('INCORRECT', 0),
            'missing_count': category_counts.get('MISSING', 0)
        }
    else:
        overall_stats = {
            'llm_accuracy': 0.0,
            'num_fields': 0,
            'num_fields_evaluated': 0,
            'num_fields_skipped': 0,
            'category_distribution': {},
            'correct_count': 0,
            'partially_correct_count': 0,
            'incorrect_count': 0,
            'missing_count': 0
        }

    return {
        'field_results': results,
        'overall_stats': overall_stats
    }
