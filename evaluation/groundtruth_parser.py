"""
Groundtruth parser for CroissantMiner evaluation

Extracts human-annotated Croissant metadata from the groundtruth PDF
and structures it for evaluation purposes.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional
import pdfplumber
from json_repair import repair_json


# CORRECTED MAPPING based on actual PDF content
# Groundtruth has annotations for: LibriSpeech, MLS, MMLU, FLORES, CIFAR, DOLLY, MSCOCO, MMMU, MathVista, Visual Genome
# PDFs available: 1405 (MSCOCO), 1602 (Visual Genome), 2009 (MMLU), 2012 (MLS), 2106 (FLORES), 2310 (MathVista), 2311 (MMMU), 2404 (CIFAR)
DATASET_PDF_MAPPING = {
    'MLS': '2012.03411v2.pdf',           # ✅ MLS paper
    'MMLU': '2009.03300v3.pdf',          # ✅ MMLU paper
    'FLORES': '2106.03193v1.pdf',        # ✅ FLORES paper
    'MSCOCO': '1405.0312v3.pdf',         # ✅ MS COCO paper
    'MMMU': '2311.16502v4.pdf',          # ✅ MMMU paper
    'CIFAR': '2404.00498v2.pdf',         # ✅ CIFAR-10 paper
    'Visual Genome': '1602.07332v1.pdf', # ✅ Visual Genome paper
    'MathVista': '2310.02255v3.pdf',     # ✅ MathVista paper
    # Note: The following datasets have groundtruth annotations but no matching PDFs:
    # - LibriSpeech (groundtruth exists, but no extraction available)
    # - DOLLY (groundtruth exists, but no extraction available)
}


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract text from PDF file using pdfplumber for better text extraction

    Args:
        pdf_path: Path to PDF file

    Returns:
        Extracted text
    """
    try:
        text = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text
    except Exception as e:
        print(f"Error extracting text from {pdf_path}: {e}")
        return ""


def clean_json_string(json_str: str) -> str:
    """
    Clean JSON string for parsing - handles PDF extraction issues

    Args:
        json_str: Raw JSON string extracted from PDF

    Returns:
        Cleaned JSON string
    """
    # Fix smart quotes first
    json_str = json_str.replace('"', '"').replace('"', '"')
    json_str = json_str.replace("'", "'").replace("'", "'")

    # Remove // comments ONLY when they're not inside strings
    # AND handle newlines at the same time
    # Strategy: Use a single-pass state machine for everything

    result = []
    i = 0
    in_string = False
    after_quote = False  # Track if we just saw a closing quote

    while i < len(json_str):
        char = json_str[i]

        # Handle escape sequences
        if char == '\\' and i + 1 < len(json_str):
            result.append(char)
            result.append(json_str[i + 1])
            i += 2
            continue

        # Track string state
        if char == '"':
            in_string = not in_string
            result.append(char)
            after_quote = not in_string  # Just closed a string
            i += 1
            continue

        # Handle // comments ONLY outside strings
        if not in_string and char == '/' and i + 1 < len(json_str) and json_str[i + 1] == '/':
            # Skip until end of line
            while i < len(json_str) and json_str[i] != '\n':
                i += 1
            # Don't skip the newline itself - let it be handled below
            continue

        # Handle newlines
        if char == '\n':
            if in_string:
                # Inside a string value - replace newline with space
                result.append(' ')
            else:
                # Outside strings - replace with space
                result.append(' ')

            after_quote = False
            i += 1
            continue

        # Regular character
        if char not in ' \t\r':
            after_quote = False
        result.append(char)
        i += 1

    json_str = ''.join(result)

    # Clean up excessive whitespace (but preserve single spaces)
    json_str = re.sub(r'[ \t]+', ' ', json_str)

    # Remove trailing commas before closing braces/brackets
    json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)

    return json_str


