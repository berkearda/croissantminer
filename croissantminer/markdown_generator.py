"""
Markdown report generator for LLM evaluation results

Generates detailed markdown reports showing LLM evaluation results
with correctly extracted values.
"""

import json
from pathlib import Path
from typing import Dict, Optional, Any


def get_extracted_value(extraction_data: Dict, field_name: str) -> Optional[str]:
    """
    Get extracted value for a field - matches evaluator.py flatten logic

    Args:
        extraction_data: Raw extraction JSON data
        field_name: Field name with prefix (e.g., 'sc:name', 'rai:dataCollection')

    Returns:
        Extracted value as string, or None if not found
    """
    if not extraction_data:
        return None

    # Handle sc: fields
    if field_name.startswith('sc:'):
        field_without_prefix = field_name.replace('sc:', '')

        # Special case: sc:url can come from @id
        if field_name == 'sc:url':
            if 'url' in extraction_data:
                return str(extraction_data['url'])
            elif '@id' in extraction_data:
                return str(extraction_data['@id'])

        # Check direct field
        if field_without_prefix in extraction_data:
            value = extraction_data[field_without_prefix]

            # Handle nested objects (like creator/publisher)
            if isinstance(value, dict):
                if 'name' in value:
                    return str(value['name'])
                else:
                    return str(value)
            elif isinstance(value, list):
                # Handle list of objects
                if len(value) > 0 and isinstance(value[0], dict):
                    names = [str(v.get('name', v)) for v in value]
                    return ', '.join(names)
                else:
                    return ', '.join(str(v) for v in value)
            else:
                return str(value)

    # Handle cr: fields (can also be cro: in extraction)
    elif field_name.startswith('cr:'):
        field_without_prefix = field_name.replace('cr:', '')

        # Check with cr: prefix
        if field_name in extraction_data:
            value = extraction_data[field_name]
            if isinstance(value, list):
                return ', '.join(str(v) for v in value)
            return str(value)

        # Check with cro: prefix
        cro_key = f'cro:{field_without_prefix}'
        if cro_key in extraction_data:
            value = extraction_data[cro_key]
            if isinstance(value, list):
                return ', '.join(str(v) for v in value)
            return str(value)

        # Check without prefix
        if field_without_prefix in extraction_data:
            value = extraction_data[field_without_prefix]
            if isinstance(value, dict) and 'name' in value:
                return str(value['name'])
            elif isinstance(value, list):
                return ', '.join(str(v) for v in value)
            return str(value)

    # Handle rai: fields (nested under rai:responsibleAIMetadata)
    elif field_name.startswith('rai:'):
        if 'rai:responsibleAIMetadata' in extraction_data:
            rai_metadata = extraction_data['rai:responsibleAIMetadata']

            # Check with rai: prefix
            if field_name in rai_metadata:
                value = rai_metadata[field_name]
                if isinstance(value, list):
                    return ', '.join(str(v) for v in value)
                return str(value)

            # Check without prefix
            field_without_prefix = field_name.replace('rai:', '')
            if field_without_prefix in rai_metadata:
                value = rai_metadata[field_without_prefix]
                if isinstance(value, list):
                    return ', '.join(str(v) for v in value)
                return str(value)

    return None


