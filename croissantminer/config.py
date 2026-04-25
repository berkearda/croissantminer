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

# Metadata schema fields (10 General + 20 RAI = 30 fields)
METADATA_SCHEMA = {
    # ===== GENERAL FIELDS (10) =====
    "name": None,
    "description": None,
    "url": None,
    "license": None,
    "creator": None,
    "publisher": None,
    "datePublished": None,
    "inLanguage": None,
    "citeAs": None,
    "isLiveDataset": None,

    # ===== RAI FIELDS (20) =====
    "rai:dataCollection": None,
    "rai:dataCollectionType": None,
    "rai:dataCollectionMissingData": None,
    "rai:dataCollectionRawData": None,
    "rai:dataCollectionTimeframe": None,
    "rai:dataImputationProtocol": None,
    "rai:dataManipulationProtocol": None,
    "rai:dataPreprocessingProtocol": None,
    "rai:dataAnnotationProtocol": None,
    "rai:dataAnnotationPlatform": None,
    "rai:dataAnnotationAnalysis": None,
    "rai:annotationsPerItem": None,
    "rai:annotatorDemographics": None,
    "rai:machineAnnotationTools": None,
    "rai:dataReleaseMaintenancePlan": None,
    "rai:personalSensitiveInformation": None,
    "rai:dataSocialImpact": None,
    "rai:dataBiases": None,
    "rai:dataLimitations": None,
    "rai:dataUseCases": None
}

# System prompt for RAI metadata extraction
SYSTEM_PROMPT = '''You are an expert researcher specializing in "Responsible AI" and metadata extraction for Machine Learning datasets.

**Your Task:**
Extract structured metadata from the provided academic paper according to the MLCommons Croissant RAI schema described below.

**Extraction Guidelines:**
1. **Accuracy First:** Only extract information explicitly stated in the paper.
2. **No Guessing:** If information is not found, return null. Do not fill fields with your own background information or assumptions that are not explicitly given in the paper.
3. **Formatting Rules:**
   - Return ONLY valid JSON.
   - Use null for missing fields.
   - No markdown formatting.

4. **RAI Field-Specific Information:**
   *Use the following official definitions to guide your extraction. Use them as matching criteria when scanning the text:*

   - **rai:dataCollection**: Description of the data collection process.
   - **rai:dataCollectionType**: Define the data collection type(s). Choose one or multiple values from: Surveys, Secondary Data analysis, Physical data collection, Direct measurement, Document analysis, Manual Human Curator, Software Collection, Experiments, Web Scraping, Web API, Focus groups, Self-reporting, Customer feedback data, User-generated content data, Passive Data Collection, Others.
   - **rai:dataCollectionMissingData**: Description of missing data in textual form. Only if missingness is explicitly discussed.
   - **rai:dataCollectionRawData**: Description of the raw data collection (i.e., source of the data).
   - **rai:dataCollectionTimeframe**: Timeframe in terms of start and end date of the collection process.
   - **rai:dataImputationProtocol**: Description of data imputation process if applicable, i.e., how missing or incomplete data were imputed or filled.
   - **rai:dataManipulationProtocol**: Description of data manipulation process if applicable.
   - **rai:dataPreprocessingProtocol**: Description of the steps that were required to bring collected data to a state that can be processed by an ML model/algorithm (e.g., filtering out incomplete entries).
   - **rai:dataAnnotationProtocol**: Description of annotations (labels, ratings), and how these were created or authored.
   - **rai:dataAnnotationPlatform**: Platform, tool, or library used to collect annotations by human annotators.
   - **rai:dataAnnotationAnalysis**: Considerations related to the process of converting the "raw" annotations into the final labels (e.g., uncertainty, disagreement analysis).
   - **rai:dataReleaseMaintenancePlan**: Versioning information in terms of the updating timeframe, the maintainers, and the deprecation policies.
   - **rai:personalSensitiveInformation**: Any sensitive human attribute(s) collected as part of this dataset (e.g., gender, socio-economic status, geography, language, age, culture, experience).
   - **rai:dataSocialImpact**: Discussion of social implications, if applicable.
   - **rai:dataBiases**: Description of biases in the dataset, if applicable.
   - **rai:dataLimitations**: Known limitations (e.g., data generalization limits, quality issues) and non-recommended uses.
   - **rai:dataUseCases**: Dataset use case(s) (e.g., Training, Testing, Validation, Fine Tuning) and Usage Guidelines.
   - **rai:annotationsPerItem**: Number of human labels per dataset item.
   - **rai:annotatorDemographics**: List of demographics specifications about the annotators.
   - **rai:machineAnnotationTools**: List of software used for data annotation (e.g., NER tools, automated labelers).'''

# User prompt template for RAI metadata extraction
USER_PROMPT_TEMPLATE = '''Extract metadata from the following academic paper by matching text to the field descriptions above. Your output must conform exactly to the following schema:

SCHEMA:
{
  "sc:name": "string",
  "sc:description": "string",
  "sc:url": "string",
  "sc:license": "string",
  "sc:creator": "string",
  "sc:publisher": "string",
  "sc:datePublished": "string",
  "sc:inLanguage": "string",
  "cr:citeAs": "string",
  "cr:isLiveDataset": "string",

  "rai:dataCollection": "string",
  "rai:dataCollectionType": "string (Select from recommended values)",
  "rai:dataCollectionMissingData": "string",
  "rai:dataCollectionRawData": "string",
  "rai:dataCollectionTimeframe": "string",
  "rai:dataImputationProtocol": "string",
  "rai:dataManipulationProtocol": "string",
  "rai:dataPreprocessingProtocol": "string",

  "rai:dataAnnotationProtocol": "string",
  "rai:dataAnnotationPlatform": "string",
  "rai:dataAnnotationAnalysis": "string",
  "rai:annotationsPerItem": "string",
  "rai:annotatorDemographics": "string",
  "rai:machineAnnotationTools": "string",

  "rai:dataReleaseMaintenancePlan": "string",
  "rai:personalSensitiveInformation": "string",
  "rai:dataSocialImpact": "string",
  "rai:dataBiases": "string",
  "rai:dataLimitations": "string",
  "rai:dataUseCases": "string"
}

PAPER TEXT:
%s

Return ONLY valid JSON matching the schema above. Do not include any markdown formatting or explanations.'''