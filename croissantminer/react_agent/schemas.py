"""Canonical 30-field schema for the ReAct agent.

Re-exports CANONICAL_FIELDS from validation.validate_extraction so there's
a single source of truth across extraction, validation, and evaluation.
"""

from __future__ import annotations

from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from validation.validate_extraction import CANONICAL_FIELDS  # noqa: E402

CORE_FIELDS = (
    "name", "description", "url", "license", "creator", "publisher",
    "datePublished", "inLanguage", "citeAs", "isLiveDataset",
)

RAI_FIELDS = tuple(sorted(f for f in CANONICAL_FIELDS if f.startswith("rai:")))

assert len(CANONICAL_FIELDS) == 30
assert set(CORE_FIELDS) | set(RAI_FIELDS) == CANONICAL_FIELDS


FIELD_DEFINITIONS: dict[str, str] = {
    "name": "Dataset name as stated in the paper.",
    "description": "Brief 1-3 sentence description of the dataset.",
    "url": "URL where the dataset can be accessed.",
    "license": "License (e.g., MIT, CC-BY-4.0). Prefer SPDX identifiers.",
    "creator": "Creator(s) — named individuals if given, else organization. Format: 'Name1, Name2 (Organization)'.",
    "publisher": "Organization that published the dataset (not the conference venue).",
    "datePublished": "Dataset release date as YYYY or YYYY-MM-DD (not arXiv submission).",
    "inLanguage": "Language(s) of the dataset, ISO 639-1 codes (e.g., 'en', 'de').",
    "citeAs": "Recommended citation for the dataset.",
    "isLiveDataset": "'Yes', 'No', or null — whether the dataset is actively updated.",
    "rai:dataCollection": "Description of the data collection process.",
    "rai:dataCollectionType": "From controlled vocab: Surveys, Secondary Data analysis, Physical data collection, Direct measurement, Document analysis, Manual Human Curator, Software Collection, Experiments, Web Scraping, Web API, Focus groups, Self-reporting, Customer feedback data, User-generated content data, Passive Data Collection, Others. Comma-separated if multiple.",
    "rai:dataCollectionMissingData": "Description of missing data — only if the paper explicitly discusses it.",
    "rai:dataCollectionRawData": "Description of raw / source data before preprocessing.",
    "rai:dataCollectionTimeframe": "Timeframe (start/end dates or period) when the data was collected.",
    "rai:dataImputationProtocol": "How missing or incomplete values were imputed or filled — only if applicable.",
    "rai:dataManipulationProtocol": "Post-preprocessing manipulations: augmentation, balancing, resampling — only if applicable.",
    "rai:dataPreprocessingProtocol": "Cleaning, filtering, normalization, tokenization steps applied to raw data.",
    "rai:dataAnnotationProtocol": "How labels were created: task description, instructions to annotators, QC process.",
    "rai:dataAnnotationPlatform": "Platform used (e.g., Amazon Mechanical Turk, Label Studio, Prolific, custom tool).",
    "rai:dataAnnotationAnalysis": "Annotation quality analysis: inter-annotator agreement metrics, validation procedures.",
    "rai:annotationsPerItem": "Number of independent annotations collected per item.",
    "rai:annotatorDemographics": "Demographics of annotators (expertise, nationality, language, etc.).",
    "rai:machineAnnotationTools": "Machine / ML tools used anywhere in the annotation pipeline.",
    "rai:dataReleaseMaintenancePlan": "Versioning, update cadence, maintenance commitments. Often null (~75%).",
    "rai:personalSensitiveInformation": "Sensitive attributes collected (PII, demographics, health, etc.).",
    "rai:dataSocialImpact": "Discussion of social / ethical impact of the dataset.",
    "rai:dataBiases": "Explicitly acknowledged biases — not generic 'all datasets have biases' statements.",
    "rai:dataLimitations": "Known limitations and non-recommended use cases.",
    "rai:dataUseCases": "Intended / anticipated use cases.",
}

assert set(FIELD_DEFINITIONS) == CANONICAL_FIELDS


NULLISH_STRINGS = {"null", "none", "n/a", "na", "not mentioned", "not applicable", "unknown", ""}


def coerce_nulls(data: dict) -> dict:
    """Coerce string 'null' / 'None' / 'N/A' / '' to real None in-place."""
    for k, v in list(data.items()):
        if isinstance(v, str) and v.strip().lower() in NULLISH_STRINGS:
            data[k] = None
    return data


def empty_extraction() -> dict:
    """Return a dict with all 30 canonical fields initialised to None."""
    return {f: None for f in CORE_FIELDS + RAI_FIELDS}
