"""
Field type definitions and evaluation strategies for CroissantMiner

Defines how different types of metadata fields should be evaluated
by the LLM judge.
"""

from enum import Enum
from typing import Dict, List


class FieldType(Enum):
    """Types of metadata fields with different evaluation strategies"""

    # Atomic fields - single value, strict matching
    ATOMIC = "atomic"  # name, license, datePublished, inLanguage

    # Description fields - longer text, semantic similarity
    DESCRIPTION = "description"  # sc:description, rai:dataCollection

    # URL fields - exact or semantic URL matching
    URL = "url"  # sc:url, @id

    # Citation fields - flexible format matching
    CITATION = "citation"  # cr:citeAs

    # Person/Organization fields - entity matching
    ENTITY = "entity"  # sc:creator, sc:publisher

    # List/Array fields - set overlap
    LIST = "list"  # dataModality, multiple values

    # Boolean fields - true/false/yes/no
    BOOLEAN = "boolean"  # cr:isLiveDataset


class EvaluationCategory(Enum):
    """LLM evaluation categories with scores"""
    CORRECT = 1.0
    PARTIALLY_CORRECT = 0.5
    MISSING = 0.0
    INCORRECT = 0.0


# Field name to field type mapping
FIELD_TYPE_MAPPING = {
    # Schema.org fields
    'sc:name': FieldType.ATOMIC,
    'sc:description': FieldType.DESCRIPTION,
    'sc:url': FieldType.URL,
    'sc:license': FieldType.ATOMIC,
    'sc:datePublished': FieldType.ATOMIC,
    'sc:inLanguage': FieldType.ATOMIC,
    'sc:publisher': FieldType.ENTITY,
    'sc:creator': FieldType.ENTITY,

    # Croissant fields
    'cr:citeAs': FieldType.CITATION,
    'cr:isLiveDataset': FieldType.BOOLEAN,
    'cr:dataModality': FieldType.LIST,
    'cro:dataModality': FieldType.LIST,

    # RAI fields
    'rai:dataCollection': FieldType.DESCRIPTION,
    'rai:dataCollectionTimeframe': FieldType.ATOMIC,
    'rai:dataAnnotationPlatform': FieldType.ATOMIC,
    'rai:annotatorDemographics': FieldType.DESCRIPTION,
    'rai:dataUseCases': FieldType.DESCRIPTION,
    'rai:personalSensitiveInformation': FieldType.DESCRIPTION,
}


def get_field_type(field_name: str) -> FieldType:
    """
    Get the field type for a given field name

    Args:
        field_name: Name of the field (e.g., 'sc:name', 'rai:dataCollection')

    Returns:
        FieldType enum value
    """
    # Direct lookup
    if field_name in FIELD_TYPE_MAPPING:
        return FIELD_TYPE_MAPPING[field_name]

    # Fallback: infer from field name patterns
    field_lower = field_name.lower()

    if 'description' in field_lower or 'collection' in field_lower or 'usecase' in field_lower:
        return FieldType.DESCRIPTION
    elif 'url' in field_lower or 'uri' in field_lower or '@id' in field_lower:
        return FieldType.URL
    elif 'cite' in field_lower or 'citation' in field_lower:
        return FieldType.CITATION
    elif 'creator' in field_lower or 'publisher' in field_lower or 'author' in field_lower:
        return FieldType.ENTITY
    elif 'date' in field_lower or 'year' in field_lower or 'time' in field_lower:
        return FieldType.ATOMIC
    elif 'language' in field_lower or 'license' in field_lower or 'name' in field_lower:
        return FieldType.ATOMIC
    else:
        # Default to atomic for unknown fields
        return FieldType.ATOMIC


