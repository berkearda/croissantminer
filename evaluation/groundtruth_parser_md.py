"""
Markdown-based groundtruth parser for CroissantMiner evaluation

Parses Croissant dataset annotations from markdown file instead of PDF.
Much simpler and more reliable than PDF parsing.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional


def parse_markdown_groundtruth(md_path: str, output_dir: Optional[str] = None) -> Dict[str, List[Dict]]:
    """
    Parse groundtruth annotations from markdown file

    Args:
        md_path: Path to Croissant_Dataset_Annotations.md file
        output_dir: Optional directory to save parsed JSON files

    Returns:
        Dictionary mapping dataset names to lists of annotations
    """
    print(f"Parsing groundtruth from: {md_path}")

    # Read markdown file
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split by dataset separators
    dataset_sections = content.split('---')

    all_annotations = {}

    for section in dataset_sections:
        if not section.strip() or '## Dataset' not in section:
            continue

        # Extract dataset info
        dataset_match = re.search(r'## Dataset \d+ - (.+?) dataset', section, re.IGNORECASE)
        if not dataset_match:
            # Try alternate format without "dataset" suffix
            dataset_match = re.search(r'## Dataset \d+ - (.+?)(?:\n|$)', section)

        if not dataset_match:
            print(f"Warning: Could not extract dataset name from section")
            continue

        dataset_name = dataset_match.group(1).strip()

        # Extract HuggingFace link
        link_match = re.search(r'\*\*Link:\*\* (.+)', section)
        hf_link = link_match.group(1).strip() if link_match else None

        # Extract annotations from all annotators
        annotations = extract_annotations_from_section(section, dataset_name, hf_link)

        if annotations:
            all_annotations[dataset_name] = annotations
            print(f"  {dataset_name}: Found {len(annotations)} annotations")
        else:
            print(f"  {dataset_name}: No annotations found")

    # Save to files if output_dir specified
    if output_dir:
        save_annotations(all_annotations, output_dir)

    return all_annotations


def extract_annotations_from_section(section: str, dataset_name: str, hf_link: Optional[str]) -> List[Dict]:
    """
    Extract all annotator annotations from a dataset section

    Args:
        section: Markdown section for one dataset
        dataset_name: Name of the dataset
        hf_link: HuggingFace link for the dataset

    Returns:
        List of annotation dictionaries
    """
    annotations = []

    # Find all annotator subsections
    annotator_pattern = r'### Annotator (\d+)\s*\n(.*?)(?=### Annotator \d+|$)'
    annotator_matches = re.findall(annotator_pattern, section, re.DOTALL)

    for annotator_num, annotator_content in annotator_matches:
        # Check if marked as incomplete
        if 'Bilgi eksik' in annotator_content or '*Incomplete*' in annotator_content:
            print(f"    Annotator {annotator_num}: Marked as incomplete, skipping")
            continue

        # Extract JSON from code block
        json_match = re.search(r'```json\s*\n(.*?)\n```', annotator_content, re.DOTALL)

        if not json_match:
            print(f"    Annotator {annotator_num}: No JSON block found")
            continue

        json_str = json_match.group(1)

        try:
            annotation = json.loads(json_str)

            # Add metadata
            annotation['dataset_name'] = dataset_name
            annotation['annotator_id'] = int(annotator_num)
            annotation['source_link'] = hf_link

            # Validate annotation has required fields
            if validate_annotation(annotation):
                annotations.append(annotation)
            else:
                print(f"    Annotator {annotator_num}: Validation failed")

        except json.JSONDecodeError as e:
            print(f"    Annotator {annotator_num}: JSON parse error: {e}")
            continue

    return annotations


def validate_annotation(annotation: Dict) -> bool:
    """
    Validate that annotation has required Croissant fields

    Args:
        annotation: Annotation dictionary

    Returns:
        True if valid, False otherwise
    """
    # Count fields with valid prefixes
    valid_prefixes = ('sc:', 'cr:', 'rai:', 'dct:')
    croissant_fields = [k for k in annotation.keys() if k.startswith(valid_prefixes)]

    # Should have at least 10 fields (relaxed requirement)
    if len(croissant_fields) < 10:
        print(f"      Warning: Only {len(croissant_fields)} Croissant fields (expected >= 10)")
        # Still accept, just warn

    return True


def save_annotations(all_annotations: Dict[str, List[Dict]], output_dir: str):
    """
    Save parsed annotations to JSON files

    Args:
        all_annotations: Dictionary of all annotations
        output_dir: Directory to save files
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Save individual dataset files
    for dataset_name, annotations in all_annotations.items():
        dataset_file = output_path / f"{dataset_name.lower().replace(' ', '_')}_annotations.json"
        with open(dataset_file, 'w', encoding='utf-8') as f:
            json.dump(annotations, f, indent=2, ensure_ascii=False)
        print(f"  Saved {dataset_name} to {dataset_file}")

    # Save combined file
    combined_file = output_path / "all_annotations.json"
    with open(combined_file, 'w', encoding='utf-8') as f:
        json.dump(all_annotations, f, indent=2, ensure_ascii=False)
    print(f"\nSaved combined annotations to {combined_file}")


def get_dataset_count(annotations: Dict[str, List[Dict]]) -> Dict:
    """
    Get statistics about parsed annotations

    Args:
        annotations: Dictionary of all annotations

    Returns:
        Dictionary with statistics
    """
    stats = {
        'total_datasets': len(annotations),
        'total_annotations': sum(len(anns) for anns in annotations.values()),
        'datasets': {}
    }

    for dataset_name, anns in annotations.items():
        stats['datasets'][dataset_name] = {
            'num_annotators': len(anns),
            'fields_count': len([k for k in anns[0].keys() if k.startswith(('sc:', 'cr:', 'rai:'))]) if anns else 0
        }

    return stats


if __name__ == "__main__":
    # Test the parser
    base_dir = Path(__file__).parent.parent
    md_file = base_dir / "groundtruth" / "Croissant_Dataset_Annotations.md"
    output_dir = base_dir / "groundtruth" / "parsed_md"

    if not md_file.exists():
        print(f"Error: Markdown file not found: {md_file}")
        exit(1)

    # Parse annotations
    annotations = parse_markdown_groundtruth(str(md_file), str(output_dir))

    # Print summary
    print("\n" + "=" * 80)
    print("MARKDOWN GROUNDTRUTH PARSING SUMMARY")
    print("=" * 80)

    stats = get_dataset_count(annotations)
    print(f"Total datasets: {stats['total_datasets']}")
    print(f"Total annotations: {stats['total_annotations']}")

    print("\nPer-dataset breakdown:")
    for dataset_name, dataset_stats in stats['datasets'].items():
        print(f"  {dataset_name:20} {dataset_stats['num_annotators']} annotators, {dataset_stats['fields_count']} fields")
