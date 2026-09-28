"""Metadata extraction module for extracting and unifying dataset metadata."""

from .extractor import (
    setup_llm_pipeline,
    extract_metadata,
    extract_metadata_full_pdf,
    parse_metadata_results
)
from .unifier import unify_metadata, convert_to_croissant
from .relevance import select_relevant_sections

__all__ = [
    'setup_llm_pipeline',
    'extract_metadata',
    'extract_metadata_full_pdf',
    'parse_metadata_results',
    'unify_metadata',
    'convert_to_croissant',
    'select_relevant_sections'
]
