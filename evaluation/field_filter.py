"""
Field filtering for CroissantMiner evaluation

Defines the official 16 Croissant metadata fields that should be evaluated.
Filters out parsing artifacts and non-standard fields.
"""

# Official 16 Croissant metadata fields from the annotation guidelines
OFFICIAL_CROISSANT_FIELDS = {
    # Croissant core attributes (10 fields)
    'sc:description',
    'sc:license',
    'sc:name',
    'sc:url',
    'sc:creator',
    'sc:publisher',
    'sc:datePublished',
    'sc:inLanguage',
    'cr:citeAs',
    'cr:isLiveDataset',

    # RAI attributes (6 fields)
    'rai:dataCollection',
    'rai:dataCollectionTimeframe',
    'rai:dataAnnotationPlatform',
    'rai:annotatorDemographics',
    'rai:dataUseCases',
    'rai:personalSensitiveInformation',
}


def filter_fields(field_dict: dict) -> dict:
    """
    Filter a field dictionary to only include official Croissant fields

    Args:
        field_dict: Dictionary of field name -> value

    Returns:
        Filtered dictionary with only official fields
    """
    filtered = {}

    for field_name, value in field_dict.items():
        # Skip metadata fields
        if field_name in ['dataset_name', 'annotator_id', 'pdf_file', '@context', '@type', '@id']:
            continue

        # Only include official Croissant fields
        if field_name in OFFICIAL_CROISSANT_FIELDS:
            filtered[field_name] = value

    return filtered


def is_valid_field(field_name: str) -> bool:
    """
    Check if a field name is a valid Croissant metadata field

    Args:
        field_name: Name of the field

    Returns:
        True if field is valid, False otherwise
    """
    # Skip metadata fields
    if field_name in ['dataset_name', 'annotator_id', 'pdf_file', '@context', '@type', '@id']:
        return False

    # Check if it's an official field
    return field_name in OFFICIAL_CROISSANT_FIELDS


def get_missing_fields(field_dict: dict) -> list:
    """
    Get list of official fields that are missing from the field dictionary

    Args:
        field_dict: Dictionary of field name -> value

    Returns:
        List of missing field names
    """
    present_fields = set(field_dict.keys())
    missing = OFFICIAL_CROISSANT_FIELDS - present_fields
    return sorted(missing)


def get_extra_fields(field_dict: dict) -> list:
    """
    Get list of non-official fields present in the field dictionary

    Args:
        field_dict: Dictionary of field name -> value

    Returns:
        List of extra/artifact field names
    """
    metadata_fields = {'dataset_name', 'annotator_id', 'pdf_file', '@context', '@type', '@id'}
    extra = []

    for field_name in field_dict.keys():
        if field_name not in OFFICIAL_CROISSANT_FIELDS and field_name not in metadata_fields:
            extra.append(field_name)

    return sorted(extra)
