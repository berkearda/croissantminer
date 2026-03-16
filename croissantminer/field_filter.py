"""
Field filtering for CroissantMiner evaluation

Defines the official 30 Croissant metadata fields (10 general + 20 RAI)
that should be evaluated. Filters out parsing artifacts and non-standard fields.
"""

# Official 30 Croissant metadata fields (10 General + 20 RAI)
OFFICIAL_CROISSANT_FIELDS = {
    # General attributes (10 fields)
    'sc:name',
    'sc:description',
    'sc:url',
    'sc:license',
    'sc:creator',
    'sc:publisher',
    'sc:datePublished',
    'sc:inLanguage',
    'cr:citeAs',
    'cr:isLiveDataset',

    # RAI attributes (20 fields)
    'rai:dataCollection',
    'rai:dataCollectionType',
    'rai:dataCollectionMissingData',
    'rai:dataCollectionRawData',
    'rai:dataCollectionTimeframe',
    'rai:dataImputationProtocol',
    'rai:dataManipulationProtocol',
    'rai:dataPreprocessingProtocol',
    'rai:dataAnnotationProtocol',
    'rai:dataAnnotationPlatform',
    'rai:dataAnnotationAnalysis',
    'rai:annotationsPerItem',
    'rai:annotatorDemographics',
    'rai:machineAnnotationTools',
    'rai:dataReleaseMaintenancePlan',
    'rai:personalSensitiveInformation',
    'rai:dataSocialImpact',
    'rai:dataBiases',
    'rai:dataLimitations',
    'rai:dataUseCases',
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