def fix_json_repair_artifacts(data: Dict) -> Dict:
    """
    Fix artifacts created by json-repair when handling PDF typos

    Common issues:
    - "field": "value"\n", becomes "field": "value", "value_fragment": "..."
    - Fields with invalid names that should be merged back

    Args:
        data: Parsed JSON dictionary

    Returns:
        Fixed dictionary
    """
    # Define valid Croissant field prefixes
    valid_prefixes = ('sc:', 'cr:', 'rai:', 'dct:')

    # Find invalid fields (those not starting with valid prefixes or metadata fields)
    invalid_fields = []
    for key in data.keys():
        if not key.startswith(valid_prefixes) and key not in ['dataset_name', 'annotator_id', 'pdf_file']:
            invalid_fields.append(key)

    # Try to merge invalid fields back into valid ones
    # Strategy: Look for the previous valid field and append the invalid field's value
    if invalid_fields:
        keys = list(data.keys())
        for invalid_key in invalid_fields:
            invalid_idx = keys.index(invalid_key)

            # Find the previous valid Croissant field
            prev_key = None
            for i in range(invalid_idx - 1, -1, -1):
                if keys[i].startswith(valid_prefixes):
                    prev_key = keys[i]
                    break

            if prev_key:
                # Merge: append invalid field value to previous field
                prev_value = str(data[prev_key])
                invalid_value = str(data[invalid_key])

                # Check if invalid_value looks like it should be appended
                # Pattern: previous field ends abruptly, invalid field continues
                if not prev_value.endswith('.') and not prev_value.endswith('"'):
                    # Append with space
                    data[prev_key] = prev_value + ', ' + invalid_value
                else:
                    # Invalid field might be a continuation of the sentence
                    data[prev_key] = prev_value + ' ' + invalid_value

                # Remove the invalid field
                del data[invalid_key]

    # Fix case sensitivity issues (e.g., "Sc:license" -> "sc:license")
    case_fixes = {}
    for key in list(data.keys()):
        if key.startswith(valid_prefixes):
            # Normalize prefix to lowercase
            prefix = key.split(':')[0].lower() + ':'
            field = ':'.join(key.split(':')[1:])
            normalized_key = prefix + field
            if normalized_key != key:
                case_fixes[key] = normalized_key

    for old_key, new_key in case_fixes.items():
        data[new_key] = data.pop(old_key)

    return data


def extract_json_from_marker_position(text: str) -> Optional[Dict]:
    """
    Extract JSON object from text that starts right after a marker

    Args:
        text: Text starting right after the marker (e.g., after "Annotator 1:")

    Returns:
        Parsed JSON dictionary or None
    """
    try:
        # Find the opening brace within a reasonable distance
        search_window = text[:500]
        brace_idx = search_window.find('{')

        if brace_idx == -1:
            print(f"Could not find opening brace")
            print(f"Text (first 100 chars): {text[:100]}")
            return None

        # Start from the opening brace
        text_from_brace = text[brace_idx:]

        # Find matching closing brace using depth tracking
        # IMPORTANT: Must handle LaTeX sequences like \'{a} which have quotes and braces
        depth = 0
        end_idx = -1
        in_string = False
        i = 0

        while i < len(text_from_brace):
            char = text_from_brace[i]

            # Handle escape sequences: \", \\, \', \{, \}
            # These should not affect string or brace tracking
            if char == '\\' and i + 1 < len(text_from_brace):
                # Skip both the backslash and the next character
                i += 2
                continue

            # Track string state (quotes toggle in/out of strings)
            if char == '"':
                in_string = not in_string
                i += 1
                continue

            # Only count braces outside of strings
            if not in_string:
                if char == '{':
                    depth += 1
                elif char == '}':
                    depth -= 1
                    if depth == 0:
                        end_idx = i
                        break

            i += 1

        if end_idx == -1:
            # Brace matching failed - this might be due to typos in the PDF
            # Try to find the next "Annotator" or "Dataset" marker and extract up to there
            next_marker = re.search(r'(Annotator\s*\d+|Dataset\s*\d+)', text_from_brace[100:])
            if next_marker:
                end_idx = 100 + next_marker.start() - 5  # Stop just before the marker
                print(f"Could not find matching closing brace (depth={depth}), using next marker at position {end_idx}")
            else:
                print(f"Could not find matching closing brace (max depth: {depth})")
                return None

        # Extract and clean JSON
        json_str = text_from_brace[:end_idx + 1]
        json_str = clean_json_string(json_str)

        # Try to parse
        try:
            result = json.loads(json_str)
        except json.JSONDecodeError:
            # Try to repair the JSON
            try:
                repaired = repair_json(json_str)
                result = json.loads(repaired)
                # Ensure we return a dict, not a list
                if isinstance(result, list) and len(result) > 0:
                    result = result[0]
                if not isinstance(result, dict):
                    return None
            except Exception:
                # If repair fails, raise the original error
                raise

        # Post-process to fix common PDF typos that json-repair handles incorrectly
        # Issue: PDF has typos like "field": "value"\n", which creates invalid fields
        result = fix_json_repair_artifacts(result)
        return result

    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        if 'json_str' in locals():
            print(f"Problematic JSON string (first 300 chars): {json_str[:300]}...")
            # Debug: Show full JSON for first error only
            import os
            if not os.path.exists('/tmp/debug_json.txt'):
                with open('/tmp/debug_json.txt', 'w') as f:
                    f.write(json_str)
                print("Saved full JSON to /tmp/debug_json.txt for debugging")
        return None
    except Exception as e:
        print(f"Error extracting JSON: {e}")
        return None


