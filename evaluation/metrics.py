"""
Evaluation metrics for CroissantMiner

Provides various metrics to evaluate the quality of extracted Croissant metadata
against human-annotated groundtruth.
"""

import re
from typing import Dict, List, Optional, Tuple
from difflib import SequenceMatcher
import numpy as np


def normalize_text(text: str) -> str:
    """
    Normalize text for comparison

    Args:
        text: Text to normalize

    Returns:
        Normalized text
    """
    if not isinstance(text, str):
        return ""

    # Convert to lowercase
    text = text.lower()

    # Remove extra whitespace
    text = ' '.join(text.split())

    # Remove punctuation
    text = re.sub(r'[^\w\s]', ' ', text)

    # Remove extra spaces again
    text = ' '.join(text.split())

    return text.strip()


def exact_match(predicted: str, groundtruth: str, case_sensitive: bool = False) -> bool:
    """
    Check if predicted value exactly matches groundtruth

    Args:
        predicted: Predicted value
        groundtruth: Groundtruth value
        case_sensitive: Whether to perform case-sensitive comparison

    Returns:
        True if exact match
    """
    if not isinstance(predicted, str) or not isinstance(groundtruth, str):
        return False

    if not case_sensitive:
        predicted = predicted.lower()
        groundtruth = groundtruth.lower()

    return predicted.strip() == groundtruth.strip()


def partial_match(predicted: str, groundtruth: str, threshold: float = 0.8) -> bool:
    """
    Check if predicted value partially matches groundtruth using sequence similarity

    Args:
        predicted: Predicted value
        groundtruth: Groundtruth value
        threshold: Similarity threshold (0.0 to 1.0)

    Returns:
        True if similarity >= threshold
    """
    if not isinstance(predicted, str) or not isinstance(groundtruth, str):
        return False

    # Normalize both strings
    pred_norm = normalize_text(predicted)
    gt_norm = normalize_text(groundtruth)

    if not pred_norm or not gt_norm:
        return False

    # Calculate similarity ratio
    similarity = SequenceMatcher(None, pred_norm, gt_norm).ratio()

    return similarity >= threshold


def cosine_similarity(text1: str, text2: str) -> float:
    """
    Calculate cosine similarity between two texts based on word overlap

    Args:
        text1: First text
        text2: Second text

    Returns:
        Cosine similarity (0.0 to 1.0)
    """
    if not isinstance(text1, str) or not isinstance(text2, str):
        return 0.0

    # Normalize and tokenize
    words1 = set(normalize_text(text1).split())
    words2 = set(normalize_text(text2).split())

    if not words1 or not words2:
        return 0.0

    # Calculate intersection and union
    intersection = words1.intersection(words2)

    if not intersection:
        return 0.0

    # Cosine similarity based on word sets
    return len(intersection) / (len(words1) ** 0.5 * len(words2) ** 0.5)


def field_f1_score(predicted: str, groundtruth: str) -> Tuple[float, float, float]:
    """
    Calculate precision, recall, and F1 score for a field based on word overlap

    Args:
        predicted: Predicted value
        groundtruth: Groundtruth value

    Returns:
        Tuple of (precision, recall, f1_score)
    """
    if not isinstance(predicted, str) or not isinstance(groundtruth, str):
        return (0.0, 0.0, 0.0)

    # Normalize and tokenize
    pred_words = set(normalize_text(predicted).split())
    gt_words = set(normalize_text(groundtruth).split())

    if not pred_words and not gt_words:
        return (1.0, 1.0, 1.0)  # Both empty

    if not pred_words or not gt_words:
        return (0.0, 0.0, 0.0)  # One is empty

    # Calculate metrics
    true_positive = len(pred_words.intersection(gt_words))
    false_positive = len(pred_words - gt_words)
    false_negative = len(gt_words - pred_words)

    precision = true_positive / (true_positive + false_positive) if (true_positive + false_positive) > 0 else 0.0
    recall = true_positive / (true_positive + false_negative) if (true_positive + false_negative) > 0 else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    return (precision, recall, f1)


