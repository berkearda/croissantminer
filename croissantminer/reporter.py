"""
Reporting and visualization for CroissantMiner evaluation

Generates comprehensive reports and visualizations of evaluation results.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
import csv


def generate_report(
    evaluation_results: Dict,
    output_dir: str,
    report_name: str = "evaluation_report"
) -> str:
    """
    Generate a comprehensive evaluation report in multiple formats

    Args:
        evaluation_results: Results from batch_evaluate()
        output_dir: Directory to save reports
        report_name: Base name for report files

    Returns:
        Path to the main report file
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Generate markdown report
    markdown_file = output_path / f"{report_name}.md"
    with open(markdown_file, 'w', encoding='utf-8') as f:
        f.write(generate_markdown_report(evaluation_results))

    print(f"Markdown report saved to: {markdown_file}")

    # Generate CSV summary
    csv_file = output_path / f"{report_name}_summary.csv"
    generate_csv_summary(evaluation_results, str(csv_file))
    print(f"CSV summary saved to: {csv_file}")

    # Generate detailed field metrics CSV
    field_csv_file = output_path / f"{report_name}_field_metrics.csv"
    generate_field_metrics_csv(evaluation_results, str(field_csv_file))
    print(f"Field metrics CSV saved to: {field_csv_file}")

    # Generate JSON report (full data)
    json_file = output_path / f"{report_name}.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(evaluation_results, f, indent=2, ensure_ascii=False)
    print(f"JSON report saved to: {json_file}")

    return str(markdown_file)