def extract_json_from_text(text: str, start_marker: str) -> Optional[Dict]:
    """
    Extract JSON object from text starting after a marker

    Args:
        text: Text containing JSON
        start_marker: Marker string before JSON starts

    Returns:
        Parsed JSON dictionary or None
    """
    try:
        # Find the start marker (e.g., "Annotator 1")
        start_idx = text.find(start_marker)
        if start_idx == -1:
            print(f"Could not find marker '{start_marker}' in text")
            return None

        # Get text after the marker
        text_after_marker = text[start_idx + len(start_marker):]

        # Try to find the opening brace within a reasonable distance (e.g., next 500 chars)
        # This handles cases where there might be extra text between marker and JSON
        search_window = text_after_marker[:500]
        brace_idx = search_window.find('{')

        if brace_idx == -1:
            print(f"Could not find opening brace after '{start_marker}'")
            print(f"Text after marker (first 200 chars): {text_after_marker[:200]}")
            return None

        # Start from the opening brace in the original text
        text_from_brace = text_after_marker[brace_idx:]

        # Find matching closing brace using depth tracking
        depth = 0
        end_idx = -1
        in_string = False
        escape_next = False

        for i, char in enumerate(text_from_brace):
            # Handle string literals to avoid counting braces inside strings
            if escape_next:
                escape_next = False
                continue

            if char == '\\':
                escape_next = True
                continue

            if char == '"' and not in_string:
                in_string = True
                continue
            elif char == '"' and in_string:
                in_string = False
                continue

            # Only count braces outside of strings
            if not in_string:
                if char == '{':
                    depth += 1
                elif char == '}':
                    depth -= 1
                    if depth == 0:
                        end_idx = i
                        break

        if end_idx == -1:
            print(f"Could not find matching closing brace for {start_marker}")
            return None

        # Extract and clean JSON
        json_str = text_from_brace[:end_idx + 1]
        json_str = clean_json_string(json_str)

        # Try to parse
        return json.loads(json_str)

    except json.JSONDecodeError as e:
        print(f"JSON decode error for {start_marker}: {e}")
        if 'json_str' in locals():
            print(f"Problematic JSON string (first 300 chars): {json_str[:300]}...")
        return None
    except Exception as e:
        print(f"Error extracting JSON for {start_marker}: {e}")
        return None


def parse_dataset_annotations(text: str, dataset_name: str) -> List[Dict]:
    """
    Parse all three annotator responses for a dataset

    Args:
        text: Full groundtruth PDF text
        dataset_name: Name of the dataset

    Returns:
        List of 3 annotation dictionaries
    """
    annotations = []

    # Strategy: Find all "Annotator X:" markers in the text, then match them to datasets
    # by looking at which dataset heading comes before each annotator section

    # Get dataset number from the mapping
    dataset_numbers = {
        'LibriSpeech': 1,
        'MLS': 2,
        'MMLU': 3,
        'FLORES': 4,
        'CIFAR': 5,
        'DOLLY': 6,
        'MSCOCO': 7,
        'MMMU': 8
    }

    dataset_num = dataset_numbers.get(dataset_name)
    if not dataset_num:
        print(f"Warning: Unknown dataset {dataset_name}")
        return []

    # Find all "Annotator X:" positions for this dataset
    # We'll look for the pattern that matches the dataset number indirectly
    # by finding groups of 3 annotators

    # Since there are 8 datasets with 3 annotators each = 24 annotators total
    # Dataset 1 annotators are at positions 0, 1, 2
    # Dataset 2 annotators are at positions 3, 4, 5
    # etc.
    first_annotator_idx = (dataset_num - 1) * 3

    # Find all annotator markers
    all_annotator_matches = list(re.finditer(r'Annotator\s*(\d+)\s*:', text, re.IGNORECASE))

    # Group by annotator number (1, 2, or 3)
    annotator_groups = {1: [], 2: [], 3: []}
    for match in all_annotator_matches:
        annotator_num = int(match.group(1))
        if annotator_num in [1, 2, 3]:
            annotator_groups[annotator_num].append(match)

    # Get the annotator matches for this dataset
    for annotator_num in range(1, 4):
        # Each annotator (1, 2, 3) appears 8 times (once per dataset)
        # For dataset N, we want the Nth occurrence of each annotator
        matches = annotator_groups[annotator_num]

        if dataset_num - 1 >= len(matches):
            print(f"Warning: Could not find Annotator {annotator_num} occurrence {dataset_num} for {dataset_name}")
            continue

        # Get the specific match for this dataset
        match = matches[dataset_num - 1]

        # Extract text from this point
        text_from_marker = text[match.end():]

        # Try to extract JSON
        annotation = extract_json_from_marker_position(text_from_marker)

        if annotation:
            annotation['dataset_name'] = dataset_name
            annotation['annotator_id'] = annotator_num
            annotation['pdf_file'] = DATASET_PDF_MAPPING.get(dataset_name, 'unknown.pdf')
            annotations.append(annotation)
        else:
            print(f"Warning: Could not extract annotation for {dataset_name}, Annotator {annotator_num}")

    return annotations