def evaluate_field(
    predicted: str,
    groundtruth: str,
    field_name: str
) -> Dict:
    """
    Comprehensive evaluation of a single field

    Args:
        predicted: Predicted value
        groundtruth: Groundtruth value
        field_name: Name of the field being evaluated

    Returns:
        Dictionary of metrics
    """
    metrics = {
        'field_name': field_name,
        'exact_match': exact_match(predicted, groundtruth),
        'partial_match_0.8': partial_match(predicted, groundtruth, threshold=0.8),
        'partial_match_0.6': partial_match(predicted, groundtruth, threshold=0.6),
        'cosine_similarity': cosine_similarity(predicted, groundtruth)
    }

    precision, recall, f1 = field_f1_score(predicted, groundtruth)
    metrics['precision'] = precision
    metrics['recall'] = recall
    metrics['f1_score'] = f1

    # Sequence similarity
    if isinstance(predicted, str) and isinstance(groundtruth, str):
        pred_norm = normalize_text(predicted)
        gt_norm = normalize_text(groundtruth)
        if pred_norm and gt_norm:
            metrics['sequence_similarity'] = SequenceMatcher(None, pred_norm, gt_norm).ratio()
        else:
            metrics['sequence_similarity'] = 0.0
    else:
        metrics['sequence_similarity'] = 0.0

    return metrics


def overall_accuracy(
    predicted_fields: Dict[str, str],
    groundtruth_fields: Dict[str, str],
    threshold: float = 0.8
) -> float:
    """
    Calculate overall accuracy across all fields

    Args:
        predicted_fields: Dictionary of predicted field values
        groundtruth_fields: Dictionary of groundtruth field values
        threshold: Similarity threshold for partial matches

    Returns:
        Accuracy (0.0 to 1.0)
    """
    if not groundtruth_fields:
        return 0.0

    # Only evaluate fields present in groundtruth
    total_fields = 0
    correct_fields = 0

    for field_name, gt_value in groundtruth_fields.items():
        # Convert to string and check if empty
        gt_value_str = str(gt_value) if gt_value is not None else ""
        if not gt_value_str or gt_value_str.strip() == "":
            continue  # Skip empty groundtruth fields
        gt_value = gt_value_str

        total_fields += 1
        pred_value = predicted_fields.get(field_name, "")
        pred_value = str(pred_value) if pred_value is not None else ""

        # Consider field correct if it passes partial match threshold
        if partial_match(pred_value, gt_value, threshold=threshold):
            correct_fields += 1

    if total_fields == 0:
        return 0.0

    return correct_fields / total_fields


def per_field_accuracy(
    predicted_list: List[Dict[str, str]],
    groundtruth_list: List[Dict[str, str]],
    field_name: str,
    threshold: float = 0.8
) -> float:
    """
    Calculate accuracy for a specific field across multiple samples

    Args:
        predicted_list: List of predicted field dictionaries
        groundtruth_list: List of groundtruth field dictionaries
        field_name: Name of the field to evaluate
        threshold: Similarity threshold

    Returns:
        Field accuracy (0.0 to 1.0)
    """
    if len(predicted_list) != len(groundtruth_list):
        raise ValueError("Predicted and groundtruth lists must have same length")

    if len(groundtruth_list) == 0:
        return 0.0

    total_samples = 0
    correct_samples = 0

    for pred_fields, gt_fields in zip(predicted_list, groundtruth_list):
        gt_value = gt_fields.get(field_name, "")

        # Convert to string and check if empty
        gt_value_str = str(gt_value) if gt_value is not None else ""
        if not gt_value_str or gt_value_str.strip() == "":
            continue
        gt_value = gt_value_str

        total_samples += 1
        pred_value = pred_fields.get(field_name, "")
        pred_value = str(pred_value) if pred_value is not None else ""

        if partial_match(pred_value, gt_value, threshold=threshold):
            correct_samples += 1

    if total_samples == 0:
        return 0.0

    return correct_samples / total_samples


def fleiss_kappa(ratings: List[List[int]]) -> float:
    """
    Calculate Fleiss' Kappa for inter-annotator agreement

    Args:
        ratings: List of [n_subjects x n_categories] rating matrices
                 where each row is a subject and columns are category counts

    Returns:
        Fleiss' Kappa value (-1.0 to 1.0)
    """
    ratings = np.array(ratings)
    n_subjects = ratings.shape[0]
    n_categories = ratings.shape[1]
    n_raters = np.sum(ratings[0])  # Total raters per subject

    # Calculate p_j (proportion of all assignments in category j)
    p_j = np.sum(ratings, axis=0) / (n_subjects * n_raters)

    # Calculate P_i (extent of agreement for subject i)
    P_i = (np.sum(ratings ** 2, axis=1) - n_raters) / (n_raters * (n_raters - 1))

    # Calculate P_bar (mean of P_i)
    P_bar = np.mean(P_i)

    # Calculate P_e (expected agreement by chance)
    P_e = np.sum(p_j ** 2)

    # Calculate Kappa
    if P_e == 1.0:
        return 1.0  # Perfect agreement

    kappa = (P_bar - P_e) / (1 - P_e)

    return kappa


