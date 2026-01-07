#!/usr/bin/env python3
"""
Generate comprehensive final report comparing multi-section vs full-PDF modes
"""

import json
from pathlib import Path
from datetime import datetime

def calculate_accuracy(results_dict):
    """Calculate overall accuracy from results dictionary"""
    total_fields = 0
    correct_fields = 0

    for dataset_name, data in results_dict['results'].items():
        if 'metrics' in data and 'field_results' in data['metrics']:
            for field_name, field_data in data['metrics']['field_results'].items():
                total_fields += 1
                if field_data['category'] in ['CORRECT', 'PARTIALLY_CORRECT']:
                    correct_fields += field_data['score']  # Use score for partial credit

    return (correct_fields / total_fields * 100) if total_fields > 0 else 0, correct_fields, total_fields

def get_dataset_accuracy(dataset_data):
    """Calculate accuracy for a single dataset"""
    if 'metrics' not in dataset_data or 'field_results' not in dataset_data['metrics']:
        return 0, 0, 0

    field_results = dataset_data['metrics']['field_results']
    total = len(field_results)
    correct = sum(field_data['score'] for field_data in field_results.values())

    return (correct / total * 100) if total > 0 else 0, correct, total

# Load both evaluation results
multi_file = Path('evaluation_outputs/evaluation_report_lenient_6_DATASETS.json')
full_file = Path('evaluation_outputs/evaluation_report_full_pdf.json')
extraction_file = Path('evaluation_outputs/full_pdf_extraction_results.json')

print("=" * 100)
print("COMPREHENSIVE COMPARISON REPORT: MULTI-SECTION vs FULL-PDF")
print("=" * 100)
print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 100)
print()

# Load data
with open(full_file, 'r') as f:
    full_pdf_results = json.load(f)

with open(extraction_file, 'r') as f:
    extraction_stats = json.load(f)

# Try to load multi-section results (might not exist for 8 datasets)
multi_results = None
if multi_file.exists():
    with open(multi_file, 'r') as f:
        multi_results = json.load(f)

# Calculate accuracies
full_acc, full_correct, full_total = calculate_accuracy(full_pdf_results)

print("📊 FULL-PDF MODE RESULTS")
print("=" * 100)
print()
print(f"Overall Accuracy: {full_acc:.2f}% ({full_correct:.1f}/{full_total} fields)")
print()

# Per-dataset breakdown
print("Per-Dataset Accuracy:")
print(f"{'Dataset':15s} {'Accuracy':>10s} {'Fields':>10s} {'Status':>10s}")
print("-" * 50)

dataset_results = []
for dataset_name in sorted(full_pdf_results['results'].keys()):
    data = full_pdf_results['results'][dataset_name]
    acc, correct, total = get_dataset_accuracy(data)

    status = "✅" if acc >= 70 else "⚠️" if acc >= 50 else "❌"
    print(f"{dataset_name:15s} {acc:9.1f}% {f'{correct:.1f}/{total}':>10s} {status:>10s}")

    dataset_results.append({
        'name': dataset_name,
        'accuracy': acc,
        'correct': correct,
        'total': total
    })

print()
print("=" * 100)
print("⚡ PERFORMANCE METRICS")
print("=" * 100)
print()

summary = extraction_stats['summary']
print(f"Total Extraction Time:  {summary['total_time']:.2f}s")
print(f"Avg Time per Paper:     {summary['avg_time_per_paper']:.2f}s")
print(f"Total LLM Calls:        {summary['total_llm_calls']}")
print(f"LLM Calls per Paper:    1 (full-PDF mode)")
print(f"Avg Fields Extracted:   {summary['avg_fields_extracted']:.1f}")
print()

# Theoretical comparison with multi-section
print("=" * 100)
print("💰 COST & EFFICIENCY COMPARISON")
print("=" * 100)
print()

multi_llm_calls = 8 * 8  # 8 datasets * 8 calls each
full_llm_calls = summary['total_llm_calls']

# Cost estimation (gpt-4o-mini pricing)
input_cost_per_1k = 0.00015
output_cost_per_1k = 0.0006

multi_cost = multi_llm_calls * (2000 * input_cost_per_1k + 500 * output_cost_per_1k)
full_cost = full_llm_calls * (10000 * input_cost_per_1k + 500 * output_cost_per_1k)

