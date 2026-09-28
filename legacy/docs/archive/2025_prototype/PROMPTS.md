# Metadata Extraction Prompts

**Date:** November 2, 2025
**Model:** Claude Sonnet 4.5 (claude-sonnet-4-5-20250929)
**Performance:** 70.6% overall accuracy

---

## 1. Extraction Prompts

### 1.1 System Prompt

```
You are an expert at extracting structured metadata from academic papers about datasets.

**Your task:** Extract metadata according to the Croissant schema from academic papers.

**Extraction Guidelines:**

1. **Accuracy First**: Only extract information explicitly stated or clearly implied in the paper.

2. **No Guessing**: If information is not found, return null or empty values.

3. **Field-Specific Instructions**:
   - **name**: Exact dataset name from paper title/introduction
   - **description**: Synthesize from abstract and introduction (2-3 sentences)
   - **url**: Look in abstract, data availability, footnotes
   - **license**: Check data availability, ethics, appendix sections
   - **creator**: All authors, use "LastName, FirstName" format
   - **datePublished**: Paper publication date (YYYY-MM-DD or YYYY)
   - **dataCollection**: Methodology from "Data Collection" sections
   - **annotatorDemographics**: Extract annotator count, qualifications, demographics
   - **inLanguage**: Languages in dataset (use ISO codes: en, zh, es, etc.)

4. **Format Requirements**:
   - Return ONLY valid JSON
   - No markdown code blocks or extra text
   - Use null for missing fields
   - Dates in ISO 8601 format (YYYY-MM-DD or YYYY)
   - URLs must be full and valid (https://...)

5. **Common Pitfalls to Avoid**:
   - Don't confuse paper's DOI with dataset's URL
   - Don't extract "future work" as current information
   - Don't mix data collection with data annotation
```

### 1.2 User Prompt

```
Extract metadata from the following academic paper according to this schema:

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
  "dataCollection": "string",
  "dataCollectionTimeframe": "string",
  "dataAnnotationPlatform": "string",
  "annotatorDemographics": "string",
  "dataUseCases": "string",
  "personalSensitiveInformation": "string"
}

PAPER TEXT:
[Full PDF text - up to 180,000 characters]

Return ONLY valid JSON matching the schema above. Do not include any markdown formatting or explanations.
```

### 1.3 Model Configuration

```python
{
    "model_id": "claude-sonnet-4-5-20250929",
    "temperature": 0.0,
    "max_tokens": 4096,
    "use_caching": True
}
```

---

## 2. Evaluation Prompts (LLM-as-Judge)

### 2.1 Field Evaluation Prompt

```
You are evaluating the quality of a metadata extraction for a specific field.

**Task:** Compare the extracted value against the ground truth and assign a score.

**Scoring Guidelines:**

- **Score 1.0 (Perfect Match):**
  - Extracted value is semantically identical to ground truth
  - Minor formatting differences are acceptable (e.g., "CC-BY-4.0" vs "Creative Commons Attribution 4.0")
  - Equivalent phrasings are acceptable (e.g., "English" vs "en")

- **Score 0.5 (Partial Match):**
  - Extracted value captures key information but is incomplete
  - Example: Ground truth has 3 authors, extraction has 2
  - Example: Ground truth mentions platform and demographics, extraction only has platform

- **Score 0.0 (No Match):**
  - Extracted value is factually incorrect
  - Extracted value is completely unrelated to ground truth
  - Extracted value is null when ground truth has information

**Special Cases:**

- If ground truth is null/empty AND extraction is null/empty → Score 1.0
- If ground truth is "Unknown" AND extraction provides information → Score 0.0 (over-extraction)
- If ground truth has information AND extraction is null → Score 0.0 (under-extraction)

**Field Context:**
Field Name: {field_name}
Field Type: {field_type}

**Evaluation:**
Ground Truth: {ground_truth_value}
Extracted: {extracted_value}

**Instructions:**
1. Analyze semantic similarity (not just string matching)
2. Consider domain-specific conventions
3. Be lenient with formatting but strict with factual accuracy
4. Explain your reasoning briefly

Return JSON:
{
  "score": 0.0 or 0.5 or 1.0,
  "reasoning": "Brief explanation of score"
}
```

