"""
Evaluation metrics for CroissantMiner

Provides various metrics to evaluate the quality of extracted Croissant metadata
against human-annotated groundtruth. Includes statistical significance testing
(bootstrap CIs, McNemar's test, Cohen's h).
"""

import re
import json
from pathlib import Path
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


# ═══════════════════════════════════════════════════════════════════════
# Statistical Significance Testing
# ═══════════════════════════════════════════════════════════════════════


def bootstrap_ci(
    scores: List[float],
    n_bootstrap: int = 10000,
    ci: float = 0.95,
    seed: int = 42
) -> Tuple[float, float, float]:
    """
    Compute bootstrap confidence interval for the mean of scores.

    Args:
        scores: List of per-dataset accuracy scores
        n_bootstrap: Number of bootstrap resamples
        ci: Confidence level (e.g. 0.95 for 95% CI)
        seed: Random seed for reproducibility

    Returns:
        (mean, lower_bound, upper_bound)
    """
    scores = np.array(scores, dtype=float)
    rng = np.random.RandomState(seed)

    boot_means = np.empty(n_bootstrap)
    n = len(scores)
    for i in range(n_bootstrap):
        sample = scores[rng.randint(0, n, size=n)]
        boot_means[i] = np.mean(sample)

    alpha = 1 - ci
    lower = np.percentile(boot_means, 100 * alpha / 2)
    upper = np.percentile(boot_means, 100 * (1 - alpha / 2))

    return float(np.mean(scores)), float(lower), float(upper)


def mcnemar_test(
    model_a_correct: List[bool],
    model_b_correct: List[bool]
) -> Tuple[float, float]:
    """
    McNemar's test for paired nominal data.

    Compares two models on the same set of items. Tests whether the
    disagreements between models are symmetric.

    Args:
        model_a_correct: Boolean array — True if model A got item correct
        model_b_correct: Boolean array — True if model B got item correct

    Returns:
        (chi2_statistic, p_value)
    """
    a = np.array(model_a_correct, dtype=bool)
    b = np.array(model_b_correct, dtype=bool)

    if len(a) != len(b):
        raise ValueError("Arrays must have the same length")

    # Contingency: b = count where A correct & B wrong, c = A wrong & B correct
    b_count = int(np.sum(a & ~b))  # A right, B wrong
    c_count = int(np.sum(~a & b))  # A wrong, B right

    # McNemar's chi-squared with continuity correction
    if b_count + c_count == 0:
        return 0.0, 1.0

    chi2 = (abs(b_count - c_count) - 1) ** 2 / (b_count + c_count)

    # p-value from chi-squared distribution with 1 df
    from scipy.stats import chi2 as chi2_dist
    p_value = 1 - chi2_dist.cdf(chi2, df=1)

    return float(chi2), float(p_value)


def cohens_h(p1: float, p2: float) -> float:
    """
    Cohen's h effect size for comparing two proportions.

    Args:
        p1: First proportion (e.g. model A accuracy)
        p2: Second proportion (e.g. model B accuracy)

    Returns:
        Effect size h (positive means p1 > p2)
    """
    return float(2 * np.arcsin(np.sqrt(p1)) - 2 * np.arcsin(np.sqrt(p2)))