def generate_markdown_report(evaluation_results: Dict) -> str:
    """
    Generate a markdown-formatted evaluation report

    Args:
        evaluation_results: Results from batch_evaluate()

    Returns:
        Markdown-formatted report string
    """
    lines = []

    # Header
    lines.append("# CroissantMiner Evaluation Report")
    lines.append("")
    lines.append("## Summary")
    lines.append("")

    # Overall statistics
    if 'summary' in evaluation_results:
        summary = evaluation_results['summary']
        lines.append(f"- **Total Datasets**: {summary.get('total_datasets', 0)}")
        lines.append(f"- **Successful Evaluations**: {summary.get('successful_evaluations', 0)}")
        lines.append(f"- **Failed Evaluations**: {summary.get('failed_evaluations', 0)}")
        lines.append("")

    # Get results
    results = evaluation_results.get('results', evaluation_results)

    # Calculate aggregate metrics
    if results:
        accuracies_08 = []
        accuracies_06 = []
        llm_accuracies = []
        agreements = []

        for dataset_name, result in results.items():
            metrics = result.get('metrics', {})
            overall = metrics.get('overall_metrics', {})
            overall_stats = metrics.get('overall_stats', {})  # For LLM evaluation

            # Check if this is LLM-based evaluation
            if 'llm_accuracy' in overall_stats:
                llm_accuracies.append(overall_stats['llm_accuracy'])
            else:
                # String-based evaluation
                if 'overall_accuracy_0.8' in overall:
                    accuracies_08.append(overall['overall_accuracy_0.8'])
                if 'overall_accuracy_0.6' in overall:
                    accuracies_06.append(overall['overall_accuracy_0.6'])

            if 'avg_inter_annotator_agreement' in overall:
                agreements.append(overall['avg_inter_annotator_agreement'])

        if llm_accuracies:
            avg_llm_acc = sum(llm_accuracies) / len(llm_accuracies)
            lines.append(f"- **Average LLM-based Accuracy**: {avg_llm_acc:.2%}")
        elif accuracies_08:
            avg_acc_08 = sum(accuracies_08) / len(accuracies_08)
            lines.append(f"- **Average Accuracy (0.8 threshold)**: {avg_acc_08:.2%}")

        if accuracies_06:
            avg_acc_06 = sum(accuracies_06) / len(accuracies_06)
            lines.append(f"- **Average Accuracy (0.6 threshold)**: {avg_acc_06:.2%}")

        if agreements:
            avg_agreement = sum(agreements) / len(agreements)
            lines.append(f"- **Average Inter-Annotator Agreement**: {avg_agreement:.2%}")

        lines.append("")

    # Per-dataset results
    lines.append("## Results by Dataset")
    lines.append("")

    for dataset_name, result in results.items():
        lines.append(f"### {dataset_name}")
        lines.append("")

        metrics = result.get('metrics', {})
        overall_metrics = metrics.get('overall_metrics', {})
        overall_stats = metrics.get('overall_stats', {})
        field_metrics = metrics.get('field_metrics', {})
        field_results = metrics.get('field_results', {})  # For LLM evaluation

        # Check if this is LLM evaluation
        is_llm_eval = bool(field_results)

        # Overall metrics
        lines.append("**Overall Metrics:**")
        lines.append("")

        if is_llm_eval:
            # LLM-based metrics
            lines.append(f"- LLM-based Accuracy: {overall_stats.get('llm_accuracy', 0):.2%}")
            lines.append(f"- Fields evaluated: {overall_stats.get('num_fields', 0)}")
            lines.append(f"- CORRECT: {overall_stats.get('correct_count', 0)}")
            lines.append(f"- PARTIALLY_CORRECT: {overall_stats.get('partially_correct_count', 0)}")
            lines.append(f"- INCORRECT: {overall_stats.get('incorrect_count', 0)}")
            lines.append(f"- MISSING: {overall_stats.get('missing_count', 0)}")
        else:
            # String-based metrics
            lines.append(f"- Accuracy (0.8 threshold): {overall_metrics.get('overall_accuracy_0.8', 0):.2%}")
            lines.append(f"- Accuracy (0.6 threshold): {overall_metrics.get('overall_accuracy_0.6', 0):.2%}")
            lines.append(f"- Number of annotators: {overall_metrics.get('num_annotators', 0)}")
            lines.append(f"- Fields evaluated: {overall_metrics.get('num_fields_evaluated', 0)}")
            lines.append(f"- Avg inter-annotator agreement: {overall_metrics.get('avg_inter_annotator_agreement', 0):.2%}")

        lines.append("")

        # Field-level metrics table
        if is_llm_eval and field_results:
            lines.append("**Field-Level Metrics (LLM Judge):**")
            lines.append("")
            lines.append("| Field Name | Score | Category | Reasoning |")
            lines.append("|------------|-------|----------|-----------|")

            # Sort by score
            sorted_fields = sorted(
                field_results.items(),
                key=lambda x: x[1].get('score', 0),
                reverse=True
            )

            for field_name, field_data in sorted_fields:
                score = field_data.get('score', 0)
                category = field_data.get('category', 'UNKNOWN')
                reasoning = field_data.get('reasoning', '')[:50] + '...' if len(field_data.get('reasoning', '')) > 50 else field_data.get('reasoning', '')
                lines.append(f"| {field_name} | {score:.2f} | {category} | {reasoning} |")

            lines.append("")

        elif field_metrics:
            lines.append("**Field-Level Metrics:**")
            lines.append("")
            lines.append("| Field Name | F1 Score | Precision | Recall | Exact Match Rate |")
            lines.append("|------------|----------|-----------|--------|------------------|")

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
                exact = field_data.get('exact_match_rate', 0)
                lines.append(f"| {field_name} | {f1:.2%} | {precision:.2%} | {recall:.2%} | {exact:.2%} |")

            lines.append("")

    # Recommendations
    lines.append("## Recommendations")
    lines.append("")
    lines.append("Based on the evaluation results:")
    lines.append("")

    # Analyze which fields perform poorly
    all_field_scores = {}
    for dataset_name, result in results.items():
        field_metrics = result.get('metrics', {}).get('field_metrics', {})
        for field_name, field_data in field_metrics.items():
            if field_name not in all_field_scores:
                all_field_scores[field_name] = []
            all_field_scores[field_name].append(field_data.get('avg_f1_score', 0))

    # Fields with low average F1 scores
    avg_field_scores = {
        field: sum(scores) / len(scores)
        for field, scores in all_field_scores.items()
    }

    poor_fields = [(field, score) for field, score in avg_field_scores.items() if score < 0.5]
    poor_fields.sort(key=lambda x: x[1])

    if poor_fields:
        lines.append("### Fields Needing Improvement")
        lines.append("")
        for field, score in poor_fields[:5]:  # Top 5 worst
            lines.append(f"- **{field}**: {score:.2%} average F1 score")
        lines.append("")

    # Good performing fields
    good_fields = [(field, score) for field, score in avg_field_scores.items() if score >= 0.8]
    good_fields.sort(key=lambda x: x[1], reverse=True)

    if good_fields:
        lines.append("### Well-Performing Fields")
        lines.append("")
        for field, score in good_fields[:5]:  # Top 5 best
            lines.append(f"- **{field}**: {score:.2%} average F1 score")
        lines.append("")

    return "\n".join(lines)


