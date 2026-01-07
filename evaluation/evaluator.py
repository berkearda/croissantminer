"""
Evaluation runner for CroissantMiner

Orchestrates the evaluation of extracted metadata against groundtruth annotations.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from .metrics import calculate_all_metrics, overall_accuracy, per_field_accuracy
from .groundtruth_parser import load_groundtruth, get_pdf_for_dataset


def load_extracted_metadata(extraction_output_path: str) -> Dict:
    """
    Load extracted metadata from JSON file

    Args:
        extraction_output_path: Path to extraction output JSON

    Returns:
        Dictionary of extracted metadata
    """
    with open(extraction_output_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def flatten_extracted_metadata(metadata: Dict) -> Dict[str, str]:
    """
    Flatten nested Croissant metadata structure to match groundtruth format

    Args:
        metadata: Nested metadata dictionary

    Returns:
        Flattened dictionary with sc: and rai: prefixed fields
    """
    flattened = {}

    # Map @id to sc:url if url is not present
    if '@id' in metadata and 'url' not in metadata:
        metadata['url'] = metadata['@id']

    # Top-level Schema.org fields (add sc: prefix)
    sc_fields = ['name', 'description', 'url', 'license', 'datePublished',
                 'inLanguage', 'publisher', 'creator']
    for field in sc_fields:
        if field in metadata:
            value = metadata[field]
            # Handle nested objects (like creator)
            if isinstance(value, dict):
                # Extract name from nested object
                if 'name' in value:
                    flattened[f'sc:{field}'] = value['name']
                else:
                    # Convert dict to string representation
                    flattened[f'sc:{field}'] = str(value)
            elif isinstance(value, list):
                # Join list items
                flattened[f'sc:{field}'] = ', '.join(str(v) for v in value)
            else:
                flattened[f'sc:{field}'] = str(value)

    # Croissant-specific fields
    cr_fields = ['isLiveDataset', 'citeAs', 'dataType', 'dataModality']
    for field in cr_fields:
        if field in metadata:
            value = metadata[field]
            if isinstance(value, list):
                flattened[f'cr:{field}'] = ', '.join(str(v) for v in value)
            else:
                flattened[f'cr:{field}'] = str(value)
        # Also check with cro: prefix
        cro_key = f'cro:{field}'
        if cro_key in metadata:
            value = metadata[cro_key]
            if isinstance(value, list):
                flattened[f'cr:{field}'] = ', '.join(str(v) for v in value)
            else:
                flattened[f'cr:{field}'] = str(value)

    # RAI fields from nested structure
    if 'rai:responsibleAIMetadata' in metadata:
        rai_metadata = metadata['rai:responsibleAIMetadata']
        rai_fields = ['dataCollection', 'dataCollectionTimeframe', 'dataAnnotationPlatform',
                      'annotatorDemographics', 'dataUseCases', 'personalSensitiveInformation']
        for field in rai_fields:
            # Try with rai: prefix first
            key_with_prefix = f'rai:{field}'
            if key_with_prefix in rai_metadata:
                value = rai_metadata[key_with_prefix]
                if isinstance(value, list):
                    flattened[key_with_prefix] = ', '.join(str(v) for v in value)
                else:
                    flattened[key_with_prefix] = str(value)
            # Try without prefix
            elif field in rai_metadata:
                value = rai_metadata[field]
                if isinstance(value, list):
                    flattened[f'rai:{field}'] = ', '.join(str(v) for v in value)
                else:
                    flattened[f'rai:{field}'] = str(value)

    return flattened


def compare_extraction(
    predicted_fields: Dict[str, str],
    groundtruth_annotations: List[Dict[str, str]],
    dataset_name: str,
    use_llm: bool = False
) -> Dict:
    """
    Compare extracted metadata against groundtruth annotations

    Args:
        predicted_fields: Extracted field values
        groundtruth_annotations: List of groundtruth annotations
        dataset_name: Name of the dataset
        use_llm: Whether to use LLM-based evaluation

    Returns:
        Comparison results with detailed metrics
    """
    print(f"\nEvaluating {dataset_name}...")

    # Calculate comprehensive metrics
    metrics = calculate_all_metrics(predicted_fields, groundtruth_annotations, use_llm=use_llm)

    # Add dataset metadata
    result = {
        'dataset_name': dataset_name,
        'num_annotators': len(groundtruth_annotations),
        'metrics': metrics
    }

    # Print summary
    if 'overall_metrics' in metrics:
        overall = metrics['overall_metrics']
        print(f"  Overall Accuracy (0.8 threshold): {overall.get('overall_accuracy_0.8', 0):.2%}")
        print(f"  Overall Accuracy (0.6 threshold): {overall.get('overall_accuracy_0.6', 0):.2%}")
        print(f"  Fields Evaluated: {overall.get('num_fields_evaluated', 0)}")
        print(f"  Avg Inter-Annotator Agreement: {overall.get('avg_inter_annotator_agreement', 0):.2%}")

    return result


def evaluate_against_groundtruth(
    extraction_output_path: str,
    groundtruth_dir: str,
    dataset_name: str,
    verbose: bool = True
) -> Dict:
    """
    Evaluate extraction output against groundtruth for a single dataset

    Args:
        extraction_output_path: Path to extraction output JSON
        groundtruth_dir: Directory containing parsed groundtruth
        dataset_name: Name of the dataset to evaluate
        verbose: Whether to print detailed output

    Returns:
        Evaluation results
    """
    # Load extracted metadata
    extracted_data = load_extracted_metadata(extraction_output_path)

    # Load groundtruth
    groundtruth = load_groundtruth(groundtruth_dir, dataset_name)

    if dataset_name not in groundtruth:
        raise ValueError(f"Groundtruth not found for dataset: {dataset_name}")

    groundtruth_annotations = groundtruth[dataset_name]

    # Extract fields from predicted data
    # Assumes extraction output has structure like: {'metadata': {...}}
    if 'metadata' in extracted_data:
        predicted_fields = extracted_data['metadata']
    elif 'croissant_metadata' in extracted_data:
        predicted_fields = extracted_data['croissant_metadata']
    else:
        # Assume the whole dict is the metadata
        predicted_fields = extracted_data

    # Flatten the nested structure to match groundtruth format
    predicted_fields = flatten_extracted_metadata(predicted_fields)

    # Compare
    result = compare_extraction(predicted_fields, groundtruth_annotations, dataset_name)

    if verbose:
        print_evaluation_summary(result)

    return result


def batch_evaluate(
    extraction_outputs_dir: str,
    groundtruth_dir: str,
    output_file: Optional[str] = None,
    verbose: bool = True,
    use_llm: bool = False
) -> Dict:
    """
    Evaluate all 8 papers in batch

    Args:
        extraction_outputs_dir: Directory containing extraction outputs
        groundtruth_dir: Directory containing parsed groundtruth
        output_file: Optional path to save results JSON
        verbose: Whether to print detailed output
        use_llm: Whether to use LLM-based evaluation

    Returns:
        Dictionary of all evaluation results
    """
    print("=" * 80)
    print("BATCH EVALUATION - 8 Papers")
    print("=" * 80)

    # Load all groundtruth
    all_groundtruth = load_groundtruth(groundtruth_dir)

    outputs_path = Path(extraction_outputs_dir)
    results = {}

    # Dataset name to PDF mapping
    from .groundtruth_parser import DATASET_PDF_MAPPING

    total_datasets = 0
    successful_evaluations = 0

    for dataset_name, pdf_filename in DATASET_PDF_MAPPING.items():
        total_datasets += 1

        # Find corresponding extraction output
        # Try several naming conventions
        possible_names = [
            f"{dataset_name.lower()}_extraction.json",
            f"{pdf_filename.replace('.pdf', '')}_extraction.json",
            f"{pdf_filename.replace('.pdf', '')}_metadata.json",
            f"{dataset_name.lower()}_metadata.json"
        ]

        extraction_file = None
        for name in possible_names:
            candidate = outputs_path / name
            if candidate.exists():
                extraction_file = candidate
                break

        if not extraction_file:
            print(f"\n⚠ Warning: No extraction output found for {dataset_name}")
            print(f"  Tried: {', '.join(possible_names)}")
            continue

        try:
            # Load and evaluate
            extracted_data = load_extracted_metadata(str(extraction_file))
            groundtruth_annotations = all_groundtruth.get(dataset_name, [])

            if not groundtruth_annotations:
                print(f"\n⚠ Warning: No groundtruth found for {dataset_name}")
                continue

            # Extract fields
            if 'metadata' in extracted_data:
                predicted_fields = extracted_data['metadata']
            elif 'croissant_metadata' in extracted_data:
                predicted_fields = extracted_data['croissant_metadata']
            else:
                predicted_fields = extracted_data

            # Flatten the nested structure to match groundtruth format
            predicted_fields = flatten_extracted_metadata(predicted_fields)

            # Evaluate
            result = compare_extraction(predicted_fields, groundtruth_annotations, dataset_name, use_llm=use_llm)
            results[dataset_name] = result
            successful_evaluations += 1

        except Exception as e:
            print(f"\n❌ Error evaluating {dataset_name}: {e}")
            import traceback
            traceback.print_exc()

    # Calculate aggregate statistics
    print("\n" + "=" * 80)
    print("AGGREGATE STATISTICS")
    print("=" * 80)
    print(f"Total Datasets: {total_datasets}")
    print(f"Successful Evaluations: {successful_evaluations}")
    print(f"Failed Evaluations: {total_datasets - successful_evaluations}")

    if successful_evaluations > 0:
        # Average metrics across all datasets
        avg_accuracy_08 = []
        avg_accuracy_06 = []
        avg_agreement = []

        for dataset_name, result in results.items():
            metrics = result.get('metrics', {})
            overall = metrics.get('overall_metrics', {})

            if 'overall_accuracy_0.8' in overall:
                avg_accuracy_08.append(overall['overall_accuracy_0.8'])
            if 'overall_accuracy_0.6' in overall:
                avg_accuracy_06.append(overall['overall_accuracy_0.6'])
            if 'avg_inter_annotator_agreement' in overall:
                avg_agreement.append(overall['avg_inter_annotator_agreement'])

        if avg_accuracy_08:
            print(f"\nAverage Accuracy (0.8 threshold): {sum(avg_accuracy_08)/len(avg_accuracy_08):.2%}")
        if avg_accuracy_06:
            print(f"Average Accuracy (0.6 threshold): {sum(avg_accuracy_06)/len(avg_accuracy_06):.2%}")
        if avg_agreement:
            print(f"Average Inter-Annotator Agreement: {sum(avg_agreement)/len(avg_agreement):.2%}")

    # Save results if output file specified
    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({
                'summary': {
                    'total_datasets': total_datasets,
                    'successful_evaluations': successful_evaluations,
                    'failed_evaluations': total_datasets - successful_evaluations
                },
                'results': results
            }, f, indent=2, ensure_ascii=False)

        print(f"\nResults saved to: {output_path}")

    return results


def print_evaluation_summary(evaluation_result: Dict):
    """
    Print a formatted summary of evaluation results

    Args:
        evaluation_result: Result from compare_extraction
    """
    print("\n" + "-" * 80)
    print(f"EVALUATION SUMMARY: {evaluation_result['dataset_name']}")
    print("-" * 80)

    metrics = evaluation_result.get('metrics', {})
    field_metrics = metrics.get('field_metrics', {})
    overall_metrics = metrics.get('overall_metrics', {})

    # Overall metrics
    print("\nOverall Metrics:")
    print(f"  Accuracy (0.8 threshold): {overall_metrics.get('overall_accuracy_0.8', 0):.2%}")
    print(f"  Accuracy (0.6 threshold): {overall_metrics.get('overall_accuracy_0.6', 0):.2%}")
    print(f"  Number of annotators: {overall_metrics.get('num_annotators', 0)}")
    print(f"  Fields evaluated: {overall_metrics.get('num_fields_evaluated', 0)}")
    print(f"  Avg inter-annotator agreement: {overall_metrics.get('avg_inter_annotator_agreement', 0):.2%}")

    # Per-field metrics
    if field_metrics:
        print("\nPer-Field Metrics (averaged across annotators):")
        print(f"{'Field Name':<40} {'F1 Score':>10} {'Precision':>10} {'Recall':>10}")
        print("-" * 80)

        # Sort by F1 score
        sorted_fields = sorted(
            field_metrics.items(),
            key=lambda x: x[1].get('avg_f1_score', 0),
            reverse=True
        )

        for field_name, field_data in sorted_fields:
            f1 = field_data.get('avg_f1_score', 0)
            precision = field_data.get('avg_precision', 0)
            recall = field_data.get('avg_recall', 0)
            print(f"{field_name:<40} {f1:>10.2%} {precision:>10.2%} {recall:>10.2%}")

    # Inter-annotator agreement
    agreement_scores = overall_metrics.get('inter_annotator_agreement', {})
    if agreement_scores:
        print("\nInter-Annotator Agreement by Field:")
        sorted_agreement = sorted(agreement_scores.items(), key=lambda x: x[1], reverse=True)
        for field_name, score in sorted_agreement[:10]:  # Show top 10
            print(f"  {field_name:<40} {score:>6.2%}")

    print("-" * 80)


def export_detailed_comparison(
    evaluation_result: Dict,
    output_path: str
):
    """
    Export detailed field-by-field comparison to JSON

    Args:
        evaluation_result: Result from compare_extraction
        output_path: Path to save detailed comparison
    """
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(evaluation_result, f, indent=2, ensure_ascii=False)

    print(f"Detailed comparison exported to: {output_file}")


if __name__ == "__main__":
    # Test the evaluator
    import sys
    from pathlib import Path

    base_dir = Path(__file__).parent.parent
    groundtruth_dir = base_dir / "groundtruth" / "parsed"

    if not groundtruth_dir.exists():
        print(f"Error: Groundtruth directory not found: {groundtruth_dir}")
        print("Please run groundtruth_parser.py first to parse the groundtruth PDF")
        sys.exit(1)

    # Example: Evaluate a single dataset (you would replace this with actual extraction output)
    print("Evaluator module loaded successfully!")
    print(f"Groundtruth directory: {groundtruth_dir}")
    print("\nTo use:")
    print("1. Run your extraction pipeline on the 8 PDFs")
    print("2. Call batch_evaluate() with the extraction outputs directory")