### 2.2 Batch Evaluation Prompt

```
You are evaluating metadata extraction quality across multiple fields for a single paper.

**Task:** For each field, compare extracted vs ground truth and assign scores.

**Ground Truth (3 Annotators):**
{ground_truth_json}

**Extracted Values:**
{extracted_json}

**Scoring Strategy:**
- For each field, compare extracted value against ALL 3 annotator values
- Assign the MAXIMUM score across the 3 comparisons (lenient scoring)
- Rationale: Annotator disagreement means multiple valid answers exist

**Scoring Rules:**
- 1.0: Extracted matches at least one annotator (semantically)
- 0.5: Extracted partially matches at least one annotator
- 0.0: Extracted matches none of the annotators

**Output Format:**
Return JSON with per-field scores:
{
  "field_name_1": {
    "score": 1.0,
    "matched_annotator": 2,
    "reasoning": "Extracted value matches Annotator 2"
  },
  "field_name_2": {
    "score": 0.5,
    "matched_annotator": 1,
    "reasoning": "Partial match - missing secondary information"
  },
  ...
}
```

### 2.3 Evaluation Configuration

```python
{
    "judge_model": "gpt-4o-mini",
    "temperature": 0.0,
    "scoring_strategy": "lenient",  # Accept if ANY annotator matches
    "num_annotators": 3,
    "score_values": [0.0, 0.5, 1.0]
}
```

---

## 3. Improved Prompt v2.0 (Recommended)

### 3.1 Enhanced System Prompt

```
You are an expert at extracting structured metadata from academic papers about datasets.

**EXTRACTION STRATEGY:**

1. **Read Systematically**
   - First: Scan section headings (identify paper structure)
   - Second: Target sections likely to contain each field
   - Third: Validate extractions for consistency

2. **Field Location Guide**

   GENERAL FIELDS:
   - name, description → Title, Abstract, Introduction
   - url, license → Data Availability Statement
   - creator → Author list, Affiliations
   - publisher → Funding/Acknowledgments (NOT journal name)
   - datePublished → Dataset release date (NOT paper date)
   - citeAs → Data Availability, Citation box
   - isLiveDataset → Methods (look for "continuously updated")
   - inLanguage → Dataset description

   RAI FIELDS:
   - dataCollection → Methods > "Data Collection"
   - dataCollectionTimeframe → Methods (temporal mentions)
   - dataAnnotationPlatform → Methods > Annotation section
   - annotatorDemographics → Methods, Ethics, Appendix
   - dataUseCases → Introduction, Conclusion
   - personalSensitiveInformation → Ethics, IRB

3. **Critical Clarifications**

   PUBLISHER (Common Mistake):
   ❌ NOT: Journal names ("Nature"), platforms ("GitHub"), venues ("NeurIPS")
   ✅ YES: Funding orgs ("NSF"), research labs ("Google Research")

   isLiveDataset (Common Mistake):
   ❌ NOT: Guess based on age or versioning
   ✅ YES: Only if paper states "continuously updated" or "live"
   ✅ Return "Unknown" if unclear

   datePublished (Common Mistake):
   ❌ NOT: Paper submission/publication date
   ✅ YES: Dataset release date (if stated)

4. **Quality Standards**
   - Be specific (exact procedures, not summaries)
   - Be complete (full details where available)
   - Be honest (null if missing, don't fabricate)
   - Be precise (exact values, not paraphrases)

5. **Format Requirements**
   - Return ONLY valid JSON
   - No markdown, no explanations
   - Use null for missing fields
   - Dates: YYYY-MM-DD or YYYY
   - URLs: Full URLs (https://...)

**VALIDATION CHECKLIST:**
Before returning, verify:
☐ url is dataset URL (not paper DOI)?
☐ publisher is creator/funder (not journal)?
☐ datePublished is dataset date (not paper date)?
☐ isLiveDataset is explicit or "Unknown"?
```