def generate_csv_summary(evaluation_results: Dict, output_file: str):
    """
    Generate CSV summary of evaluation results

    Args:
        evaluation_results: Results from batch_evaluate()
        output_file: Path to save CSV file
    """
    results = evaluation_results.get('results', evaluation_results)

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)

        # Header
        writer.writerow([
            'Dataset',
            'Accuracy (0.8)',
            'Accuracy (0.6)',
            'Num Annotators',
            'Fields Evaluated',
            'Avg Inter-Annotator Agreement'
        ])

        # Data rows
        for dataset_name, result in results.items():
            metrics = result.get('metrics', {})
            overall = metrics.get('overall_metrics', {})

            writer.writerow([
                dataset_name,
                f"{overall.get('overall_accuracy_0.8', 0):.4f}",
                f"{overall.get('overall_accuracy_0.6', 0):.4f}",
                overall.get('num_annotators', 0),
                overall.get('num_fields_evaluated', 0),
                f"{overall.get('avg_inter_annotator_agreement', 0):.4f}"
            ])


def generate_field_metrics_csv(evaluation_results: Dict, output_file: str):
    """
    Generate detailed field-level metrics CSV

    Args:
        evaluation_results: Results from batch_evaluate()
        output_file: Path to save CSV file
    """
    results = evaluation_results.get('results', evaluation_results)

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)

        # Header
        writer.writerow([
            'Dataset',
            'Field Name',
            'F1 Score',
            'Precision',
            'Recall',
            'Exact Match Rate',
            'Partial Match (0.8) Rate',
            'Cosine Similarity',
            'Num Annotators'
        ])

        # Data rows
        for dataset_name, result in results.items():
            field_metrics = result.get('metrics', {}).get('field_metrics', {})

            for field_name, field_data in field_metrics.items():
                writer.writerow([
                    dataset_name,
                    field_name,
                    f"{field_data.get('avg_f1_score', 0):.4f}",
                    f"{field_data.get('avg_precision', 0):.4f}",
                    f"{field_data.get('avg_recall', 0):.4f}",
                    f"{field_data.get('exact_match_rate', 0):.4f}",
                    f"{field_data.get('partial_match_0.8_rate', 0):.4f}",
                    f"{field_data.get('avg_cosine_similarity', 0):.4f}",
                    field_data.get('num_annotators', 0)
                ])


