#!/usr/bin/env python3
"""
Analyze completed annotation data for inter-annotator agreement and quality metrics.

This script:
1. Loads completed annotation CSVs from data/annotations/
2. Calculates accuracy (% TRUE verdicts)
3. Analyzes confidence distributions
4. Generates correction summary
5. Exports unified results

Usage:
    python scripts/analyze_annotations.py
"""

import csv
import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime

ANNOTATIONS_DIR = Path("data/annotations")
OUTPUT_DIR = Path("data/annotations/analysis")


def load_completed_annotations():
    """Load all completed annotation CSVs."""
    all_annotations = []

    for csv_file in sorted(ANNOTATIONS_DIR.glob("Annotator_*.csv")):
        annotator = csv_file.stem

        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Skip rows without verdicts (not yet annotated)
                if not row.get('verdict'):
                    continue

                all_annotations.append({
                    'annotator': annotator,
                    'dataset_id': row['dataset_id'],
                    'field_name': row['field_name'],
                    'extracted_value': row['extracted_value'],
                    'verdict': row['verdict'].upper().strip(),
                    'corrected_value': row.get('corrected_value', ''),
                    'confidence': row.get('confidence', '').strip() if row.get('confidence') else None,
                    'notes': row.get('notes', '')
                })

    return all_annotations


def calculate_metrics(annotations):
    """Calculate accuracy and other metrics."""
    metrics = {
        'overall': {'total': 0, 'true': 0, 'false': 0},
        'by_field': defaultdict(lambda: {'total': 0, 'true': 0, 'false': 0}),
        'by_annotator': defaultdict(lambda: {'total': 0, 'true': 0, 'false': 0}),
        'by_dataset': defaultdict(lambda: {'total': 0, 'true': 0, 'false': 0}),
        'confidence_dist': defaultdict(int),
        'corrections': []
    }

    for ann in annotations:
        verdict = ann['verdict']
        field = ann['field_name']
        annotator = ann['annotator']
        dataset = ann['dataset_id']

        # Overall
        metrics['overall']['total'] += 1
        if verdict == 'TRUE':
            metrics['overall']['true'] += 1
        else:
            metrics['overall']['false'] += 1

        # By field
        metrics['by_field'][field]['total'] += 1
        if verdict == 'TRUE':
            metrics['by_field'][field]['true'] += 1
        else:
            metrics['by_field'][field]['false'] += 1

        # By annotator
        metrics['by_annotator'][annotator]['total'] += 1
        if verdict == 'TRUE':
            metrics['by_annotator'][annotator]['true'] += 1
        else:
            metrics['by_annotator'][annotator]['false'] += 1

        # By dataset
        metrics['by_dataset'][dataset]['total'] += 1
        if verdict == 'TRUE':
            metrics['by_dataset'][dataset]['true'] += 1
        else:
            metrics['by_dataset'][dataset]['false'] += 1

        # Confidence
        if ann['confidence']:
            metrics['confidence_dist'][ann['confidence']] += 1

        # Corrections
        if verdict == 'FALSE' and ann['corrected_value']:
            metrics['corrections'].append({
                'dataset_id': dataset,
                'field': field,
                'extracted': ann['extracted_value'][:200],  # Truncate for readability
                'corrected': ann['corrected_value'][:500],
                'annotator': annotator,
                'notes': ann['notes']
            })

    return metrics