def generate_detailed_markdown(
    report_path: str,
    extraction_dir: str,
    groundtruth_dir: str,
    output_path: str
) -> None:
    """
    Generate detailed markdown report with correct extracted values

    Args:
        report_path: Path to evaluation report JSON
        extraction_dir: Directory with extraction output JSONs
        groundtruth_dir: Directory with groundtruth annotation JSONs
        output_path: Path to save markdown report
    """
    # Load evaluation report
    with open(report_path, 'r') as f:
        report = json.load(f)

    # Paper ID to dataset name mapping
    paper_to_dataset = {
        '1405.0312v3': 'LibriSpeech',
        '2012.03411v2': 'MLS',
        '2009.03300v3': 'MMLU',
        '2106.03193v1': 'FLORES',
        '1602.07332v1': 'CIFAR',
        '2310.02255v3': 'DOLLY',
        '2311.16502v4': 'MSCOCO',
        '2404.00498v2': 'MMMU'
    }
    dataset_to_paper = {v: k for k, v in paper_to_dataset.items()}

    groundtruth_path = Path(groundtruth_dir)

    markdown_lines = []
    markdown_lines.append("# LLM Evaluation Results - Detailed Report (FINAL)")
    markdown_lines.append("")
    markdown_lines.append("**Date:** October 28, 2025")
    markdown_lines.append("**Model:** GPT-4o-mini (temperature=0.0)")
    markdown_lines.append("**Status:** ✅ All fixes applied + Cache cleaned")
    markdown_lines.append("")
    markdown_lines.append("---")
    markdown_lines.append("")

    # Overall statistics
    total_fields = 0
    total_score = 0
    for dataset_name, dataset_data in report['results'].items():
        stats = dataset_data['metrics']['overall_stats']
        total_fields += stats['num_fields']
        total_score += stats['llm_accuracy'] * stats['num_fields']

    overall_accuracy = total_score / total_fields if total_fields > 0 else 0

    markdown_lines.append("## Overall Statistics")
    markdown_lines.append("")
    markdown_lines.append(f"- **Overall Accuracy:** {overall_accuracy:.1%}")
    markdown_lines.append(f"- **Total Fields Evaluated:** {total_fields}")
    markdown_lines.append(f"- **Total Datasets:** {len(report['results'])}")
    markdown_lines.append("")
    markdown_lines.append("---")
    markdown_lines.append("")

    # Process each dataset
    for dataset_name, dataset_data in sorted(report['results'].items()):
        markdown_lines.append(f"## Dataset: {dataset_name}")
        markdown_lines.append("")

        stats = dataset_data['metrics']['overall_stats']
        markdown_lines.append(f"**Accuracy:** {stats['llm_accuracy']:.1%}")
        markdown_lines.append(f"**Fields Evaluated:** {stats['num_fields']}")
        markdown_lines.append("")
        markdown_lines.append("**Category Distribution:**")
        markdown_lines.append(f"- CORRECT: {stats['correct_count']}")
        markdown_lines.append(f"- PARTIALLY_CORRECT: {stats['partially_correct_count']}")
        markdown_lines.append(f"- INCORRECT: {stats['incorrect_count']}")
        markdown_lines.append(f"- MISSING: {stats['missing_count']}")
        markdown_lines.append("")
        markdown_lines.append("---")
        markdown_lines.append("")

        # Load extraction output
        paper_id = dataset_to_paper.get(dataset_name)
        if paper_id:
            extraction_file = Path(extraction_dir) / f"{paper_id}_extraction.json"
            try:
                with open(extraction_file, 'r') as f:
                    extraction_data = json.load(f)
            except FileNotFoundError:
                extraction_data = {}
        else:
            extraction_data = {}

        # Load groundtruth annotations
        gt_file = groundtruth_path / f"{dataset_name.lower()}_annotations.json"
        try:
            with open(gt_file, 'r') as f:
                gt_annotations = json.load(f)
        except FileNotFoundError:
            gt_annotations = []

        # Process each field
        field_results = dataset_data['metrics']['field_results']

        for field_name, field_result in sorted(field_results.items()):
            category = field_result['category']
            score = field_result['score']

            # Emoji for category
            if category == 'CORRECT':
                emoji = '✅'
            elif category == 'PARTIALLY_CORRECT':
                emoji = '🟡'
            elif category == 'INCORRECT':
                emoji = '❌'
            else:  # MISSING
                emoji = '⚪'

            markdown_lines.append(f"### {emoji} Field: `{field_name}`")
            markdown_lines.append("")
            markdown_lines.append(f"**Final Result**: {category} (Score: {score})")
            markdown_lines.append("")

            # Get extracted value using correct function
            extracted_value = get_extracted_value(extraction_data, field_name)
            markdown_lines.append("**Extracted Value**:")
            markdown_lines.append("```")
            if extracted_value:
                markdown_lines.append(extracted_value)
            else:
                markdown_lines.append("(not extracted)")
            markdown_lines.append("```")
            markdown_lines.append("")

            # Show evaluation by each annotator
            markdown_lines.append("**Evaluation by Each Annotator**:")
            markdown_lines.append("")

            all_categories = field_result.get('all_categories', [])
            all_scores = field_result.get('all_scores', [])
            all_reasonings = field_result.get('all_reasonings', [])

            for i, (cat, scr, reasoning) in enumerate(zip(all_categories, all_scores, all_reasonings)):
                # Get groundtruth for this annotator
                gt_value = "(not provided)"
                if i < len(gt_annotations) and field_name in gt_annotations[i]:
                    gt_val = gt_annotations[i][field_name]
                    if isinstance(gt_val, list):
                        gt_value = ', '.join(str(v) for v in gt_val)
                    else:
                        gt_value = str(gt_val)

                # Emoji for this annotator's result
                if cat == 'CORRECT':
                    ann_emoji = '✅'
                elif cat == 'PARTIALLY_CORRECT':
                    ann_emoji = '🟡'
                elif cat == 'INCORRECT':
                    ann_emoji = '❌'
                else:
                    ann_emoji = '⚪'

                markdown_lines.append(f"**Annotator {i+1}**: {ann_emoji} {cat} (score: {scr})")
                markdown_lines.append("")
                markdown_lines.append(f"- Groundtruth: `{gt_value}`")
                markdown_lines.append(f"- LLM Reasoning: \"{reasoning}\"")
                markdown_lines.append("")

            markdown_lines.append("---")
            markdown_lines.append("")

    # Write to file
    with open(output_path, 'w') as f:
        f.write('\n'.join(markdown_lines))

    print(f"✅ Generated detailed markdown: {output_path}")
    print(f"   Total lines: {len(markdown_lines)}")
    print(f"   Datasets: {len(report['results'])}")
    print(f"   Total fields: {total_fields}")
    print(f"   Overall accuracy: {overall_accuracy:.1%}")