def visualize_results(evaluation_results: Dict, output_dir: str):
    """
    Generate visualizations of evaluation results

    Args:
        evaluation_results: Results from batch_evaluate()
        output_dir: Directory to save visualizations
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    try:
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("Warning: matplotlib not installed. Skipping visualizations.")
        print("Install with: pip install matplotlib")
        return

    results = evaluation_results.get('results', evaluation_results)

    # 1. Overall accuracy by dataset
    datasets = []
    acc_08 = []
    acc_06 = []

    for dataset_name, result in results.items():
        overall = result.get('metrics', {}).get('overall_metrics', {})
        datasets.append(dataset_name)
        acc_08.append(overall.get('overall_accuracy_0.8', 0))
        acc_06.append(overall.get('overall_accuracy_0.6', 0))

    if datasets:
        fig, ax = plt.subplots(figsize=(12, 6))
        x = np.arange(len(datasets))
        width = 0.35

        ax.bar(x - width/2, acc_08, width, label='Threshold 0.8')
        ax.bar(x + width/2, acc_06, width, label='Threshold 0.6')

        ax.set_xlabel('Dataset')
        ax.set_ylabel('Accuracy')
        ax.set_title('Overall Accuracy by Dataset')
        ax.set_xticks(x)
        ax.set_xticklabels(datasets, rotation=45, ha='right')
        ax.legend()
        ax.grid(axis='y', alpha=0.3)

        plt.tight_layout()
        plt.savefig(output_path / 'accuracy_by_dataset.png', dpi=150)
        plt.close()

    # 2. Field-level performance heatmap
    all_fields = set()
    for result in results.values():
        field_metrics = result.get('metrics', {}).get('field_metrics', {})
        all_fields.update(field_metrics.keys())

    all_fields = sorted(all_fields)

    if all_fields and datasets:
        # Create matrix of F1 scores
        matrix = []
        for dataset_name in datasets:
            row = []
            field_metrics = results[dataset_name].get('metrics', {}).get('field_metrics', {})
            for field in all_fields:
                if field in field_metrics:
                    row.append(field_metrics[field].get('avg_f1_score', 0))
                else:
                    row.append(0)
            matrix.append(row)

        fig, ax = plt.subplots(figsize=(14, 8))
        im = ax.imshow(matrix, cmap='RdYlGn', aspect='auto', vmin=0, vmax=1)

        ax.set_xticks(np.arange(len(all_fields)))
        ax.set_yticks(np.arange(len(datasets)))
        ax.set_xticklabels(all_fields, rotation=90, ha='right')
        ax.set_yticklabels(datasets)

        # Add colorbar
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label('F1 Score', rotation=270, labelpad=15)

        ax.set_title('Field-Level F1 Scores Heatmap')
        plt.tight_layout()
        plt.savefig(output_path / 'field_performance_heatmap.png', dpi=150)
        plt.close()

    print(f"\nVisualizations saved to: {output_path}")


def export_results(
    evaluation_results: Dict,
    output_dir: str,
    formats: List[str] = ['json', 'csv', 'markdown']
):
    """
    Export evaluation results in multiple formats

    Args:
        evaluation_results: Results from batch_evaluate()
        output_dir: Directory to save exports
        formats: List of formats to export ('json', 'csv', 'markdown', 'visualizations')
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    exported_files = []

    if 'json' in formats:
        json_file = output_path / 'evaluation_results.json'
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(evaluation_results, f, indent=2, ensure_ascii=False)
        exported_files.append(str(json_file))

    if 'csv' in formats:
        csv_file = output_path / 'evaluation_summary.csv'
        generate_csv_summary(evaluation_results, str(csv_file))
        exported_files.append(str(csv_file))

        field_csv = output_path / 'field_metrics.csv'
        generate_field_metrics_csv(evaluation_results, str(field_csv))
        exported_files.append(str(field_csv))

    if 'markdown' in formats:
        md_file = output_path / 'evaluation_report.md'
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(generate_markdown_report(evaluation_results))
        exported_files.append(str(md_file))

    if 'visualizations' in formats:
        visualize_results(evaluation_results, str(output_path))
        exported_files.extend([
            str(output_path / 'accuracy_by_dataset.png'),
            str(output_path / 'field_performance_heatmap.png')
        ])

    print(f"\nExported {len(exported_files)} files to: {output_path}")
    for file in exported_files:
        print(f"  - {Path(file).name}")

    return exported_files


if __name__ == "__main__":
    print("Reporter module loaded successfully!")
    print("\nAvailable functions:")
    print("  - generate_report(): Create comprehensive reports")
    print("  - visualize_results(): Generate charts and graphs")
    print("  - export_results(): Export in multiple formats")
