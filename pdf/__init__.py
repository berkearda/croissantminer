"""PDF processing module for reading and processing academic papers."""

from .reader import download_pdf, extract_text_from_pdf
from .processor import (
    clean_text,
    process_paper,
    extract_targeted_sections,
    process_sections,
    chunk_for_llm,
    save_processed_paper
)

__all__ = [
    'download_pdf',
    'extract_text_from_pdf',
    'clean_text',
    'process_paper',
    'extract_targeted_sections',
    'process_sections',
    'chunk_for_llm',
    'save_processed_paper'
]
