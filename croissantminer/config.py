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

4. **General Field-Specific Information:**
   *For standard schema.org / Croissant fields:*

   - **creator**: The creator/author of this dataset (schema.org/creator). Prefer the most specific attribution available. If the paper names individual authors, list them. If only an organization is named, use the organization. When both are available, use the format: "Name1, Name2 (Organization)". Do not list all paper authors if they are not explicitly identified as dataset creators — some papers distinguish between paper authors and dataset creators.
     GOOD: "Karl Cobbe, Vineet Kosaraju, Mohammad Bavarian, Mark Chen, Heewoo Jun, Lukasz Kaiser (OpenAI)"
     GOOD: "Allen Institute for AI" (when paper only names the organization)
     BAD: "OpenAI" (when the paper explicitly lists individual creator names)

   - **datePublished**: Date the DATASET was first published or released (not the paper's arxiv submission date). Use the dataset's release date if explicitly stated. If only a year is mentioned (e.g., "released in 2021"), use "YYYY" format. If an exact date is given, use "YYYY-MM-DD". If the paper does not distinguish between paper and dataset publication dates, use the paper's publication year.
     GOOD: "2021" (paper says "We release GSM8K in 2021")
     GOOD: "2018-03-14" (paper states exact release date)
     BAD: "2021-10-28" (arxiv submission timestamp when paper doesn't state a dataset release date)

5. **RAI Field-Specific Information:**
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
     [EXTRACTION GUIDE] This field is ONLY about the labeling/annotation process — how labels, ratings, or tags were assigned to data items. Do NOT include data collection methodology (→ rai:dataCollection), cleaning/filtering steps (→ rai:dataPreprocessingProtocol), or post-processing modifications like augmentation or balancing (→ rai:dataManipulationProtocol). Include: annotation task description, annotator instructions, workforce type (crowdworkers, experts, authors), quality control steps (e.g., majority voting, adjudication), and annotation format. If the dataset has no human or machine annotation step (e.g., questions sourced from existing exams), return null.
     GOOD: "Crowdworkers on MTurk were asked to formulate questions about Wikipedia passages and highlight answer spans. Workers were required to have 97% HIT acceptance rate. Each question received 3 independent answers for evaluation."
     BAD: "The dataset was collected from Wikipedia articles and filtered for quality." (This describes data collection and preprocessing, not annotation.)
   - **rai:dataAnnotationPlatform**: Platform, tool, or library used to collect annotations by human annotators.
   - **rai:dataAnnotationAnalysis**: Considerations related to the process of converting the "raw" annotations into the final labels (e.g., uncertainty, disagreement analysis).
   - **rai:dataReleaseMaintenancePlan**: Versioning information in terms of the updating timeframe, the maintainers, and the deprecation policies.
     [EXTRACTION GUIDE] Most academic papers do NOT discuss maintenance plans, versioning schedules, or deprecation policies. Return null unless the paper EXPLICITLY mentions: version numbering, planned updates, a maintenance team, or deprecation timelines. Do not infer or fabricate maintenance information — a statement like "the dataset is publicly available" is NOT a maintenance plan. This is one of the most commonly hallucinated fields.
     GOOD: "The dataset is maintained by the LMSYS team with quarterly updates. Version 2.0 was released in March 2024 with expanded language coverage."
     BAD: "The dataset is maintained by the authors and updated regularly." (Fabricated — paper says nothing about maintenance.)
     MOST LIKELY CORRECT ANSWER: null
   - **rai:personalSensitiveInformation**: Any sensitive human attribute(s) collected as part of this dataset (e.g., gender, socio-economic status, geography, language, age, culture, experience).
   - **rai:dataSocialImpact**: Discussion of social implications, if applicable.
   - **rai:dataBiases**: Description of biases in the dataset, if applicable.
     [EXTRACTION GUIDE] Look specifically in the paper's Limitations, Ethics Statement, Discussion, or Broader Impact sections. Only extract biases the authors EXPLICITLY discuss — do not add generic bias warnings. Types of bias to look for: geographic/cultural bias (e.g., "questions biased toward North American curricula"), demographic bias (e.g., underrepresentation of certain groups), selection bias (e.g., "only English-language sources"), temporal bias, annotator bias, or label bias. If authors acknowledge no specific biases, return null rather than inventing generic concerns.
     GOOD: "The authors note that questions are biased toward North American educational standards and may not represent global curricula. English-only sources limit cross-lingual generalization."
     BAD: "The dataset may contain biases inherent in the source data." (Too vague — does not reflect any specific discussion in the paper.)
   - **rai:dataLimitations**: Known limitations (e.g., data generalization limits, quality issues) and non-recommended uses.
   - **rai:dataUseCases**: Dataset use(s) (e.g., Training, Testing, Validation, Fine Tuning) and Usage Guidelines.
   - **rai:annotationsPerItem**: Number of human labels per dataset item.
   - **rai:annotatorDemographics**: List of demographics specifications about the annotators.
   - **rai:machineAnnotationTools**: List of software used for data annotation (e.g., NER tools, automated labelers).'''

# User prompt template for RAI metadata extraction
USER_PROMPT_TEMPLATE = '''Extract metadata from the following academic paper by matching text to the field descriptions above. Your output must conform exactly to the following schema:

SCHEMA:
{
  "name": "string",
  "description": "string",
  "url": "string",
  "license": "string",
  "creator": "object or string",
  "publisher": "string",
  "datePublished": "string (YYYY-MM-DD or YYYY)",
  "inLanguage": "string (ISO codes)",
  "citeAs": "string",
  "isLiveDataset": "string (Yes/No)",

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