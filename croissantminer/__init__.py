"""
CroissantMiner: Automated Metadata Extraction for ML Datasets

Extracts structured metadata from academic papers following the
MLCommons Croissant RAI schema using Large Language Models.
"""

__version__ = "0.1.0"

from .config import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE, METADATA_SCHEMA
from .extractor import extract_metadata_full_pdf, setup_llm_pipeline
from .metrics import (
    bootstrap_ci,
    mcnemar_test,
    cohens_h,
    krippendorff_alpha,
    fleiss_kappa,
)