def parse_groundtruth(groundtruth_pdf_path: str, output_dir: Optional[str] = None) -> Dict[str, List[Dict]]:
    """
    Parse the groundtruth PDF and extract all annotations

    Args:
        groundtruth_pdf_path: Path to the groundtruth PDF
        output_dir: Optional directory to save parsed JSON files

    Returns:
        Dictionary mapping dataset names to lists of annotations
    """
    print(f"Parsing groundtruth from: {groundtruth_pdf_path}")

    # Extract text from PDF
    text = extract_text_from_pdf(groundtruth_pdf_path)
    if not text:
        print("Error: Could not extract text from groundtruth PDF")
        return {}

    # Parse annotations for each dataset (first 8)
    datasets = ['LibriSpeech', 'MLS', 'MMLU', 'FLORES', 'CIFAR', 'DOLLY', 'MSCOCO', 'MMMU']
    all_annotations = {}

    for dataset_name in datasets:
        print(f"\nParsing {dataset_name}...")
        annotations = parse_dataset_annotations(text, dataset_name)

        if annotations:
            all_annotations[dataset_name] = annotations
            print(f"  Found {len(annotations)} annotations")

            # Save to individual JSON files if output_dir specified
            if output_dir:
                output_path = Path(output_dir)
                output_path.mkdir(parents=True, exist_ok=True)

                dataset_file = output_path / f"{dataset_name.lower()}_annotations.json"
                with open(dataset_file, 'w', encoding='utf-8') as f:
                    json.dump(annotations, f, indent=2, ensure_ascii=False)
                print(f"  Saved to {dataset_file}")
        else:
            print(f"  Warning: No annotations found for {dataset_name}")

    # Save combined file
    if output_dir:
        combined_file = Path(output_dir) / "all_annotations.json"
        with open(combined_file, 'w', encoding='utf-8') as f:
            json.dump(all_annotations, f, indent=2, ensure_ascii=False)
        print(f"\nSaved combined annotations to {combined_file}")

    return all_annotations


def load_groundtruth(groundtruth_dir: str, dataset_name: Optional[str] = None) -> Dict:
    """
    Load parsed groundtruth annotations from JSON files

    Args:
        groundtruth_dir: Directory containing parsed JSON files
        dataset_name: Optional specific dataset to load

    Returns:
        Dictionary of annotations
    """
    groundtruth_path = Path(groundtruth_dir)

    if dataset_name:
        # Load specific dataset
        dataset_file = groundtruth_path / f"{dataset_name.lower()}_annotations.json"
        if not dataset_file.exists():
            print(f"Error: Groundtruth file not found: {dataset_file}")
            return {}

        with open(dataset_file, 'r', encoding='utf-8') as f:
            return {dataset_name: json.load(f)}
    else:
        # Load all datasets
        combined_file = groundtruth_path / "all_annotations.json"
        if combined_file.exists():
            with open(combined_file, 'r', encoding='utf-8') as f:
                return json.load(f)

        # Fallback: load individual files
        all_annotations = {}
        for dataset_file in groundtruth_path.glob("*_annotations.json"):
            if dataset_file.name != "all_annotations.json":
                dataset_name = dataset_file.stem.replace('_annotations', '').upper()
                with open(dataset_file, 'r', encoding='utf-8') as f:
                    all_annotations[dataset_name] = json.load(f)

        return all_annotations


