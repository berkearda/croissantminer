"""
Configuration settings for the metadata extraction pipeline
"""

from pathlib import Path

# Project paths
PROJECT_ROOT = Path(__file__).parent  # croissantminer directory
DATA_DIR = PROJECT_ROOT / "data"
DATACARD_DIR = PROJECT_ROOT / "datacard"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

# Create directories if they don't exist
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Default parameters
DEFAULT_MODEL_ID = "gpt-4o"  # Testing GPT-4o for 80%+ accuracy
MODEL_CONFIGS = {
    "temperature": 0.3,
    "max_tokens": 8192,  # Increased for Gemini to support full JSON responses
    "device": "auto"  # For HuggingFace models
}
MAX_SECTION_TOKENS = 1000  # Token limit for section chunking
MAX_SECTIONS = 15          # Maximum number of sections to process

# Extraction mode configuration
EXTRACTION_MODE = "full-pdf"  # Options: "multi-section" or "full-pdf"
# "multi-section": Extract from 8 sections separately, then unify (8 LLM calls)
# "full-pdf": Extract from entire PDF in one call (1 LLM call)

MAX_PDF_CHARS = 300000  # Maximum characters for full-PDF mode (increased for better accuracy - cost not a concern)

# Metadata schema fields (used in JSON template)
METADATA_SCHEMA = {
   "description": "Not mentioned",
   "license": "Not mentioned",
   "name": "Not mentioned",
   "url": "Not mentioned",
   "creator": {
       "@type": "Organization or Person",
       "name": "Not mentioned"
   },
   "publisher": "Not mentioned",  # Who published this dataset?
   "datePublished": "Not mentioned",
   "inLanguage": "Not mentioned",  # What language(s) is the dataset in?
   "citeAs": "Not mentioned",  # How should this dataset be cited?
   "isLiveDataset": "Not mentioned",  # Is this dataset continuously updated?
   
   "dataCollection": "Not mentioned",  # How was the data collected?
   "dataCollectionTimeframe": "Not mentioned",  # When was the data collected?
   "dataAnnotationPlatform": "Not mentioned",  # What platform was used for annotation?
   "annotatorDemographics": "Not mentioned",  # What are the demographics of annotators?
   "dataUseCases": "Not mentioned",  # What are the intended uses for this data?
   "personalSensitiveInformation": "Not mentioned"  # Does the dataset contain personal information?
}