def inter_annotator_agreement(
    annotations: List[Dict[str, str]],
    field_name: str,
    similarity_threshold: float = 0.8
) -> float:
    """
    Calculate inter-annotator agreement for a specific field

    Args:
        annotations: List of annotation dictionaries from different annotators
        field_name: Field to evaluate
        similarity_threshold: Threshold for considering annotations as agreeing

    Returns:
        Agreement score (0.0 to 1.0)
    """
    if len(annotations) < 2:
        return 1.0  # Perfect agreement if only one annotator

    # Extract field values
    values = [ann.get(field_name, "") for ann in annotations]

    # Filter out empty values (convert to string first)
    values = [str(v) if v is not None else "" for v in values]
    values = [v for v in values if v and v.strip() != ""]

    if len(values) < 2:
        return 1.0  # Can't compute agreement

    # Count pairwise agreements
    total_pairs = 0
    agreement_pairs = 0

    for i in range(len(values)):
        for j in range(i + 1, len(values)):
            total_pairs += 1
            if partial_match(values[i], values[j], threshold=similarity_threshold):
                agreement_pairs += 1

    if total_pairs == 0:
        return 1.0

    return agreement_pairs / total_pairs


def calculate_all_metrics(
    predicted_fields: Dict[str, str],
    groundtruth_annotations: List[Dict[str, str]],
    use_llm: bool = False
) -> Dict:
    """
    Calculate comprehensive metrics comparing predicted fields against
    multiple groundtruth annotations

    Args:
        predicted_fields: Extracted field values
        groundtruth_annotations: List of groundtruth annotations (from multiple annotators)
        use_llm: Whether to use LLM-based evaluation (default: False, uses string matching)

    Returns:
        Dictionary of comprehensive metrics
    """
    if not groundtruth_annotations:
        return {}

    # Use LLM evaluation if requested
    if use_llm:
        try:
            from .llm_evaluator import evaluate_with_llm
            return evaluate_with_llm(predicted_fields, groundtruth_annotations)
        except Exception as e:
            print(f"⚠️  LLM evaluation failed: {e}")
            print("   Falling back to string-based evaluation...")
            use_llm = False

    # Get all field names from groundtruth
    all_fields = set()
    for annotation in groundtruth_annotations:
        all_fields.update(annotation.keys())

    # Remove metadata fields and filter to only official Croissant fields
    from .field_filter import is_valid_field
    all_fields = {f for f in all_fields if is_valid_field(f)}

    # Calculate metrics for each field against each annotator
    field_metrics = {}

    for field_name in all_fields:
        field_scores = []

        for annotation in groundtruth_annotations:
            gt_value = annotation.get(field_name, "")

            # Convert to string and skip empty groundtruth values
            gt_value_str = str(gt_value) if gt_value is not None else ""
            if not gt_value_str or gt_value_str.strip() == "":
                continue
            gt_value = gt_value_str

            pred_value = predicted_fields.get(field_name, "")
            pred_value = str(pred_value) if pred_value is not None else ""
            metrics = evaluate_field(pred_value, gt_value, field_name)
            field_scores.append(metrics)

        if field_scores:
            # Average metrics across annotators
            avg_metrics = {
                'field_name': field_name,
                'num_annotators': len(field_scores)
            }

            # Average numeric metrics
            numeric_keys = ['cosine_similarity', 'precision', 'recall', 'f1_score', 'sequence_similarity']
            for key in numeric_keys:
                avg_metrics[f'avg_{key}'] = np.mean([m[key] for m in field_scores])

            # Majority vote for boolean metrics
            avg_metrics['exact_match_rate'] = np.mean([m['exact_match'] for m in field_scores])
            avg_metrics['partial_match_0.8_rate'] = np.mean([m['partial_match_0.8'] for m in field_scores])
            avg_metrics['partial_match_0.6_rate'] = np.mean([m['partial_match_0.6'] for m in field_scores])

            field_metrics[field_name] = avg_metrics

    # Calculate overall metrics
    overall_metrics = {
        'overall_accuracy_0.8': overall_accuracy(predicted_fields, groundtruth_annotations[0], threshold=0.8),
        'overall_accuracy_0.6': overall_accuracy(predicted_fields, groundtruth_annotations[0], threshold=0.6),
        'num_fields_evaluated': len(field_metrics),
        'num_annotators': len(groundtruth_annotations)
    }

    # Calculate inter-annotator agreement
    agreement_scores = {}
    for field_name in all_fields:
        agreement = inter_annotator_agreement(groundtruth_annotations, field_name)
        agreement_scores[field_name] = agreement

    overall_metrics['inter_annotator_agreement'] = agreement_scores
    overall_metrics['avg_inter_annotator_agreement'] = np.mean(list(agreement_scores.values())) if agreement_scores else 0.0

    return {
        'field_metrics': field_metrics,
        'overall_metrics': overall_metrics
    }