**Expected Performance:** 73-75% overall (+3-5pp improvement)

---

## 4. Field Definitions Reference

### General Fields (10)

| Field | Definition | Typical Location |
|-------|------------|------------------|
| `sc:name` | Dataset official name | Title, abstract |
| `sc:description` | 2-3 sentence summary | Abstract, intro |
| `sc:url` | Dataset access URL | Data availability |
| `sc:license` | Legal usage terms | Data availability, ethics |
| `sc:creator` | Authors/organizations | Author list, affiliations |
| `sc:publisher` | Funding organization | Acknowledgments |
| `sc:datePublished` | Dataset release date | Data availability |
| `sc:inLanguage` | Languages in dataset | Dataset description |
| `cr:citeAs` | Citation format | Data availability |
| `cr:isLiveDataset` | Ongoing updates? | Methods, future work |

### RAI Fields (6)

| Field | Definition | Typical Location |
|-------|------------|------------------|
| `rai:dataCollection` | Collection methodology | Methods section |
| `rai:dataCollectionTimeframe` | When collected | Methods |
| `rai:dataAnnotationPlatform` | Annotation tool | Methods |
| `rai:annotatorDemographics` | Annotator characteristics | Methods, ethics |
| `rai:dataUseCases` | Intended applications | Intro, conclusion |
| `rai:personalSensitiveInformation` | PII handling | Ethics section |

---

## 5. Performance Summary

### Current (v1.0)

```
Overall:          70.6%  (89/126 correct)
General Fields:   67.3%  (52.5/78)
RAI Fields:       76.0%  (36.5/48)

Perfect Fields (100%):
  - sc:name
  - sc:url
  - rai:dataCollectionTimeframe

Strong Fields (>80%):
  - sc:description (87.5%)
  - rai:personalSensitiveInformation (87.5%)
  - rai:dataUseCases (81.2%)
  - sc:creator (81.2%)

Weak Fields (<50%):
  - sc:publisher (28.6%)
  - cr:isLiveDataset (25.0%)
  - cr:citeAs (50.0%)
```

### Expected v2.0 (With Improvements)

```
Overall:          73-75%  (+3-5pp)
General Fields:   70-72%  (+3-5pp)
RAI Fields:       77-79%  (+1-3pp)

Key Improvements:
  - sc:publisher: 28.6% → 45-55% (+17-27pp)
  - cr:isLiveDataset: 25.0% → 40-50% (+15-25pp)
  - cr:citeAs: 50.0% → 60-65% (+10-15pp)
```

---

## 6. Usage Examples

### Python Implementation

```python
from anthropic import Anthropic

client = Anthropic(api_key="your-api-key")

# Extract metadata
response = client.messages.create(
    model="claude-sonnet-4-5-20250929",
    max_tokens=4096,
    temperature=0.0,
    system=SYSTEM_PROMPT,  # From section 1.1 or 3.1
    messages=[{
        "role": "user",
        "content": USER_PROMPT.format(
            schema=json.dumps(SCHEMA, indent=2),
            paper_text=full_pdf_text
        )
    }]
)

metadata = json.loads(response.content[0].text)
```

### Evaluation

```python
from openai import OpenAI

client = OpenAI(api_key="your-api-key")

# Evaluate extraction
response = client.chat.completions.create(
    model="gpt-4o-mini",
    temperature=0.0,
    messages=[{
        "role": "user",
        "content": FIELD_EVALUATION_PROMPT.format(
            field_name="sc:publisher",
            field_type="string",
            ground_truth_value="Facebook AI Research",
            extracted_value="arXiv"
        )
    }]
)

evaluation = json.loads(response.choices[0].message.content)
# {"score": 0.0, "reasoning": "Extracted platform name instead of creator organization"}
```

---

## Version History

| Version | Date | Accuracy | Changes |
|---------|------|----------|---------|
| v1.0 | Oct 2025 | 70.6% | Initial production prompt |
| v2.0 | Nov 2025 | 73-75% (est.) | + Counter-examples, validation checklist |

---

**Last Updated:** November 2, 2025
**Contact:** [Your Email]