def generate_report(metrics):
    """Generate a markdown report."""
    report_lines = []

    def accuracy(stats):
        if stats['total'] == 0:
            return 0
        return (stats['true'] / stats['total']) * 100

    report_lines.append("# Annotation Analysis Report")
    report_lines.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Overall
    report_lines.append("## Overall Accuracy\n")
    overall = metrics['overall']
    report_lines.append(f"- **Total Annotations**: {overall['total']:,}")
    report_lines.append(f"- **Correct (TRUE)**: {overall['true']:,} ({accuracy(overall):.1f}%)")
    report_lines.append(f"- **Incorrect (FALSE)**: {overall['false']:,} ({100-accuracy(overall):.1f}%)")
    report_lines.append("")

    # By Field
    report_lines.append("## Accuracy by Field\n")
    report_lines.append("| Field | Total | Correct | Accuracy |")
    report_lines.append("|-------|-------|---------|----------|")

    for field, stats in sorted(metrics['by_field'].items(), key=lambda x: accuracy(x[1]), reverse=True):
        acc = accuracy(stats)
        report_lines.append(f"| {field} | {stats['total']} | {stats['true']} | {acc:.1f}% |")

    report_lines.append("")

    # By Annotator
    report_lines.append("## Annotations by Annotator\n")
    report_lines.append("| Annotator | Total | TRUE | FALSE | TRUE Rate |")
    report_lines.append("|-----------|-------|------|-------|-----------|")

    for annotator, stats in sorted(metrics['by_annotator'].items()):
        acc = accuracy(stats)
        report_lines.append(f"| {annotator} | {stats['total']} | {stats['true']} | {stats['false']} | {acc:.1f}% |")

    report_lines.append("")

    # Confidence Distribution
    report_lines.append("## Confidence Distribution\n")
    report_lines.append("| Confidence | Count | Percentage |")
    report_lines.append("|------------|-------|------------|")

    total_conf = sum(metrics['confidence_dist'].values())
    # Sort by High, Medium, Low order
    conf_order = ['High', 'Medium', 'Low']
    for conf in conf_order:
        if conf in metrics['confidence_dist']:
            count = metrics['confidence_dist'][conf]
            pct = (count / total_conf * 100) if total_conf > 0 else 0
            report_lines.append(f"| {conf} | {count} | {pct:.1f}% |")
    # Add any other confidence values not in the standard order
    for conf in sorted(metrics['confidence_dist'].keys()):
        if conf not in conf_order:
            count = metrics['confidence_dist'][conf]
            pct = (count / total_conf * 100) if total_conf > 0 else 0
            report_lines.append(f"| {conf} | {count} | {pct:.1f}% |")

    report_lines.append("")

    # Sample Corrections
    report_lines.append("## Sample Corrections (First 20)\n")
    for i, corr in enumerate(metrics['corrections'][:20], 1):
        report_lines.append(f"### {i}. {corr['dataset_id']} - `{corr['field']}`")
        report_lines.append(f"- **Extracted**: {corr['extracted'][:100]}...")
        report_lines.append(f"- **Corrected**: {corr['corrected'][:200]}...")
        if corr['notes']:
            report_lines.append(f"- **Notes**: {corr['notes']}")
        report_lines.append("")

    return "\n".join(report_lines)


def export_corrections_json(metrics, output_dir):
    """Export corrections as JSON for applying to metadata."""
    corrections_file = output_dir / "corrections.json"

    corrections_by_dataset = defaultdict(dict)
    for corr in metrics['corrections']:
        corrections_by_dataset[corr['dataset_id']][corr['field']] = {
            'original': corr['extracted'],
            'corrected': corr['corrected'],
            'annotator': corr['annotator'],
            'notes': corr['notes']
        }

    with open(corrections_file, 'w', encoding='utf-8') as f:
        json.dump(dict(corrections_by_dataset), f, indent=2, ensure_ascii=False)

    return corrections_file


def main():
    """Main analysis function."""
    print("=" * 60)
    print("CroissantMiner - Annotation Analysis")
    print("=" * 60)

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load annotations
    print("\nLoading completed annotations...")
    annotations = load_completed_annotations()
    print(f"  Loaded {len(annotations)} annotations")

    if not annotations:
        print("\nNo completed annotations found.")
        print("Make sure annotators have filled in the 'verdict' column in their CSVs.")
        return

    # Calculate metrics
    print("\nCalculating metrics...")
    metrics = calculate_metrics(annotations)

    # Generate report
    print("\nGenerating report...")
    report = generate_report(metrics)

    report_file = OUTPUT_DIR / "annotation_report.md"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"  Saved report to {report_file}")

    # Export corrections
    if metrics['corrections']:
        corrections_file = export_corrections_json(metrics, OUTPUT_DIR)
        print(f"  Saved corrections to {corrections_file}")

    # Print summary
    overall = metrics['overall']
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total Annotations: {overall['total']:,}")
    print(f"Extraction Accuracy: {(overall['true']/overall['total']*100) if overall['total'] > 0 else 0:.1f}%")
    print(f"Corrections Needed: {len(metrics['corrections'])}")


if __name__ == "__main__":
    main()
