"""
Shared extraction validation utility.

Import and call validate_extraction(data, ds_id) after saving any extraction output.
Returns (is_valid, errors). If is_valid is False, log errors and skip that extraction.
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# Canonical 30 field names — single source of truth
CANONICAL_FIELDS = frozenset({
    "name", "description", "url", "license", "creator", "publisher",
    "datePublished", "inLanguage", "citeAs", "isLiveDataset",
    "rai:dataCollection", "rai:dataCollectionType", "rai:dataCollectionMissingData",
    "rai:dataCollectionRawData", "rai:dataCollectionTimeframe",
    "rai:dataImputationProtocol", "rai:dataManipulationProtocol",
    "rai:dataPreprocessingProtocol", "rai:dataAnnotationProtocol",
    "rai:dataAnnotationPlatform", "rai:dataAnnotationAnalysis",
    "rai:annotationsPerItem", "rai:annotatorDemographics",
    "rai:machineAnnotationTools", "rai:dataReleaseMaintenancePlan",
    "rai:personalSensitiveInformation", "rai:dataSocialImpact",
    "rai:dataBiases", "rai:dataLimitations", "rai:dataUseCases",
})

VALID_VALUE_TYPES = (str, type(None), dict, list, bool, int, float)


def validate_extraction(data: Dict, ds_id: str = "unknown") -> Tuple[bool, List[str]]:
    """Validate a single extraction dict against the canonical schema.

    Args:
        data: The extraction dict (30 fields).
        ds_id: Dataset identifier for error messages.

    Returns:
        (is_valid, errors): True if valid, list of error strings if not.
    """
    errors = []

    if not isinstance(data, dict):
        return False, [f"{ds_id}: extraction is not a dict (got {type(data).__name__})"]

    fields = set(data.keys())

    # Check for missing fields
    missing = CANONICAL_FIELDS - fields
    if missing:
        errors.append(f"{ds_id}: missing fields: {sorted(missing)}")

    # Check for extra fields
    extra = fields - CANONICAL_FIELDS
    if extra:
        errors.append(f"{ds_id}: extra fields: {sorted(extra)}")

    # Check for whitespace in field names
    for field in fields:
        if field != field.strip():
            errors.append(f"{ds_id}: field '{field}' has leading/trailing whitespace")

    # Check value types
    for field, val in data.items():
        if not isinstance(val, VALID_VALUE_TYPES):
            errors.append(f"{ds_id}/{field}: unexpected type {type(val).__name__}")

    return len(errors) == 0, errors


def validate_extraction_file(path: Path) -> Tuple[bool, List[str]]:
    """Validate an extraction JSON file on disk.

    Args:
        path: Path to the JSON file.

    Returns:
        (is_valid, errors): True if valid.
    """
    ds_id = path.parent.name if path.parent.name != "." else path.stem

    if not path.exists():
        return False, [f"{ds_id}: file not found: {path}"]

    try:
        with open(path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return False, [f"{ds_id}: invalid JSON: {e}"]

    return validate_extraction(data, ds_id)
