# LLM Evaluator Complete Prompt Documentation

This document contains the complete prompt used by the CroissantMiner LLM evaluator (GPT-4o-mini).

## System Message

```
You are an expert metadata extraction evaluator. Always respond with valid JSON only.
```

## User Message Template

```
You are an expert evaluator assessing metadata extraction quality.

**Task**: Compare the extracted value against the groundtruth value and determine if the extraction is correct.

**Field Name**: {field_name}
**Field Type**: {field_type}

**Extracted Value**:
{predicted}

**Groundtruth Value**:
{groundtruth}

{field_type_instructions}

**Your Task**:
1. Analyze semantic equivalence between extracted and groundtruth values
2. Assign ONE of these categories:
   - CORRECT (1.0): Semantically equivalent, valid subset, or accurate representation
   - PARTIALLY_CORRECT (0.5): Contains some correct information but incomplete or has extra info
   - INCORRECT (0.0): Wrong information or significantly different meaning
   - MISSING (0.0): Field is empty or not extracted

3. Provide brief reasoning (1-2 sentences)

**Response Format** (JSON only, no other text):
{
  "category": "CORRECT" | "PARTIALLY_CORRECT" | "INCORRECT" | "MISSING",
  "score": 1.0 | 0.5 | 0.0,
  "reasoning": "Brief explanation of your decision"
}
```

---

## Field Type Specific Instructions

### ATOMIC Fields
**Applies to**: sc:name, sc:license, sc:datePublished, sc:inLanguage, rai:dataCollectionTimeframe, rai:dataAnnotationPlatform

```
For ATOMIC fields (single values like dates, names, languages):
- CORRECT: Semantically equivalent, different representations of same value
  * Dates: "2014" = "December 2014" = "2014-12-01"
  * Languages: "en" = "English" = "english"
  * Names: "CIFAR-10" = "cifar10" = "CIFAR 10 dataset"
  * Dataset names: "COCO" = "MS COCO" = "Microsoft COCO" = "Common Objects in Context"
  * Acronyms and full names are equivalent: "MMLU" = "Massive Multitask Language Understanding"
  * Dataset names with/without organization prefix: "databricks-dolly" = "dolly"
  * Dataset versions/subsets of same base dataset are CORRECT
- PARTIALLY_CORRECT: Partially matches (e.g., "MIT" vs "MIT and Stanford")
- INCORRECT: Refers to completely different dataset/entity
- MISSING: Empty or not provided

**Important**: Focus on whether values refer to the SAME dataset/entity, not exact string match. Be very lenient with naming variations.
```

### DESCRIPTION Fields
**Applies to**: sc:description, rai:dataCollection, rai:annotatorDemographics, rai:dataUseCases, rai:personalSensitiveInformation

```
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
```

### URL Fields
**Applies to**: sc:url, @id

```
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
```

### CITATION Fields
**Applies to**: cr:citeAs

```
For CITATION fields:
- CORRECT: Contains correct authors, title, year (format may vary)
- PARTIALLY_CORRECT: Has some correct elements but incomplete
- INCORRECT: Wrong citation
- MISSING: Empty or not provided
```

### ENTITY Fields
**Applies to**: sc:creator, sc:publisher

```
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
```

### LIST Fields
**Applies to**: cr:dataModality, cro:dataModality

```
For LIST fields (multiple values):
- CORRECT: Contains all or most key items (>80% overlap)
- PARTIALLY_CORRECT: Contains some items (30-80% overlap)
- INCORRECT: Mostly wrong items (<30% overlap)
- MISSING: Empty or not provided
```

### BOOLEAN Fields
**Applies to**: cr:isLiveDataset

```
For BOOLEAN fields (yes/no):
- CORRECT: Same boolean value (true/yes/1 or false/no/0)
- INCORRECT: Opposite value or unclear
- MISSING: Empty or not provided
```

---

## Aggregation Strategy (Multi-Annotator)

When evaluating against multiple annotators (typically 3), the system uses **priority-based aggregation**:

```python
# Priority order: CORRECT > PARTIALLY_CORRECT > INCORRECT > MISSING

if ANY annotator marks as CORRECT:
    Final result = CORRECT (score: 1.0)
elif ANY annotator marks as PARTIALLY_CORRECT:
    Final result = PARTIALLY_CORRECT (score: 0.5)
else:
    Final result = INCORRECT or MISSING (score: 0.0)
```

**Rationale**: If an extraction matches ANY valid human annotation, it should be considered correct. This accounts for natural variation in groundtruth annotations.

---

## Special Cases

### Empty Predicted Value
```python
if predicted is empty:
    return {
        "category": "MISSING",
        "score": 0.0,
        "reasoning": "Field not extracted"
    }
```

### Empty Groundtruth Value
```python
if groundtruth is empty:
    return {
        "category": "CORRECT",
        "score": 1.0,
        "reasoning": "No groundtruth available for comparison"
    }
```

### "Unknown" Groundtruth Value
```python
if groundtruth in ["unknown", "n/a", "none", "null"]:
    return {
        "category": "CORRECT",
        "score": 1.0,
        "reasoning": "Groundtruth marked as 'Unknown', extracted value assumed correct"
    }
```

### Exact Match (Optimization)
```python
if predicted.lower() == groundtruth.lower():
    return {
        "category": "CORRECT",
        "score": 1.0,
        "reasoning": "Exact match (case-insensitive)"
    }
```

---

## Model Configuration

- **Model**: gpt-4o-mini
- **Temperature**: 0.0 (deterministic)
- **Max Tokens**: 200
- **Response Format**: JSON object
- **Caching**: Results are cached to avoid redundant API calls

---

## Example Evaluation

### Input:
```json
{
  "field_name": "sc:name",
  "field_type": "atomic",
  "predicted": "MS COCO",
  "groundtruth": "COCO"
}
```

### LLM Response:
```json
{
  "category": "CORRECT",
  "score": 1.0,
  "reasoning": "Both refer to the same dataset (Microsoft COCO). Different naming conventions are acceptable for atomic fields."
}
```

---

## File Location

**Implementation**: `evaluation/llm_evaluator.py`

**Field Type Definitions**: `evaluation/field_types.py`

**Date**: October 28, 2025