def get_evaluation_instructions(field_type: FieldType) -> str:
    """
    Get LLM evaluation instructions specific to field type

    Args:
        field_type: Type of the field being evaluated

    Returns:
        Instructions string for LLM prompt
    """
    instructions = {
        FieldType.ATOMIC: """
For ATOMIC fields (single values like dates, names, languages):
- CORRECT: Semantically equivalent, different representations of same value
  * Dates: "2014" = "December 2014" = "2014-12-01" = "2014-12-15"
    - **Important for dates**: Focus on YEAR match. Different months/days within the same year are CORRECT.
    - Examples: "December 22, 2020" = "December 7, 2020" = "2020" (same year → CORRECT)
    - Only mark INCORRECT if years are completely different: "2020" vs "2021"
  * Languages: "en" = "English" = "english"
  * Dataset names (case-insensitive, version-aware):
    - "CIFAR-10" = "cifar-10" = "cifar10" = "CIFAR 10 dataset"
    - "FLORES-101" = "flores-101" = "flores" = "FLORES" (version numbers are OK)
    - "COCO" = "MS COCO" = "Microsoft COCO" = "Common Objects in Context"
    - "ImageNet-1K" = "ImageNet" (1K is subset size)
    - "MMLU" = "Massive Multitask Language Understanding" = "mmlu"
  * Acronyms and full names are equivalent
  * Dataset names with/without organization prefix: "databricks-dolly" = "dolly"
  * Dataset versions/subsets of same base dataset are CORRECT
  * **Be case-insensitive for all name comparisons**
  * **Version numbers (like -101, -1K) and hyphens are formatting - treat as same dataset**
- PARTIALLY_CORRECT: Partially matches (e.g., "MIT" vs "MIT and Stanford")
- INCORRECT: Refers to completely different dataset/entity
- MISSING: Empty or not provided

**Important**: Focus on whether values refer to the SAME dataset/entity, not exact string match. Be VERY lenient with naming variations, case differences, and version numbers.
""",

        FieldType.DESCRIPTION: """
For DESCRIPTION fields (longer text):
- CORRECT: Captures the essential meaning and key facts
  * May be shorter/longer than groundtruth
  * Different wording is acceptable
  * Focus on semantic content, not exact phrasing
  * Missing minor details is OK if core purpose is clear
- PARTIALLY_CORRECT: Has the general idea but missing significant important details
- INCORRECT: Wrong information or fundamentally different dataset/purpose
- MISSING: Empty or not provided

**Important**: Descriptions can vary significantly in length and detail while still being correct.
""",

        FieldType.URL: """
For URL fields:
- CORRECT: Same resource or semantically equivalent URLs
  * http vs https (same domain/path)
  * Trailing slash differences
  * Different URLs pointing to SAME dataset (e.g., GitHub vs HuggingFace mirrors)
  * Different versions/subsets of same dataset (e.g., full dataset vs subset)
- PARTIALLY_CORRECT: Related resource (e.g., project page vs dataset download page)
- INCORRECT: Completely different unrelated URL
- MISSING: Empty or not provided

**Important**: Same dataset may have multiple valid URLs (mirrors, versions, subsets).
""",

        FieldType.CITATION: """
For CITATION fields:
- CORRECT: Contains correct authors, title, year (format may vary)
- PARTIALLY_CORRECT: Has some correct elements but incomplete
- INCORRECT: Wrong citation
- MISSING: Empty or not provided
""",

        FieldType.ENTITY: """
For ENTITY fields (people, organizations):
- CORRECT: Same entity/entities, different representations acceptable
  * "Pratap et al" = "Vineel Pratap" (first author)
  * "Facebook AI" = "Facebook AI Research" = "Meta AI"
  * "Microsoft" = "Microsoft Research"
  * Multiple authors listed vs "et al" format
  * Organization vs individual researchers from that organization
- PARTIALLY_CORRECT: Related but incomplete (e.g., one author out of many when all should be listed)
- INCORRECT: Completely different entity/person
- MISSING: Empty or not provided

**Important**: Many valid ways to refer to same entity - be lenient with format differences.
""",

        FieldType.LIST: """
For LIST fields (multiple values):
- CORRECT: Contains all or most key items (>80% overlap)
- PARTIALLY_CORRECT: Contains some items (30-80% overlap)
- INCORRECT: Mostly wrong items (<30% overlap)
- MISSING: Empty or not provided
""",

        FieldType.BOOLEAN: """
For BOOLEAN fields (yes/no):
- CORRECT: Same boolean value - ANY representation of true/false that means the same thing
  * TRUE values (all equivalent): "True" = "true" = "TRUE" = "Yes" = "yes" = "1" = "Y" = "y"
  * FALSE values (all equivalent): "False" = "false" = "FALSE" = "No" = "no" = "0" = "N" = "n"
  * **Be case-insensitive and format-flexible**
  * Examples of CORRECT matches:
    - "True" = "Yes" ✓
    - "True" = "1" ✓
    - "False" = "No" ✓
    - "False" = "0" ✓
- INCORRECT: Opposite boolean values
  * "True" vs "False"
  * "Yes" vs "No"
  * "1" vs "0"
- MISSING: Empty or not provided

**Important**: Focus on the BOOLEAN MEANING (true vs false), not the exact representation format.
"""
    }

    return instructions.get(field_type, instructions[FieldType.ATOMIC])


def get_field_examples(field_type: FieldType) -> List[Dict]:
    """
    Get example evaluations for each field type

    Args:
        field_type: Type of the field

    Returns:
        List of example {predicted, groundtruth, category, reasoning}
    """
    examples = {
        FieldType.ATOMIC: [
            {
                "predicted": "2014",
                "groundtruth": "December 2014",
                "category": "CORRECT",
                "reasoning": "Same year, month detail doesn't change correctness"
            },
            {
                "predicted": "English",
                "groundtruth": "en",
                "category": "CORRECT",
                "reasoning": "Semantically equivalent language codes"
            }
        ],

        FieldType.DESCRIPTION: [
            {
                "predicted": "LibriSpeech ASR corpus",
                "groundtruth": "LibriSpeech: An ASR corpus based on public domain audio books",
                "category": "PARTIALLY_CORRECT",
                "reasoning": "Contains core information but missing key detail about audio books"
            },
            {
                "predicted": "Dataset for speech recognition",
                "groundtruth": "LibriSpeech: An ASR corpus based on public domain audio books",
                "category": "PARTIALLY_CORRECT",
                "reasoning": "General description matches purpose but missing specifics"
            }
        ],

        FieldType.ENTITY: [
            {
                "predicted": "Microsoft Research",
                "groundtruth": "Microsoft Research and collaborators",
                "category": "CORRECT",
                "reasoning": "Main entity is correct, 'and collaborators' is additional detail"
            }
        ]
    }

    return examples.get(field_type, [])