def krippendorff_alpha(
    reliability_data: List[List[Optional[float]]],
    level: str = "nominal"
) -> float:
    """
    Krippendorff's alpha for inter-annotator agreement.

    Args:
        reliability_data: List of annotator rows, each a list of ratings.
                          None for missing ratings.
        level: Measurement level — 'nominal', 'ordinal', 'interval', 'ratio'

    Returns:
        Krippendorff's alpha (-1.0 to 1.0)
    """
    # Build units: list of (unit_index, value) pairs per observer
    units = {}
    for observer_idx, row in enumerate(reliability_data):
        for unit_idx, value in enumerate(row):
            if value is not None:
                if unit_idx not in units:
                    units[unit_idx] = []
                units[unit_idx].append(value)

    # Only keep units with 2+ coders
    pairable = {k: v for k, v in units.items() if len(v) >= 2}
    if not pairable:
        return 0.0

    # Difference function
    if level == "nominal":
        def delta(v1, v2):
            return 0.0 if v1 == v2 else 1.0
    elif level in ("interval", "ratio"):
        def delta(v1, v2):
            return (v1 - v2) ** 2
    elif level == "ordinal":
        all_vals = sorted(set(v for vals in pairable.values() for v in vals))
        rank_map = {v: i for i, v in enumerate(all_vals)}
        def delta(v1, v2):
            return (rank_map[v1] - rank_map[v2]) ** 2
    else:
        raise ValueError(f"Unknown level: {level}")

    # Observed disagreement
    Do = 0.0
    n_pairs_o = 0
    for vals in pairable.values():
        m = len(vals)
        for i in range(m):
            for j in range(i + 1, m):
                Do += delta(vals[i], vals[j])
                n_pairs_o += 1

    if n_pairs_o == 0:
        return 1.0
    Do /= n_pairs_o

    # Expected disagreement
    all_values = [v for vals in pairable.values() for v in vals]
    n_total = len(all_values)
    De = 0.0
    n_pairs_e = 0
    for i in range(n_total):
        for j in range(i + 1, n_total):
            De += delta(all_values[i], all_values[j])
            n_pairs_e += 1

    if n_pairs_e == 0:
        return 1.0
    De /= n_pairs_e

    if De == 0:
        return 1.0

    return float(1 - Do / De)


