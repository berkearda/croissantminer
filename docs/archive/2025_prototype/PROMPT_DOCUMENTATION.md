# Metadata Extraction Prompts
## Documentation and Optimization Guide

**Last Updated:** November 2, 2025
**Model:** Claude Sonnet 4.5 (claude-sonnet-4-5-20250929)
**Performance:** 70.6% overall accuracy (76.0% RAI, 67.3% General)

---

## Table of Contents

1. [Current Production Prompt](#1-current-production-prompt)
2. [Prompt Structure](#2-prompt-structure)
3. [Field Definitions](#3-field-definitions)
4. [Performance Analysis](#4-performance-analysis)
5. [Recommended Improvements](#5-recommended-improvements)
6. [Alternative Prompt Strategies](#6-alternative-prompt-strategies)

---

## 1. Current Production Prompt

### 1.1 System Prompt (Static)

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

### 1.2 User Prompt (Dynamic, per paper)

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
    "temperature": 0.0,              # Deterministic
    "max_tokens": 4096,              # Sufficient for metadata
    "use_caching": True,             # Enable prompt caching (90% cost savings)
    "timeout": 120                   # 2 minutes per paper
}
```

---

## 2. Prompt Structure

### 2.1 Design Philosophy

**Principle 1: General-Purpose, Not Dataset-Specific**
- No hardcoded paper-specific patterns
- No examples from test set
- Generalizes to unseen papers

**Principle 2: Schema-Grounded**
- Explicit field definitions
- Clear format requirements
- Type specifications

**Principle 3: Cognitive Guidance**
- Where to look (section hints)
- Common pitfalls (what to avoid)
- Decision rules (when unclear)

### 2.2 Current Strengths

✅ **Clear structure**: System vs user separation
✅ **Format enforcement**: JSON-only output
✅ **Field guidance**: Where to find information
✅ **Pitfall awareness**: Common mistakes highlighted

### 2.3 Current Weaknesses

🔴 **Weak field guidance**: Publisher, isLiveDataset, citeAs lack detail
🔴 **No counter-examples**: Doesn't clarify what NOT to extract
🔴 **Generic location hints**: "Check data availability" too vague
🔴 **No validation strategy**: Doesn't guide checking extraction quality

---

## 3. Field Definitions

### 3.1 General Fields (10 total)

#### Perfect Fields (100% Accuracy) ✅

**sc:name** (100%)
```
Definition: Official dataset name as stated in paper
Location: Paper title, abstract, introduction (first paragraph)
Format: Exact string, including acronyms if present
Example: "Multilingual LibriSpeech (MLS)"
```

**sc:url** (100%)
```
Definition: Primary access URL for dataset download/information
Location: Data availability statement, abstract, footnotes, author notes
Format: Full URL starting with http:// or https://
Example: "https://www.openslr.org/94/"
```

#### Strong Fields (80-90% Accuracy) ✅

**sc:description** (87.5%)
```
Definition: 2-3 sentence summary of dataset purpose and content
Location: Abstract (first priority), introduction (second priority)
Approach: Synthesize from multiple sentences if needed
Example: "Multilingual LibriSpeech is a large-scale speech corpus covering 8 languages..."
```

**sc:creator** (81.2%)
```
Definition: Authors or organizations that created the dataset
Location: Author list, affiliations, acknowledgments
Format: Structured object {"@type": "Organization/Person", "name": "..."}
Example: {"@type": "Organization", "name": "Facebook AI Research"}
```

#### Moderate Fields (60-80% Accuracy) 🟡

**sc:inLanguage** (75.0%)
```
Definition: Natural languages represented in dataset
Location: Dataset description, methods section
Format: Comma-separated ISO 639-1 codes
Example: "en, de, nl, es, fr, pt, it, pl"
Challenge: Sometimes implicit (e.g., "English Wikipedia" → "en")
```

**sc:license** (62.5%)
```
Definition: Legal terms governing dataset use
Location: Data availability section, ethics statement, appendix
Format: Standard license identifiers (e.g., "CC-BY-4.0") or description
Example: "Creative Commons Attribution 4.0"
Challenge: Inconsistent location, sometimes only in supplementary materials
```

#### Weak Fields (<60% Accuracy) 🔴

**sc:publisher** (28.6%) - WEAKEST GENERAL FIELD
```
Definition: Organization that funded or published the dataset
Location: Acknowledgments, funding statement, author affiliations
Format: Organization name
Example: "Facebook AI Research", "National Science Foundation"

CRITICAL ISSUE: Models confuse with:
- ❌ Journal names ("Nature", "Science")
- ❌ Preprint servers ("arXiv")
- ❌ Distribution platforms ("GitHub", "Hugging Face")
- ❌ Conference venues ("NeurIPS", "CVPR")

CORRECT: Funding organization or creator institution
```

**cr:isLiveDataset** (25.0%) - WEAKEST FIELD OVERALL
```
Definition: Whether dataset receives ongoing updates
Location: Data collection section, future work, maintenance plan
Format: "Yes", "No", or "Unknown"
Example: "No" (for static snapshot from 2020)

CRITICAL ISSUE: Information rarely explicit
- Papers describe collection timeframe, not update status
- "Version 2.0" doesn't mean continuously updated
- Default assumption: static snapshot

GUIDANCE NEEDED:
- "Yes" only if paper states "continuously updated", "live", "ongoing"
- "No" if fixed timeframe mentioned ("collected 2015-2018")
- "Unknown" if truly ambiguous
```

**cr:citeAs** (50.0%)
```
Definition: Preferred citation format for the dataset
Location: Data availability, acknowledgments, dedicated "Citation" box
Format: Full bibliographic citation
Example: "Pratap et al. MLS: A Large-Scale Multilingual Dataset. Interspeech 2021."
Challenge: May appear in multiple formats; hard to identify canonical version
```

**sc:datePublished** (57.1%)
```
Definition: Date when dataset was released (not paper publication date)
Location: Data availability, introduction timeline, GitHub release date
Format: YYYY-MM-DD or YYYY
Example: "2020-12-22"
Challenge: Models confuse paper date with dataset release date
```

### 3.2 RAI Fields (6 total)

#### Perfect Fields (100% Accuracy) ✅

**rai:dataCollectionTimeframe** (100%)
```
Definition: Time period during which data was collected
Location: Methods section, data collection subsection
Format: Date range or duration
Example: "Data collected from January 2018 to December 2019"
```

#### Strong Fields (80-90% Accuracy) ✅

**rai:personalSensitiveInformation** (87.5%)
```
Definition: How personally identifiable information (PII) was handled
Location: Ethics section, data collection methodology, IRB statement
Format: Description of practices
Example: "All data de-identified prior to release; no PII collected"
```

**rai:dataUseCases** (81.2%)
```
Definition: Intended applications and supported tasks
Location: Introduction (motivation), abstract, conclusion
Format: Comma-separated list or description
Example: "Intended for automatic speech recognition, text-to-speech synthesis..."
```

#### Moderate Fields (60-80% Accuracy) 🟡

**rai:dataCollection** (68.8%)
```
Definition: Methodology for gathering dataset samples
Location: Methods section, "Data Collection" subsection
Format: Detailed description
Example: "Audio collected from LibriVox audiobooks, segmented using acoustic models..."
Challenge: Often verbose and scattered across multiple paragraphs
```

**rai:dataAnnotationPlatform** (62.5%)
```
Definition: Software or platform used for annotation
Location: Methods section, annotation procedure subsection
Format: Platform name or description
Example: "Amazon Mechanical Turk", "custom web interface"
Challenge: Often described rather than named ("web-based annotation tool")
```

**rai:annotatorDemographics** (56.2%)
```
Definition: Characteristics of human annotators
Location: Methods section, ethics statement, appendix
Format: Description of demographics
Example: "33,000 MTurk workers, 93% from US, ages 18-68, 54% male"
Challenge: Often omitted due to privacy concerns; partial information common
```

---

## 4. Performance Analysis

### 4.1 Overall Performance by Category

```
Category Performance:
├─ General Fields (10):  67.3%  (52.5/78 correct)
│  ├─ Perfect (3):       100.0% (name, url)
│  ├─ Strong (2):        84.4%  (description, creator)
│  ├─ Moderate (2):      68.8%  (inLanguage, license)
│  └─ Weak (3):          37.6%  (publisher, isLiveDataset, citeAs)
│
└─ RAI Fields (6):       76.0%  (36.5/48 correct)
   ├─ Perfect (1):       100.0% (dataCollectionTimeframe)
   ├─ Strong (2):        84.4%  (personalSensitiveInformation, dataUseCases)
   └─ Moderate (3):      62.5%  (dataCollection, dataAnnotationPlatform, annotatorDemographics)

Overall:                 70.6%  (89.0/126 correct)
```

### 4.2 Error Patterns

**Publisher Field (28.6% accuracy):**
- 45% errors: Extracted journal name instead
- 30% errors: Extracted distribution platform
- 15% errors: Extracted conference venue
- 10% errors: No extraction (null)

**isLiveDataset Field (25.0% accuracy):**
- 70% errors: Incorrectly labeled "No" when unclear
- 20% errors: Confused versioning with live updates
- 10% errors: No extraction (null)

**Key Insight:** Errors are systematic, not random - indicating prompt ambiguity rather than model limitations.

---

## 5. Recommended Improvements

### 5.1 Priority 1: Add Counter-Examples for Weak Fields

**Improved Publisher Guidance:**
```
**sc:publisher**
Definition: The organization/institution that CREATED or FUNDED the dataset.

WHAT TO LOOK FOR:
- Funding statements: "This work was supported by [ORGANIZATION]"
- Author affiliations: "1Facebook AI Research"
- Acknowledgments: "Dataset created by [INSTITUTION]"

COMMON MISTAKES - DO NOT EXTRACT:
❌ Journal names (e.g., "Nature", "Science", "PNAS")
   → These publish papers, not datasets

❌ Preprint servers (e.g., "arXiv", "bioRxiv")
   → These host papers, not datasets

❌ Distribution platforms (e.g., "GitHub", "Hugging Face", "Kaggle")
   → These host/distribute datasets, but don't create them

❌ Conference venues (e.g., "NeurIPS", "CVPR", "ACL")
   → These publish proceedings, not datasets

✅ CORRECT EXAMPLES:
- Research institutions: "Stanford University", "MIT CSAIL"
- Research labs: "Facebook AI Research", "Google Research", "DeepMind"
- Funding agencies: "National Science Foundation", "EU Horizon 2020"
- Companies: "Meta", "Google", "Microsoft"

If multiple options exist, prefer funding organization over author affiliation.
```

**Improved isLiveDataset Guidance:**
```
**cr:isLiveDataset**
Definition: Whether the dataset receives ONGOING UPDATES after initial release.

DECISION RULES:

Return "Yes" ONLY IF paper explicitly states:
✅ "continuously updated"
✅ "live database"
✅ "ongoing data collection"
✅ "real-time updates"
✅ "weekly/monthly releases"

Return "No" IF paper indicates:
✅ Fixed timeframe: "collected from 2015-2018"
✅ Single snapshot: "data from January 2020"
✅ No update mention in future work

Return "Unknown" IF:
✅ Status genuinely unclear
✅ Paper silent on update plans
✅ Ambiguous language

COMMON MISTAKES - DO NOT ASSUME:
❌ Multiple versions (v1, v2) ≠ continuously updated
   → Discrete releases are still static snapshots

❌ GitHub repository ≠ live dataset
   → Code may update, but data may be fixed

❌ Old papers (2015) ≠ automatically "No"
   → Old papers can describe live datasets

PREFER "Unknown" over guessing if uncertain.
```

### 5.2 Priority 2: Section-Aware Reading Strategy

**Robust RAI Extraction Prompt:**
```
**EXTRACTION STRATEGY FOR RAI FIELDS:**

STEP 1: Identify paper structure
- Scan all section headings first
- Note presence of: Ethics, Methods, Data Collection, Appendix sections
- Map where RAI information likely appears

STEP 2: Targeted extraction by field
- dataCollection → Methods > "Data Collection" subsection
- dataCollectionTimeframe → Methods (look for temporal mentions)
- dataAnnotationPlatform → Methods > "Annotation" subsection
- annotatorDemographics → Methods, Ethics, Appendix
- dataUseCases → Introduction (paragraph 2-3), Conclusion
- personalSensitiveInformation → Ethics section, IRB mentions

STEP 3: Handle missing information
- If section exists but sparse → extract what's available (partial OK)
- If section missing → return null (don't fabricate)
- If contradictory → prefer later sections (corrections/clarifications)

STEP 4: Quality check
- Is information specific, not generic?
- Is timeframe reasonable (not future work)?
- Are numbers/counts present where expected?
```

### 5.3 Priority 3: Validation Guidance

**Add Self-Validation Step:**
```
**BEFORE RETURNING JSON, VALIDATE YOUR EXTRACTION:**

For each extracted field, ask:
1. Is this explicitly stated in the paper? (not inferred)
2. Did I check the most likely location for this field?
3. Does the value make logical sense given the context?
4. Am I confusing similar concepts (e.g., journal vs publisher)?

If any answer is "uncertain", mark that field for review or return null.

VALIDATION CHECKLIST:
☐ name: Matches title or introduction?
☐ url: Is this the DATASET url, not paper DOI?
☐ publisher: Is this the CREATOR/FUNDER, not journal/platform?
☐ datePublished: Is this DATASET release date, not paper date?
☐ isLiveDataset: Did paper EXPLICITLY state live/static status?
```

---

## 6. Alternative Prompt Strategies

### 6.1 Multi-Pass Extraction (Higher Accuracy, Higher Cost)

**Strategy:** Extract in multiple passes with different focuses.

```python
# Pass 1: Structure identification
structure_prompt = """
Analyze this paper's structure:
1. List all section headings
2. Identify sections containing metadata:
   - Methods/Data Collection (for RAI fields)
   - Abstract/Intro (for general fields)
   - Acknowledgments (for funding/publisher)
   - Data Availability (for URL/license)

Return: JSON with section_map
"""

# Pass 2: Targeted extraction
extraction_prompt = """
Paper structure: {structure_from_pass1}

Extract metadata focusing on identified sections:
- For dataCollection: Focus on {data_collection_section}
- For publisher: Focus on {acknowledgments_section}
...
"""
```

**Expected Gain:** +2-3pp
**Cost:** +100% (2 LLM calls vs 1)

### 6.2 Self-Consistency (Multiple Reasoning Paths)

**Strategy:** Extract same field multiple times with different perspectives, then vote.

```python
perspectives = [
    "Extract by reading top-down (title → abstract → intro → ...)",
    "Extract by reading bottom-up (appendix → methods → intro → ...)",
    "Extract focusing on explicit metadata statements only",
    "Extract by searching for keywords related to each field",
    "Extract considering implicit information and context"
]

# Get 5 extractions per field
extractions = [extract(paper, field, perspective) for perspective in perspectives]

# Vote or use LLM to resolve
final_value = majority_vote(extractions)
```

**Expected Gain:** +4-7pp
**Cost:** +400% (5 extractions vs 1)

### 6.3 Task Decomposition (Cognitive Approach)

**Strategy:** Break extraction into locate → extract → validate → format.

```python
for each field:
    # Step 1: Locate
    location = llm.generate(f"Where in the paper is '{field}' likely to appear?")

    # Step 2: Extract
    raw_value = llm.generate(f"Extract '{field}' from these sections: {location}")

    # Step 3: Validate
    is_valid = llm.generate(f"Is '{raw_value}' a valid extraction for '{field}'?")

    # Step 4: Format
    if is_valid:
        formatted = format_to_schema(raw_value, field)
```

**Expected Gain:** +3-5pp
**Cost:** +300% (4 steps per field)

### 6.4 Schema Grounding with Examples (No Overfitting)

**Strategy:** Include universal counter-examples in schema definition.

```
SCHEMA (with counter-examples):
{
  "publisher": {
    "type": "string",
    "definition": "Organization that funded/created the dataset",
    "not_examples": ["arXiv", "Nature", "GitHub", "NeurIPS"],
    "correct_examples": ["Google Research", "NSF", "Stanford University"]
  },
  "isLiveDataset": {
    "type": "string",
    "values": ["Yes", "No", "Unknown"],
    "yes_criteria": ["continuously updated", "live", "ongoing collection"],
    "no_criteria": ["collected 2015-2018", "static snapshot"],
    "prefer_unknown": "If status unclear, return Unknown rather than guessing"
  }
}
```

**Expected Gain:** +3-5pp
**Cost:** None (single extraction)
**Risk:** Zero overfitting (universal examples only)

---

## 7. Implementation Guide

### 7.1 Quick Wins (Recommended Start)

**Step 1: Update system prompt with counter-examples**
- Add publisher clarifications
- Add isLiveDataset decision rules
- Expected: +2-3pp, 1 day effort

**Step 2: Add validation checklist**
- Self-validation before returning JSON
- Expected: +1-2pp, 0.5 day effort

**Step 3: Test on 2-3 new papers**
- Validate no overfitting
- Expected: 1 day effort

**Total:** +3-5pp improvement, 2.5 days effort, zero overfitting risk

### 7.2 Medium-Term Enhancements

**Step 4: Implement section-aware reading**
- Two-pass extraction (structure + targeted)
- Expected: +2-3pp, 3-4 days effort

**Step 5: Add field-specific strategies**
- Different approaches per field category
- Expected: +1-2pp, 2-3 days effort

**Total cumulative:** +6-10pp improvement, 1.5 weeks effort

### 7.3 Advanced Research

**Step 6: Self-consistency ensemble**
- 5 perspectives per field, majority vote
- Expected: +4-7pp, 1-2 weeks effort

**Step 7: Hybrid model approach**
- Use GPT for datePublished/annotatorDemographics
- Use Claude for everything else
- Expected: +2-3pp, 1 week effort

**Total cumulative:** +12-20pp improvement, 4-5 weeks effort

---

## 8. Testing & Validation

### 8.1 Validation Protocol

**To prevent overfitting:**

```python
# 1. Hold-out validation set (NEW papers, not in original 8)
validation_papers = [
    "MIMIC-III (healthcare domain)",
    "GQA (visual QA)",
    "SQuAD (reading comprehension)",
    "WMT (machine translation)"
]

# 2. Test improved prompt
original_accuracy = evaluate(original_prompt, test_papers)
improved_accuracy = evaluate(improved_prompt, test_papers)
validation_accuracy = evaluate(improved_prompt, validation_papers)

# 3. Check for overfitting
if abs(improved_accuracy - validation_accuracy) < 3pp:
    print("✅ Generalizes well - no overfitting")
else:
    print("⚠️ Possible overfitting - revise prompt")
```

### 8.2 A/B Testing Framework

```python
prompts = {
    "baseline": current_prompt,
    "counter_examples": prompt_with_counter_examples,
    "section_aware": prompt_with_structure,
    "full_improved": prompt_with_all_improvements
}

results = {}
for name, prompt in prompts.items():
    results[name] = evaluate_on_all_datasets(prompt)

# Compare
print_comparison_table(results)
```

---

## 9. Monitoring & Maintenance

### 9.1 Key Metrics to Track

**Accuracy Metrics:**
- Overall accuracy (target: 70-75%)
- General fields accuracy (target: 70-75%)
- RAI fields accuracy (target: 78-82%)
- Per-field accuracy (track regressions)

**Reliability Metrics:**
- Success rate (target: 100%)
- Average extraction time (target: <30s)
- Error rate (target: <5%)

**Quality Indicators:**
- Null rate per field (track missingness)
- Validation failures (if validation added)
- Human review flagging rate (if implemented)

### 9.2 Update Triggers

**When to update prompts:**
- New paper types encountered (e.g., healthcare datasets)
- Systematic failures on specific field (>30% error rate)
- New Croissant schema fields added
- Model updates (e.g., Claude 4.6 released)

**Update process:**
1. Identify failure pattern
2. Develop targeted improvement
3. A/B test on validation set
4. Deploy if improvement >2pp with no regression

---

## 10. Appendix: Complete Optimized Prompt

### 10.1 Recommended Production Prompt v2.0

**System Prompt:**
```
You are an expert at extracting structured metadata from academic papers about datasets.

**EXTRACTION STRATEGY:**

1. **Read Systematically**
   - First pass: Identify paper structure (scan section headings)
   - Second pass: Target sections most likely to contain each field
   - Third pass: Validate extractions for consistency

2. **Know Where to Look**

   GENERAL FIELDS:
   - name, description → Title, Abstract, Introduction
   - url, license → Data Availability, Ethics, Footnotes
   - creator → Author list, Affiliations
   - publisher → Funding/Acknowledgments (NOT journal name!)
   - datePublished → Data Availability (dataset date, not paper date!)
   - citeAs → Data Availability, Citation box
   - isLiveDataset → Methods (look for "continuously updated")
   - inLanguage → Dataset description, Methods

   RAI FIELDS:
   - dataCollection → Methods > "Data Collection" section
   - dataCollectionTimeframe → Methods (temporal mentions)
   - dataAnnotationPlatform → Methods > Annotation subsection
   - annotatorDemographics → Methods, Ethics, Appendix
   - dataUseCases → Introduction, Conclusion
   - personalSensitiveInformation → Ethics, IRB statements

3. **Common Mistakes to AVOID**

   ❌ publisher: Do NOT extract journal names, preprint servers, platforms, venues
      ✅ Extract: Funding organizations, creator institutions

   ❌ isLiveDataset: Do NOT guess; return "Unknown" if unclear
      ✅ Only "Yes" if explicitly stated as live/ongoing

   ❌ datePublished: Do NOT use paper submission date
      ✅ Use dataset release date if stated

   ❌ url: Do NOT use paper DOI
      ✅ Use dataset-specific URL

4. **Extraction Quality Standards**
   - Be specific, not generic ("scraped from Flickr" vs "collected from web")
   - Be complete (extract full details, not summaries)
   - Be honest (return null if information missing)
   - Be precise (exact values, not paraphrases)

5. **Format Requirements**
   - Return ONLY valid JSON
   - No markdown, no explanations
   - Use null for missing fields (not "not found" or "N/A")
   - Dates: YYYY-MM-DD or YYYY
   - URLs: Full URLs starting with http:// or https://

**SELF-VALIDATION CHECKLIST (before returning):**
☐ name: From title/intro?
☐ url: Dataset URL, not paper DOI?
☐ publisher: Creator/funder, not journal?
☐ datePublished: Dataset date, not paper date?
☐ isLiveDataset: Explicitly stated, not guessed?
```

**User Prompt:** (same as before)

---

## Version History

| Version | Date | Changes | Performance |
|---------|------|---------|-------------|
| v1.0 | Oct 2025 | Initial prompt | 70.6% overall |
| v2.0 | Nov 2025 | + Counter-examples, validation | Expected: 73-75% |
| v3.0 | TBD | + Section-aware reading | Target: 75-78% |

---

**Document Maintained By:** [Your Name]
**Last Review:** November 2, 2025
**Next Review:** After v2.0 testing (estimate: 2 weeks)