def get_pdf_for_dataset(dataset_name: str) -> str:
    """
    Get the PDF filename for a given dataset

    Args:
        dataset_name: Name of the dataset

    Returns:
        PDF filename
    """
    return DATASET_PDF_MAPPING.get(dataset_name, 'unknown.pdf')


def list_available_datasets() -> List[str]:
    """
    Get list of available datasets in groundtruth

    Returns:
        List of dataset names
    """
    return list(DATASET_PDF_MAPPING.keys())


def validate_annotations(annotations: Dict[str, List[Dict]]) -> Dict:
    """
    Validate extracted annotations for quality issues

    Args:
        annotations: Dictionary mapping dataset names to lists of annotations

    Returns:
        Dictionary with validation results
    """
    results = {
        'total_annotations': 0,
        'valid_annotations': 0,
        'issues': []
    }

    valid_prefixes = ('sc:', 'cr:', 'rai:', 'dct:')
    expected_fields = 16  # 10 core + 2 cr + 4-6 RAI

    for dataset_name, dataset_annotations in annotations.items():
        for ann in dataset_annotations:
            results['total_annotations'] += 1
            annotator_id = ann.get('annotator_id', '?')
            is_valid = True

            # Check for invalid field names
            invalid_fields = []
            for key in ann.keys():
                if key not in ['dataset_name', 'annotator_id', 'pdf_file']:
                    if not key.startswith(valid_prefixes):
                        invalid_fields.append(key)
                        is_valid = False

            if invalid_fields:
                results['issues'].append({
                    'dataset': dataset_name,
                    'annotator': annotator_id,
                    'type': 'invalid_fields',
                    'details': f"Invalid field names: {', '.join(invalid_fields)}"
                })

            # Check for embedded field names in values
            for key, value in ann.items():
                if key.startswith(valid_prefixes) and isinstance(value, str):
                    # Check if value contains what looks like a field name
                    if any(f'"{prefix}' in value for prefix in valid_prefixes):
                        results['issues'].append({
                            'dataset': dataset_name,
                            'annotator': annotator_id,
                            'type': 'embedded_field',
                            'details': f"Field '{key}' contains embedded field name"
                        })
                        is_valid = False

            # Count Croissant fields
            croissant_fields = [k for k in ann.keys() if k.startswith(valid_prefixes)]
            if len(croissant_fields) < 10:
                results['issues'].append({
                    'dataset': dataset_name,
                    'annotator': annotator_id,
                    'type': 'missing_fields',
                    'details': f"Only {len(croissant_fields)} Croissant fields (expected at least 10)"
                })
                is_valid = False

            if is_valid:
                results['valid_annotations'] += 1

    return results


if __name__ == "__main__":
    # Test the parser
    import sys
    from pathlib import Path

    # Find groundtruth PDF
    base_dir = Path(__file__).parent.parent
    groundtruth_pdf = base_dir / "groundtruth" / "Croissant User Research Report.pdf"
    output_dir = base_dir / "groundtruth" / "parsed"

    if not groundtruth_pdf.exists():
        print(f"Error: Groundtruth PDF not found: {groundtruth_pdf}")
        sys.exit(1)

    # Parse and save
    annotations = parse_groundtruth(str(groundtruth_pdf), str(output_dir))

    # Validate annotations
    print("\n" + "=" * 80)
    print("VALIDATING ANNOTATIONS")
    print("=" * 80)
    validation = validate_annotations(annotations)
    print(f"Total annotations: {validation['total_annotations']}")
    print(f"Valid annotations: {validation['valid_annotations']}")
    print(f"Annotations with issues: {len(validation['issues'])}")

    if validation['issues']:
        print("\nIssues found:")
        for issue in validation['issues']:
            print(f"  • {issue['dataset']} Annotator {issue['annotator']}: {issue['details']}")

    # Print summary
    print("\n" + "=" * 80)
    print("GROUNDTRUTH PARSING SUMMARY")
    print("=" * 80)
    print(f"Total datasets parsed: {len(annotations)}")
    for dataset_name, dataset_annotations in annotations.items():
        print(f"\n{dataset_name}:")
        print(f"  Annotations: {len(dataset_annotations)}")
        print(f"  PDF file: {get_pdf_for_dataset(dataset_name)}")
        if dataset_annotations:
            first_annotation = dataset_annotations[0]
            fields = [k for k in first_annotation.keys() if k not in ['dataset_name', 'annotator_id', 'pdf_file']]
            print(f"  Fields: {', '.join(fields[:5])}...")
