"""
Compatibility shim for groundtruth parser.

Provides load_groundtruth, get_pdf_for_dataset, and DATASET_PDF_MAPPING
by wrapping the markdown-based parser.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional

DATASET_PDF_MAPPING = {
    "MLS": "2012.03411v2.pdf",
    "MMLU": "2009.03300v3.pdf",
    "FLORES": "2106.03193v1.pdf",
    "CIFAR": "2404.00498v2.pdf",
    "MSCOCO": "1405.0312v3.pdf",
    "MMMU": "2311.16502v4.pdf",
    "Visual Genome": "1602.07332v1.pdf",
    "MathVista": "2310.02255v3.pdf",
}


def get_pdf_for_dataset(dataset_name: str) -> Optional[str]:
    return DATASET_PDF_MAPPING.get(dataset_name)


def load_groundtruth(groundtruth_dir: str, dataset_name: Optional[str] = None) -> Dict[str, List[Dict]]:
    """Load parsed groundtruth annotations from JSON files.

    Tries the combined all_annotations.json first (has proper casing),
    falls back to individual files.
    """
    gt_path = Path(groundtruth_dir)

    # Prefer combined file (preserves original dataset name casing)
    combined = gt_path / "all_annotations.json"
    if combined.exists():
        with open(combined, "r", encoding="utf-8") as f:
            raw = json.load(f)
        all_annotations = {}
        for ds_name, anns in raw.items():
            if isinstance(anns, list):
                all_annotations[ds_name] = anns
            elif isinstance(anns, dict):
                all_annotations[ds_name] = [anns]

        if dataset_name:
            return {dataset_name: all_annotations.get(dataset_name, [])}
        return all_annotations

    # Fallback: load individual files
    all_annotations = {}
    for json_file in sorted(gt_path.glob("*_annotations.json")):
        ds_name = json_file.stem.replace("_annotations", "")
        with open(json_file, "r", encoding="utf-8") as f:
            annotations = json.load(f)
        if isinstance(annotations, list):
            all_annotations[ds_name] = annotations
        elif isinstance(annotations, dict):
            all_annotations[ds_name] = [annotations]

    if dataset_name:
        return {dataset_name: all_annotations.get(dataset_name, [])}

    return all_annotations


def parse_groundtruth(groundtruth_path: str, output_dir: Optional[str] = None) -> Dict:
    """Delegate to markdown parser."""
    from .groundtruth_parser_md import parse_markdown_groundtruth
    return parse_markdown_groundtruth(groundtruth_path, output_dir=output_dir)
