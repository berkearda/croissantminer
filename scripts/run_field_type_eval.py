#!/usr/bin/env python3
"""Run field-type-aware evaluation on all methods."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from evaluation.composite_evaluator import evaluate_method, generate_report
from evaluation.field_metrics import finalize_cache

GT_PATH = "data/groundtruth_30field/all_annotations.json"

methods = {
    "Claude Sonnet 4.5": "evaluation_outputs_v2",
    "GPT-4o-mini": "results/gpt4o_mini",
}

# HF baseline needs special handling (mapped files, not extraction files)
HF_MAPPED_DIR = "data/baselines/hf_croissant_mapped"

results = {}

for method_name, ext_dir in methods.items():
    print(f"\nEvaluating {method_name}...")
    results[method_name] = evaluate_method(ext_dir, GT_PATH, method_name)

# HF baseline
print(f"\nEvaluating HF Auto-Croissant...")
import json
with open(GT_PATH) as f:
    gt_all = json.load(f)

hf_results = {}
for ds_name in gt_all:
    hf_file = Path(HF_MAPPED_DIR) / f"{ds_name}.json"
    if not hf_file.exists():
        continue
    with open(hf_file) as f:
        predicted = json.load(f)
    gt_ref = gt_all[ds_name][0] if isinstance(gt_all[ds_name], list) else gt_all[ds_name]

    from evaluation.composite_evaluator import evaluate_dataset
    hf_results[ds_name] = evaluate_dataset(predicted, gt_ref, ds_name)

results["HF Auto-Croissant"] = hf_results
finalize_cache()

generate_report(results, "results/field_type_eval")
