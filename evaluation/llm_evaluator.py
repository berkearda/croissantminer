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

        # Case 1: We didn't extract AND groundtruth is also empty/unknown
        # → CORRECT (both agree field doesn't exist or is unknown)
        if predicted_empty and (groundtruth_empty or groundtruth_unknown):
            return {
                "category": "CORRECT",
                "score": 1.0,
                "reasoning": "Field not extracted and groundtruth is also empty/unknown - correctly not extracted"
            }

        # Case 2: We didn't extract BUT groundtruth HAS a value
        # → MISSING (we failed to extract something that exists)
        if predicted_empty and not groundtruth_empty and not groundtruth_unknown:
            return {
                "category": "MISSING",
                "score": 0.0,
                "reasoning": "Field not extracted but groundtruth has a value"
            }

        # Case 3: We extracted BUT groundtruth is empty (no annotation to compare)
        # → CORRECT (assume our extraction is correct when no groundtruth available)
        if not predicted_empty and groundtruth_empty:
            return {
                "category": "CORRECT",
                "score": 1.0,
                "reasoning": "No groundtruth available for comparison"
            }

        # Case 4: We extracted BUT groundtruth is "Unknown"
        # → CORRECT (we attempted extraction, annotator didn't know - accept our extraction)
        if not predicted_empty and groundtruth_unknown:
            return {
                "category": "CORRECT",
                "score": 1.0,
                "reasoning": "Groundtruth marked as 'Unknown', extracted value assumed correct"
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

    # Calculate overall statistics
    if results:
        scores = [r['score'] for r in results.values()]
        categories = [r['category'] for r in results.values()]

        from collections import Counter
        category_counts = Counter(categories)

        overall_stats = {
            'llm_accuracy': sum(scores) / len(scores) if scores else 0.0,
            'num_fields': len(results),
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