def _load_eval_report(path: Path) -> Dict:
    """Load an evaluation report JSON and extract per-field scores.

    Uses the weighted scoring from llm_accuracy (CORRECT=1.0,
    PARTIALLY_CORRECT=0.5, INCORRECT/MISSING=0.0) for accuracy.
    Uses binary CORRECT-or-not for McNemar's test.
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    per_field_correct = {}  # field -> list of bools (one per dataset)
    per_dataset_accuracy = {}  # dataset -> weighted accuracy (from llm_accuracy)
    all_field_scores = {}  # (dataset, field) -> score (0.0, 0.5, or 1.0)

    for ds_name, ds_data in data["results"].items():
        stats = ds_data["metrics"]["overall_stats"]
        per_dataset_accuracy[ds_name] = stats["llm_accuracy"]

        for field, result in ds_data["metrics"]["field_results"].items():
            if field not in per_field_correct:
                per_field_correct[field] = []
            # Binary: only CORRECT counts as correct for McNemar
            per_field_correct[field].append(result["score"] >= 1.0)
            # Weighted score for accuracy computation
            all_field_scores[(ds_name, field)] = result["score"]

    return {
        "per_dataset_accuracy": per_dataset_accuracy,
        "per_field_correct": per_field_correct,
        "all_field_scores": all_field_scores,
    }


def run_all_significance_tests(
    evaluation_outputs_dir: str = "evaluation_outputs",
    ci_level: float = 0.95,
    n_bootstrap: int = 10000,
) -> Dict:
    """
    Run bootstrap CIs, McNemar's tests, and Cohen's h on available evaluation data.

    Loads evaluation reports from evaluation_outputs/ and model_comparison/,
    computes statistical tests, and prints a LaTeX-ready summary table.

    Args:
        evaluation_outputs_dir: Path to evaluation outputs directory
        ci_level: Confidence level for bootstrap CIs
        n_bootstrap: Number of bootstrap resamples

    Returns:
        Dictionary with all test results
    """
    base = Path(evaluation_outputs_dir)

    # ── Load available evaluation reports ──
    models = {}

    # Claude Sonnet 4.5 (full-pdf) — primary model
    full_pdf_path = base / "evaluation_report_full_pdf.json"
    if full_pdf_path.exists():
        models["Claude Sonnet 4.5"] = _load_eval_report(full_pdf_path)

    # Claude Sonnet 4.5 (lenient / multi-section) — ablation
    lenient_path = base / "evaluation_report_lenient.json"
    if lenient_path.exists():
        models["Claude (lenient)"] = _load_eval_report(lenient_path)

    # Gemini 2.5 Pro — from model_comparison
    gemini_path = base.parent / "model_comparison" / "gemini_pro_field_analysis.json"
    if gemini_path.exists():
        with open(gemini_path, "r", encoding="utf-8") as f:
            gemini_data = json.load(f)
        # Reconstruct per-dataset accuracy from per_field_details
        if "per_field_details" in gemini_data:
            gemini_per_ds = {}
            gemini_per_field = {}
            gemini_all_scores = {}
            for field, details in gemini_data["per_field_details"].items():
                correct_list = []
                if "per_dataset" in details:
                    per_ds = details["per_dataset"]
                    # Handle both list-of-dicts and dict-of-dicts
                    items = per_ds.items() if isinstance(per_ds, dict) else [
                        (entry["dataset"], entry) for entry in per_ds
                    ]
                    for ds_name, ds_result in items:
                        is_correct = ds_result.get("category") == "CORRECT"
                        correct_list.append(is_correct)
                        # Use weighted score (0-100 scale → 0-1)
                        raw_score = ds_result.get("score", 0)
                        weighted = raw_score / 100.0 if raw_score > 1 else raw_score
                        gemini_all_scores[(ds_name, field)] = weighted
                        if ds_name not in gemini_per_ds:
                            gemini_per_ds[ds_name] = {"weighted_sum": 0, "total": 0}
                        gemini_per_ds[ds_name]["total"] += 1
                        gemini_per_ds[ds_name]["weighted_sum"] += weighted
                gemini_per_field[field] = correct_list

            models["Gemini 2.5 Pro"] = {
                "per_dataset_accuracy": {
                    ds: s["weighted_sum"] / s["total"] for ds, s in gemini_per_ds.items()
                },
                "per_field_correct": gemini_per_field,
                "all_field_scores": gemini_all_scores,
            }

    if not models:
        print("No evaluation data found.")
        return {}

    # ── Compute bootstrap CIs ──
    print("=" * 80)
    print("STATISTICAL SIGNIFICANCE TESTS")
    print("=" * 80)

    results = {}
    for model_name, model_data in models.items():
        ds_accuracies = list(model_data["per_dataset_accuracy"].values())
        mean_acc, ci_low, ci_high = bootstrap_ci(ds_accuracies, n_bootstrap, ci_level)
        results[model_name] = {
            "mean": mean_acc,
            "ci_low": ci_low,
            "ci_high": ci_high,
            "n_datasets": len(ds_accuracies),
            "per_dataset": model_data["per_dataset_accuracy"],
        }

    # ── Pairwise McNemar's tests ──
    # Build per-item binary vectors aligned across models
    reference_model = "Claude Sonnet 4.5"
    if reference_model not in models:
        reference_model = list(models.keys())[0]

    ref_data = models[reference_model]
    ref_scores = ref_data["all_field_scores"]

    pairwise = {}
    for model_name, model_data in models.items():
        if model_name == reference_model:
            continue

        # Find common (dataset, field) pairs
        other_scores = model_data["all_field_scores"]
        common_keys = sorted(set(ref_scores.keys()) & set(other_scores.keys()))

        if not common_keys:
            continue

        ref_correct = [ref_scores[k] >= 1.0 for k in common_keys]
        other_correct = [other_scores[k] >= 1.0 for k in common_keys]

        chi2, p_val = mcnemar_test(ref_correct, other_correct)
        h = cohens_h(
            np.mean(ref_correct),
            np.mean(other_correct)
        )

        pairwise[model_name] = {
            "chi2": chi2,
            "p_value": p_val,
            "cohens_h": h,
            "n_common": len(common_keys),
            "ref_acc": np.mean(ref_correct),
            "other_acc": np.mean(other_correct),
        }

    # ── Print results ──
    print(f"\nBootstrap {ci_level*100:.0f}% Confidence Intervals ({n_bootstrap:,} resamples)")
    print(f"Reference model: {reference_model}")
    print()

    # Table header
    print(f"{'Model':<22} {'Accuracy':>8} {'95% CI':>16} {'vs Ref (p)':>12} {'Effect (h)':>11} {'n':>5}")
    print("-" * 80)

    # Reference model row
    r = results[reference_model]
    print(f"{reference_model:<22} {r['mean']*100:>7.1f}% [{r['ci_low']*100:.1f}, {r['ci_high']*100:.1f}] {'—':>12} {'—':>11} {r['n_datasets']:>5}")

    # Other models
    for model_name in sorted(results.keys()):
        if model_name == reference_model:
            continue
        r = results[model_name]
        p_info = pairwise.get(model_name, {})
        if p_info:
            p_val = p_info["p_value"]
            p_str = f"p={p_val:.3f}{'*' if p_val < 0.05 else ''}"
            h_str = f"h={p_info['cohens_h']:.3f}"
            n = p_info["n_common"]
        else:
            p_str = "—"
            h_str = "—"
            n = r["n_datasets"]

        print(f"{model_name:<22} {r['mean']*100:>7.1f}% [{r['ci_low']*100:.1f}, {r['ci_high']*100:.1f}] {p_str:>12} {h_str:>11} {n:>5}")

    # ── LaTeX table ──
    print(f"\n{'=' * 80}")
    print("LATEX TABLE")
    print(f"{'=' * 80}")
    print()
    print(r"\begin{table}[h]")
    print(r"\centering")
    print(r"\caption{Model comparison with statistical significance tests.}")
    print(r"\begin{tabular}{lcccc}")
    print(r"\toprule")
    print(r"Model & Accuracy & 95\% CI & vs Claude ($p$) & Effect size \\")
    print(r"\midrule")

    r = results[reference_model]
    print(f"Claude Sonnet 4.5 & \\textbf{{{r['mean']*100:.1f}\\%}} & "
          f"[{r['ci_low']*100:.1f}, {r['ci_high']*100:.1f}] & --- & --- \\\\")

    for model_name in sorted(results.keys()):
        if model_name == reference_model:
            continue
        r = results[model_name]
        p_info = pairwise.get(model_name, {})
        if p_info:
            p_val = p_info["p_value"]
            p_str = f"$p={p_val:.3f}$" + (r"\textsuperscript{*}" if p_val < 0.05 else "")
            h_str = f"$h={abs(p_info['cohens_h']):.3f}$"
        else:
            p_str = "---"
            h_str = "---"
        acc_str = f"{r['mean']*100:.1f}\\%"
        ci_str = f"[{r['ci_low']*100:.1f}, {r['ci_high']*100:.1f}]"
        print(f"{model_name} & {acc_str} & {ci_str} & {p_str} & {h_str} \\\\")

    print(r"\bottomrule")
    print(r"\end{tabular}")
    print(r"\end{table}")

    # ── Per-dataset breakdown ──
    print(f"\n{'=' * 80}")
    print("PER-DATASET ACCURACY")
    print(f"{'=' * 80}")

    all_datasets = sorted(set(
        ds for m in results.values() for ds in m.get("per_dataset", {}).keys()
    ))

    header = f"{'Dataset':<20}"
    for model_name in sorted(results.keys()):
        header += f" {model_name:>18}"
    print(header)
    print("-" * (20 + 19 * len(results)))

    for ds in all_datasets:
        row = f"{ds:<20}"
        for model_name in sorted(results.keys()):
            acc = results[model_name].get("per_dataset", {}).get(ds)
            if acc is not None:
                row += f" {acc*100:>17.1f}%"
            else:
                row += f" {'—':>18}"
        print(row)

    return {"results": results, "pairwise": pairwise}