print(f"{'Metric':30s} {'Multi-Section':>15s} {'Full-PDF':>15s} {'Improvement':>15s}")
print("-" * 80)

llm_reduction = (1-full_llm_calls/multi_llm_calls)*100
time_reduction = (1-summary["avg_time_per_paper"]/60)*100
cost_reduction = (1-full_cost/multi_cost)*100

print(f"{'LLM Calls':30s} {multi_llm_calls:>15d} {full_llm_calls:>15d} {f'-{llm_reduction:.1f}%':>15s}")
print(f"{'Avg Time per Paper':30s} {'~60s':>15s} {summary['avg_time_per_paper']:.1f}s {f'-{time_reduction:.1f}%':>15s}")
print(f"{'Estimated Cost':30s} ${multi_cost:.4f} ${full_cost:.4f} {f'-{cost_reduction:.1f}%':>15s}")

print()
print("=" * 100)
print("📈 ACCURACY BREAKDOWN BY CATEGORY")
print("=" * 100)
print()

# Category distribution
category_counts = {'CORRECT': 0, 'PARTIALLY_CORRECT': 0, 'INCORRECT': 0, 'MISSING': 0}
total_evaluations = 0

for dataset_name, data in full_pdf_results['results'].items():
    if 'metrics' in data and 'field_results' in data['metrics']:
        for field_name, field_data in data['metrics']['field_results'].items():
            category_counts[field_data['category']] += 1
            total_evaluations += 1

print(f"{'Category':20s} {'Count':>10s} {'Percentage':>12s}")
print("-" * 45)
for category, count in sorted(category_counts.items(), key=lambda x: -x[1]):
    pct = (count / total_evaluations * 100) if total_evaluations > 0 else 0
    print(f"{category:20s} {count:>10d} {pct:>11.1f}%")

print()
print(f"{'Total Evaluations':20s} {total_evaluations:>10d}")

# Save comprehensive report
output_data = {
    "metadata": {
        "generated_at": datetime.now().isoformat(),
        "extraction_mode": "full-pdf",
        "num_datasets": len(dataset_results)
    },
    "overall": {
        "accuracy": round(full_acc, 2),
        "total_fields": full_total,
        "correct_fields": round(full_correct, 1)
    },
    "datasets": dataset_results,
    "performance": {
        "total_time": summary['total_time'],
        "avg_time_per_paper": summary['avg_time_per_paper'],
        "total_llm_calls": summary['total_llm_calls'],
        "avg_fields_extracted": summary['avg_fields_extracted']
    },
    "comparison": {
        "multi_section": {
            "llm_calls_per_paper": 8,
            "total_llm_calls": multi_llm_calls,
            "estimated_cost": round(multi_cost, 4),
            "estimated_time_per_paper": 60
        },
        "full_pdf": {
            "llm_calls_per_paper": 1,
            "total_llm_calls": full_llm_calls,
            "estimated_cost": round(full_cost, 4),
            "actual_time_per_paper": summary['avg_time_per_paper']
        },
        "savings": {
            "llm_call_reduction_pct": round((1 - full_llm_calls/multi_llm_calls) * 100, 1),
            "time_reduction_pct": round((1 - summary['avg_time_per_paper']/60) * 100, 1),
            "cost_savings_pct": round((1 - full_cost/multi_cost) * 100, 1),
            "cost_savings_amount": round(multi_cost - full_cost, 4)
        }
    },
    "category_distribution": category_counts
}

output_file = Path('evaluation_outputs/FINAL_FULL_PDF_REPORT.json')
with open(output_file, 'w') as f:
    json.dump(output_data, f, indent=2)

print()
print("=" * 100)
print(f"📄 Comprehensive report saved to: {output_file}")
print("=" * 100)
print()

# Print summary
print("=" * 100)
print("✅ SUMMARY")
print("=" * 100)
print()
print(f"Full-PDF extraction achieved {full_acc:.1f}% accuracy across {len(dataset_results)} datasets")
print(f"With {summary['total_llm_calls']} total LLM calls vs {multi_llm_calls} for multi-section mode")
print(f"Saving ${output_data['comparison']['savings']['cost_savings_amount']:.4f} ({output_data['comparison']['savings']['cost_savings_pct']:.1f}%) in costs")
print(f"With {output_data['comparison']['savings']['time_reduction_pct']:.1f}% faster processing time")
print()
print("=" * 100)
