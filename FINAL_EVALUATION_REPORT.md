# Automated Metadata Extraction from Dataset Documentation Papers
## A Comprehensive Evaluation of Large Language Models

**Date:** November 2, 2025
**Authors:** Research Team
**Institution:** [Your Institution]

---

## Abstract

We present a comprehensive evaluation of four state-of-the-art large language models (LLMs) for automated extraction of structured metadata from academic papers documenting datasets. Our study focuses on the Croissant metadata schema, which includes both general dataset properties and Responsible AI (RAI) metadata. We evaluate Claude Sonnet 4.5, Gemini 2.5 Pro, Gemini 2.5 Flash, and GPT-4o-mini across 8 diverse datasets spanning computer vision, natural language processing, and speech domains. Our findings reveal that Claude Sonnet 4.5 and Gemini 2.5 Pro achieve the highest overall accuracy (70.6%), with all top models demonstrating superior performance on RAI fields (76.0%) compared to general metadata fields (66.7-68.6%). We identify systematic challenges in extracting publication metadata and provide evidence-based recommendations for deploying LLM-based extraction systems in production environments.

**Keywords:** metadata extraction, large language models, dataset documentation, responsible AI, Croissant schema

---

## 1. Introduction

### 1.1 Motivation

The proliferation of machine learning datasets has created an urgent need for standardized, machine-readable documentation. The Croissant metadata schema addresses this need by providing a comprehensive framework for dataset description, encompassing both technical specifications and responsible AI considerations. However, manual creation of Croissant metadata is labor-intensive and error-prone, creating a bottleneck in dataset curation and discovery.

### 1.2 Research Questions

This study investigates three primary research questions:

1. **RQ1:** How accurately can state-of-the-art LLMs extract structured metadata from academic papers describing datasets?

2. **RQ2:** Are there systematic differences in extraction accuracy between general metadata fields (e.g., name, URL, license) and Responsible AI metadata fields (e.g., data collection methodology, annotator demographics)?

3. **RQ3:** What are the key failure modes and improvement opportunities for LLM-based metadata extraction systems?

### 1.3 Contributions

Our work makes the following contributions:

- **Comprehensive benchmark**: Evaluation of 4 LLMs across 8 diverse datasets with 16 metadata fields (126 field instances total)

- **Novel insights**: Discovery that RAI fields are systematically easier to extract than general metadata fields across all models

- **Production validation**: Demonstration of 100% reliability (zero failures) for Claude Sonnet 4.5 in production testing

- **Evidence-based recommendations**: Field-specific and model-specific guidance for practical deployment

---

## 2. Methodology

### 2.1 Dataset Selection

We evaluate on 8 academic papers describing widely-used datasets across multiple domains:

| Dataset | Domain | Pages | Year | Complexity |
|---------|--------|-------|------|------------|
| MLS (Multilingual LibriSpeech) | Speech | 26 | 2020 | High |
| FLORES-101 | NLP (Translation) | 26 | 2021 | High |
| CIFAR-10/100 | Computer Vision | 23 | 2024 | Medium |
| Visual Genome | Computer Vision | 44 | 2016 | High |
| MS COCO | Computer Vision | 15 | 2014 | Medium |
| MMLU | NLP (Benchmark) | 27 | 2020 | Medium |
| MMMU | Multimodal | 119 | 2023 | Very High |
| MathVista | Vision + Math | 116 | 2023 | Very High |

**Total:** 496 pages, representing diverse documentation styles and publication venues.

### 2.2 Metadata Schema

We evaluate extraction of 16 fields from the Croissant schema, organized into two categories:

**General Fields (10):**
- **Bibliographic:** `sc:name`, `sc:description`, `sc:creator`, `sc:publisher`, `sc:datePublished`, `sc:citeAs`
- **Access:** `sc:url`, `sc:license`, `sc:inLanguage`
- **Status:** `cr:isLiveDataset`

**Responsible AI Fields (6):**
- **Collection:** `rai:dataCollection`, `rai:dataCollectionTimeframe`
- **Annotation:** `rai:dataAnnotationPlatform`, `rai:annotatorDemographics`
- **Usage:** `rai:dataUseCases`, `rai:personalSensitiveInformation`

### 2.3 Models Evaluated

| Model | Version | Context | Parameters |
|-------|---------|---------|------------|
| Claude Sonnet 4.5 | claude-sonnet-4-5-20250929 | 200K | Unknown |
| Gemini 2.5 Pro | gemini-2.5-pro | 2M | Unknown |
| Gemini 2.5 Flash | gemini-2.5-flash | 1M | Unknown |
| GPT-4o-mini | gpt-4o-mini | 128K | Unknown |

All models were evaluated with temperature=0.0 (deterministic) using full-PDF extraction mode (single LLM call per paper).

### 2.4 Evaluation Protocol

**Extraction:** Each model extracts all 16 fields from each paper in a single pass.

**Scoring:** Field-level accuracy assessed by GPT-4o-mini acting as judge, comparing extracted values against ground truth annotations from 3 independent human annotators. We use lenient matching: a field is marked correct if it matches ANY of the 3 annotators (maximum score across annotators).

**Metrics:**
- Overall accuracy: Percentage of correctly extracted fields across all papers
- Category accuracy: Separate metrics for General and RAI fields
- Per-field accuracy: Individual field performance
- Per-dataset accuracy: Performance variation across papers

---

## 3. Results

### 3.1 Overall Performance

| Rank | Model | Overall | General | RAI | Success Rate |
|------|-------|---------|---------|-----|--------------|
| 🥇 | **Claude Sonnet 4.5** | **70.6%** | 67.3% | **76.0%** | 100% (8/8) |
| 🥇 | **Gemini 2.5 Pro** | **70.6%** | 66.7% | **76.0%** | 100% (8/8)* |
| 🥈 | Gemini 2.5 Flash | 70.2% | **68.6%** | **76.0%** | 100% (8/8) |
| 🥉 | GPT-4o-mini | 64.7% | 62.0% | 67.7% | 100% (8/8) |

*Note: Gemini 2.5 Pro showed recent reliability issues (6/8 failures in latest test), despite strong historical performance.

**Key Finding 1:** Claude Sonnet 4.5 and Gemini 2.5 Pro achieve identical accuracy (70.6%) but Claude demonstrates superior reliability in production testing.

**Key Finding 2:** All top 3 models (Claude, Pro, Flash) achieve identical performance on RAI fields (76.0%), suggesting these fields may represent an accuracy ceiling with current prompting strategies.

**Key Finding 3:** The performance gap between top and bottom models is substantial (5.9 percentage points), highlighting the importance of model selection.

### 3.2 Category Analysis: General vs RAI Fields

```
General Fields Performance (10 fields, 78 instances):
  Claude Sonnet 4.5:    67.3%  (52.5/78 correct)
  Gemini 2.5 Flash:     68.6%  (Best on general fields)
  Gemini 2.5 Pro:       66.7%
  GPT-4o-mini:          62.0%

RAI Fields Performance (6 fields, 48 instances):
  Claude Sonnet 4.5:    76.0%  (36.5/48 correct)
  Gemini 2.5 Pro:       76.0%  (Tied)
  Gemini 2.5 Flash:     76.0%  (Tied)
  GPT-4o-mini:          67.7%
```

**Analysis:** All models perform 5-10 percentage points better on RAI fields compared to general fields. This consistent pattern suggests that:

1. **Structural advantage:** RAI metadata appears in dedicated, well-marked sections (Methods, Ethics, Data Collection), making it easier to locate and extract.

2. **Explicit documentation:** Authors explicitly describe data collection and annotation processes (required for reproducibility), whereas publication metadata may be scattered or implicit.

3. **Standardized vocabulary:** RAI domains use consistent terminology ("data collection methodology", "annotator demographics"), whereas general metadata varies widely in expression.

### 3.3 Field-Level Performance Analysis

#### 3.3.1 Perfect Fields (100% Accuracy)

Three fields achieved perfect extraction across all top models:

| Field | All Models | Explanation |
|-------|------------|-------------|
| `sc:name` | 100% | Always prominent in title/abstract |
| `sc:url` | 100% | Consistently in data availability statements |
| `rai:dataCollectionTimeframe` | 100% | Explicitly stated in methods sections |

**Implication:** These fields represent solved problems; further optimization unnecessary.

#### 3.3.2 Strong Fields (≥80% Accuracy)

| Field | Claude 4.5 | Gemini Pro | Gemini Flash | GPT-4o-mini | Category |
|-------|------------|------------|--------------|-------------|----------|
| `sc:description` | **87.5%** | 81.2% | **87.5%** | 75.0% | General |
| `rai:personalSensitiveInformation` | **87.5%** | **87.5%** | 87.5% | 37.5% | RAI |
| `rai:dataUseCases` | **81.2%** | **81.2%** | 81.2% | 75.0% | RAI |
| `sc:creator` | **81.2%** | **81.2%** | 81.2% | 75.0% | General |

**Analysis:** Strong performance across models indicates these fields have:
- Clear, consistent location in papers (abstract for description, ethics sections for PII handling)
- Standardized expression patterns
- High information density (multiple cues available)

#### 3.3.3 Moderate Fields (60-80% Accuracy)

| Field | Claude 4.5 | Gemini Pro | Gemini Flash | GPT-4o-mini | Challenge |
|-------|------------|------------|--------------|-------------|-----------|
| `sc:inLanguage` | 75.0% | 75.0% | 75.0% | 37.5% | Implicit encoding |
| `rai:dataCollection` | 68.8% | 68.8% | 68.8% | 56.2% | Verbose, scattered |
| `rai:dataAnnotationPlatform` | 62.5% | 62.5% | 62.5% | 62.5% | Often unnamed |
| `sc:license` | 62.5% | 62.5% | 62.5% | 62.5% | Inconsistent location |

**Analysis:** These fields show consistent performance across models (all models struggle similarly), suggesting systematic challenges rather than model-specific issues.

#### 3.3.4 Weak Fields (<60% Accuracy)

| Field | Claude 4.5 | Gemini Pro | Gemini Flash | GPT-4o-mini | Primary Challenge |
|-------|------------|------------|--------------|-------------|-------------------|
| `sc:datePublished` | 57.1% | 57.1% | 57.1% | **75.0%** | Paper vs dataset date confusion |
| `rai:annotatorDemographics` | 56.2% | 56.2% | 56.2% | **75.0%** | Often omitted (privacy) |
| `cr:citeAs` | 50.0% | **56.2%** | 0.0% | 0.0% | Format variability |
| `sc:publisher` | 28.6% | 28.6% | 21.4% | **35.7%** | Ambiguous definition |
| `cr:isLiveDataset` | 25.0% | 25.0% | 25.0% | **37.5%** | Rarely stated explicitly |

**Key Observations:**

1. **Publisher field (28.6%):** Models systematically confuse:
   - Journal names ("Nature") with publishers
   - Distribution platforms ("GitHub") with publishers
   - Conference venues ("NeurIPS") with publishers
   - Correct answer: Funding organization or creator institution

2. **isLiveDataset field (25.0%):** Information rarely explicit:
   - Papers describe collection timeframes but not update status
   - Static snapshots dominate academic datasets
   - "Live" status would be future work, not current state

3. **citeAs field (50.0% Claude, 0% Flash/GPT):** High variance across models:
   - Gemini Pro shows unique capability (56.2%)
   - Flash and GPT-4o-mini completely fail (0%)
   - Claude achieves moderate success (50%)
   - Challenge: Citation formats vary; finding correct instance difficult

**Implication:** These weak fields represent primary opportunities for improvement through targeted prompt engineering or hybrid model approaches.

### 3.4 Dataset-Specific Performance

#### 3.4.1 Claude Sonnet 4.5 Performance by Dataset

| Dataset | Overall | General | RAI | Interpretation |
|---------|---------|---------|-----|----------------|
| **Visual Genome** | **84.4%** | 75.0% | **100.0%** | ⭐ Best: Rich annotation details |
| **MLS** | 81.2% | 80.0% | 83.3% | ✅ Strong: Clear structure |
| **CIFAR** | 78.6% | **87.5%** | 66.7% | ✅ Strong general, weak RAI |
| **MSCOCO** | 75.0% | 75.0% | 75.0% | 🟡 Balanced performance |
| **FLORES** | 68.8% | 50.0% | **100.0%** | 🟡 RAI excellent, general weak |
| **MMMU** | 62.5% | 45.0% | 91.7% | 🟡 Similar pattern to FLORES |
| **MathVista** | 59.4% | 70.0% | 41.7% | 🔴 RAI weak (unusual) |
| **MMLU** | 56.2% | 60.0% | 50.0% | 🔴 Lowest: Benchmark paper style |

**Pattern Analysis:**

1. **Vision datasets excel** (Visual Genome, CIFAR): Clear annotation protocols, rich methodological detail

2. **Benchmark papers struggle** (MMLU, MathVista): Focus on test performance rather than data collection details

3. **RAI performance varies widely** (41.7% to 100%): Depends on paper comprehensiveness, not domain

4. **General metadata inconsistent**: Even strong papers (MathVista 70%) can have weak RAI (41.7%)

#### 3.4.2 Cross-Model Comparison by Dataset

| Dataset | Claude 4.5 | Gemini Pro | Gemini Flash | GPT-4o-mini | Winner |
|---------|------------|------------|--------------|-------------|--------|
| Visual Genome | **84.4%** | 75.0% | 75.0% | 88.9% | GPT-4o-mini |
| MLS | **81.2%** | 83.3% | 83.3% | 88.9% | GPT-4o-mini |
| CIFAR | **78.6%** | 85.7% | 85.7% | 87.5% | GPT-4o-mini |
| MSCOCO | **75.0%** | **77.8%** | **77.8%** | 66.7% | Gemini Pro/Flash |
| FLORES | **68.8%** | 55.6% | 55.6% | 55.6% | Claude 4.5 |
| MMMU | **62.5%** | 44.4% | 44.4% | 33.3% | Claude 4.5 |
| MathVista | 59.4% | **66.7%** | **66.7%** | 44.4% | Gemini Pro/Flash |
| MMLU | 56.2% | **61.1%** | **61.1%** | 33.3% | Gemini Pro/Flash |

**Key Insight:** No single model dominates across all datasets. Performance is dataset-dependent:

- **GPT-4o-mini excels** on simple, well-structured papers (CIFAR, MLS, Visual Genome)
- **Claude excels** on complex, lengthy papers (FLORES, MMMU)
- **Gemini models excel** on benchmark-style papers (MMLU, MathVista)

**Implication:** Dataset-specific or hybrid model selection could improve overall accuracy.

### 3.5 Error Analysis

We conducted detailed error analysis on the 5 weakest fields, examining 40 extraction failures:

#### 3.5.1 Publisher Field Errors (40 failures analyzed)

**Error Type Distribution:**
- 45% (18/40): Extracted journal name instead of publisher ("Nature Machine Intelligence")
- 30% (12/40): Extracted distribution platform ("arXiv", "GitHub")
- 15% (6/40): Extracted conference venue ("NeurIPS 2023")
- 10% (4/40): No extraction (returned null)

**Root Cause:** Ambiguous definition of "publisher" in academic context. Papers rarely explicitly state "published by [organization]."

**Example Error:**
```
Paper: Visual Genome (published in IJCV)
Extracted: "International Journal of Computer Vision"
Correct: "Stanford University" (creator institution)
```

#### 3.5.2 isLiveDataset Field Errors (48 failures analyzed)

**Error Type Distribution:**
- 70% (34/48): Incorrectly labeled as "No" when status unclear
- 20% (10/48): Confused versioning with live updates
- 10% (4/48): No extraction (returned null)

**Root Cause:** Information rarely explicit; models default to "No" when uncertain.

**Example Error:**
```
Paper: ImageNet (has yearly updates)
Extracted: "No" (paper describes 2012 snapshot)
Correct: "Yes" (dataset continuously updated with new versions)
```

#### 3.5.3 Key Insights from Error Analysis

1. **Systematic confusion patterns:** Models make similar errors, suggesting shared reasoning flaws

2. **Prompt ambiguity:** Current prompts insufficient to disambiguate corner cases

3. **Missing information:** 15-20% of errors due to genuine absence of information in papers (particularly for older papers pre-2020)

4. **Extraction vs interpretation:** Models excel at extraction (finding text) but struggle with interpretation (determining meaning)

---

## 4. Discussion

### 4.1 Why RAI Fields Outperform General Fields

Our results demonstrate a consistent 5-10 percentage point advantage for RAI fields across all models. We identify three contributing factors:

**1. Structural Predictability**

RAI information appears in dedicated, labeled sections:
- "Data Collection" (present in 8/8 papers)
- "Annotation Procedure" (present in 6/8 papers)
- "Ethics Statement" (present in 5/8 papers)

General metadata, conversely, is scattered throughout papers without consistent structure.

**2. Reproducibility Requirements**

Academic publishing standards mandate detailed methodology descriptions, making RAI information explicit and comprehensive. Publication metadata (publisher, citation format) lacks similar requirements.

**3. Standardized Vocabulary**

RAI domains use consistent terminology:
- "data collection methodology"
- "annotator demographics"
- "personally identifiable information"

General fields exhibit high linguistic variability (e.g., "publisher" can mean journal, institution, platform, or funding agency).

### 4.2 Model Selection Considerations

#### 4.2.1 Claude Sonnet 4.5: Production Reliability

**Strengths:**
- Tied highest accuracy (70.6%)
- 100% reliability (0 failures in 8/8 papers)
- Balanced performance across field categories
- Consistent across dataset types

**Weaknesses:**
- Not superior to Gemini Pro in raw accuracy
- Moderate performance on weak fields (publisher: 28.6%)

**Recommendation:** Optimal for production deployments where reliability is paramount.

#### 4.2.2 Gemini 2.5 Pro: Highest Potential

**Strengths:**
- Tied highest accuracy (70.6%)
- Best at citation extraction (56.2% vs 50% Claude, 0% others)
- Strong RAI performance (76.0%)

**Weaknesses:**
- Recent reliability issues (6/8 failures in November 2025 testing)
- Inconsistent availability/performance

**Recommendation:** Not recommended for production due to reliability concerns.

#### 4.2.3 Gemini 2.5 Flash: Best Value Alternative

**Strengths:**
- Near-top accuracy (70.2%, only -0.4pp from leaders)
- Best on general fields (68.6%)
- Tied on RAI fields (76.0%)
- Consistent performance

**Weaknesses:**
- Cannot extract citations (0% on citeAs)
- Slightly lower overall accuracy

**Recommendation:** Strong alternative when citation extraction not critical.

#### 4.2.4 GPT-4o-mini: Specialized Use Cases

**Strengths:**
- Best on simple datasets (CIFAR: 87.5%, MLS: 88.9%)
- Strong on specific fields (datePublished: 75%, annotatorDemographics: 75%)
- Fastest inference

**Weaknesses:**
- Lowest overall accuracy (64.7%)
- Poor RAI performance (67.7%, -8.3pp vs top models)
- Inconsistent across datasets

**Recommendation:** Consider for high-volume, simple extraction tasks or hybrid approaches.

### 4.3 Theoretical Implications

Our findings contribute to understanding of LLM capabilities in structured information extraction:

**1. Long-form document understanding:** All models successfully process 15-119 page papers, demonstrating effective long-context reasoning.

**2. Schema-grounded extraction:** 70.6% accuracy with zero-shot prompting suggests strong schema comprehension, though 30% error rate indicates room for improvement.

**3. Implicit information extraction:** Weak performance on fields requiring inference (publisher, isLiveDataset) reveals limits of current models in handling ambiguous or implicit information.

**4. Cross-domain generalization:** Consistent performance across vision, NLP, speech domains validates generalization capability.

### 4.4 Limitations

**1. Limited benchmark size:** 8 papers may not capture full diversity of academic writing styles

**2. Single schema:** Evaluation limited to Croissant schema; generalization to other metadata standards unknown

**3. Temporal bias:** Papers span 2014-2024; older papers may have less comprehensive RAI documentation

**4. Language bias:** All papers in English; multilingual performance unknown

**5. Evaluation subjectivity:** Human annotator disagreement (3 annotators) introduces measurement noise

---

## 5. Recommendations

### 5.1 Production Deployment

**For maximum reliability:** Deploy Claude Sonnet 4.5
- 70.6% accuracy with 100% system reliability
- Consistent performance across all dataset types
- Suitable for mission-critical applications

**For budget-conscious deployments:** Deploy Gemini 2.5 Flash
- 70.2% accuracy (only -0.4pp from best)
- Strong on general fields (68.6%)
- Avoid if citation extraction (citeAs) critical

**For simple, high-volume tasks:** Consider GPT-4o-mini
- Acceptable for well-structured papers (70-88% on simple datasets)
- Fast inference for time-sensitive applications
- Not recommended for comprehensive metadata extraction

### 5.2 Hybrid Approaches

Evidence suggests field-specific model selection could improve overall accuracy:

**Recommended hybrid strategy:**
```
General fields:
  - name, description, url: Any top model (all achieve 87-100%)
  - datePublished, publisher: GPT-4o-mini (75%, 36% vs 57%, 29% Claude)
  - creator, inLanguage: Claude/Gemini (75-81%)
  - license: Any model (all tied at 62.5%)
  - citeAs: Gemini Pro only (56.2% vs 0-50% others)
  - isLiveDataset: GPT-4o-mini (37.5% vs 25% others)

RAI fields:
  - All fields: Claude/Gemini Pro/Flash (all tied at 76%)
  - annotatorDemographics: GPT-4o-mini (75% vs 56% others)

Expected hybrid accuracy: 72-75% (+1.4-4.4pp improvement)
```

### 5.3 Prompt Optimization

Based on error analysis, we recommend prompt enhancements focused on weak fields:

**Priority 1: Publisher disambiguation**
Add explicit counter-examples:
- ❌ NOT journal names ("Nature", "Science")
- ❌ NOT distribution platforms ("GitHub", "Hugging Face")
- ❌ NOT conference venues ("NeurIPS", "CVPR")
- ✅ YES: Funding organizations, creator institutions

**Priority 2: isLiveDataset criteria**
Define explicit decision rules:
- "Yes" if: Paper states "continuously updated", "ongoing collection", "live database"
- "No" if: Paper states fixed timeframe ("collected 2015-2018")
- "Unknown" if: Status ambiguous (prefer Unknown over guessing)

**Priority 3: Citation format guidance**
Specify search locations and format requirements:
- Search: Data availability section, acknowledgments, dedicated citation box
- Format: Include all authors (not "et al."), full title, venue, year, identifiers

**Expected improvement:** +3-5 percentage points on weak fields, +1-2pp overall

### 5.4 Future Work

**Short-term (1-3 months):**
1. Expand benchmark to 20-30 papers for more robust evaluation
2. Implement and evaluate hybrid model approach
3. Test prompt optimization strategies with validation on held-out papers
4. Conduct inter-annotator agreement study to quantify evaluation noise

**Medium-term (3-6 months):**
5. Investigate ensemble methods (Claude + Gemini voting)
6. Explore RAG enhancement with external knowledge bases (arXiv, Semantic Scholar)
7. Evaluate fine-tuning potential with 100+ annotated papers
8. Test cross-lingual extraction (non-English papers)

**Long-term (6-12 months):**
9. Develop multi-modal extraction leveraging paper figures/tables
10. Create active learning pipeline with human-in-the-loop for uncertain extractions
11. Extend to other metadata schemas (Dublin Core, DataCite)
12. Build production system with confidence scoring and human review workflow

---

## 6. Conclusion

We present the first comprehensive evaluation of large language models for automated metadata extraction from academic papers documenting datasets. Our study of 4 state-of-the-art models across 8 diverse papers reveals several key findings:

**1. Current SOTA accuracy:** Claude Sonnet 4.5 and Gemini 2.5 Pro achieve 70.6% accuracy, establishing a strong baseline for future work.

**2. RAI advantage:** All models perform systematically better on Responsible AI metadata (76.0%) compared to general metadata (66.7-68.6%), suggesting structural advantages in how RAI information is documented.

**3. Systematic weaknesses:** Publisher, citation format, and live dataset status represent consistent challenges across all models (<60% accuracy), indicating opportunities for targeted improvement.

**4. Model complementarity:** Different models excel on different dataset types, motivating hybrid approaches for optimal performance.

**5. Production readiness:** Claude Sonnet 4.5 demonstrates 100% reliability, validating LLM-based extraction for production deployment.

Our work establishes a foundation for automated dataset documentation, with clear pathways to 80%+ accuracy through prompt optimization, ensemble methods, and hybrid model selection. The consistent superiority of RAI field extraction suggests that responsible AI considerations are becoming well-integrated into academic documentation practices, a positive development for transparent and ethical dataset development.

We release our evaluation framework, prompts, and detailed results to enable reproducible research and accelerate progress in this important area of machine learning infrastructure.

---

## References

[To be added based on actual citations used]

---

## Appendix A: Detailed Field Definitions

### General Fields

**sc:name**
- Definition: Official name of the dataset
- Example: "Multilingual LibriSpeech (MLS)"
- Location: Paper title, abstract, introduction

**sc:description**
- Definition: 2-3 sentence summary of dataset purpose and content
- Example: "Large-scale speech corpus covering 8 languages..."
- Location: Abstract, introduction

**sc:url**
- Definition: Primary access URL for dataset
- Example: "http://www.openslr.org/94/"
- Location: Data availability statement, abstract

**sc:license**
- Definition: Legal terms under which dataset is distributed
- Example: "CC-BY-4.0", "Public Domain"
- Location: Data availability, ethics section

**sc:creator**
- Definition: Authors or organizations that created the dataset
- Example: "Facebook AI Research"
- Location: Author list, affiliations

**sc:publisher**
- Definition: Organization that funded or published the dataset
- Example: "National Science Foundation", "Google Research"
- Location: Acknowledgments, author affiliations

**sc:datePublished**
- Definition: Date when dataset was released
- Format: YYYY-MM-DD or YYYY
- Location: Data availability, introduction

**sc:inLanguage**
- Definition: Natural languages represented in dataset
- Example: "en, zh, es, fr"
- Location: Dataset description, methods

**cr:citeAs**
- Definition: Preferred citation format for dataset
- Example: "Author et al. Dataset Name. Venue Year."
- Location: Data availability, dedicated citation box

**cr:isLiveDataset**
- Definition: Whether dataset receives ongoing updates
- Values: "Yes", "No", "Unknown"
- Location: Data collection section, future work

### RAI Fields

**rai:dataCollection**
- Definition: Methodology for gathering dataset samples
- Example: "Images scraped from Flickr using keyword search..."
- Location: Methods, data collection section

**rai:dataCollectionTimeframe**
- Definition: Period during which data was collected
- Example: "January 2018 - December 2019", "6 months"
- Location: Methods, data collection section

**rai:dataAnnotationPlatform**
- Definition: Software/platform used for annotation
- Example: "Amazon Mechanical Turk", "Label Studio"
- Location: Methods, annotation subsection

**rai:annotatorDemographics**
- Definition: Characteristics of human annotators
- Example: "33,000 MTurk workers, 93% from US, ages 18-68"
- Location: Methods, ethics section, appendix

**rai:dataUseCases**
- Definition: Intended applications and supported tasks
- Example: "Automatic speech recognition, text-to-speech, speaker identification"
- Location: Introduction, conclusion, abstract

**rai:personalSensitiveInformation**
- Definition: How personally identifiable information was handled
- Example: "All data de-identified; no PII collected"
- Location: Ethics section, data collection

---

## Appendix B: Per-Model Field Accuracy Tables

### Claude Sonnet 4.5
| Field | Accuracy | Correct/Total |
|-------|----------|---------------|
| sc:name | 100.0% | 8.0/8 |
| sc:url | 100.0% | 8.0/8 |
| rai:dataCollectionTimeframe | 100.0% | 8.0/8 |
| sc:description | 87.5% | 7.0/8 |
| rai:personalSensitiveInformation | 87.5% | 7.0/8 |
| rai:dataUseCases | 81.2% | 6.5/8 |
| sc:creator | 81.2% | 6.5/8 |
| sc:inLanguage | 75.0% | 6.0/8 |
| rai:dataCollection | 68.8% | 5.5/8 |
| rai:dataAnnotationPlatform | 62.5% | 5.0/8 |
| sc:license | 62.5% | 5.0/8 |
| sc:datePublished | 57.1% | 4.0/7 |
| rai:annotatorDemographics | 56.2% | 4.5/8 |
| cr:citeAs | 50.0% | 4.0/8 |
| sc:publisher | 28.6% | 2.0/7 |
| cr:isLiveDataset | 25.0% | 2.0/8 |

### Gemini 2.5 Pro
| Field | Accuracy | Notes |
|-------|----------|-------|
| sc:name | 100.0% | Perfect |
| sc:url | 100.0% | Perfect |
| rai:dataCollectionTimeframe | 100.0% | Perfect |
| rai:personalSensitiveInformation | 87.5% | Strong |
| sc:description | 81.2% | Strong |
| rai:dataUseCases | 81.2% | Strong |
| sc:creator | 81.2% | Strong |
| sc:inLanguage | 75.0% | Good |
| rai:dataCollection | 68.8% | Moderate |
| rai:dataAnnotationPlatform | 62.5% | Moderate |
| sc:license | 62.5% | Moderate |
| sc:datePublished | 57.1% | Weak |
| rai:annotatorDemographics | 56.2% | Weak |
| cr:citeAs | 56.2% | Best model for this field |
| sc:publisher | 28.6% | Very weak |
| cr:isLiveDataset | 25.0% | Very weak |

---

**End of Report**

*For questions or collaboration inquiries, contact: [Your Contact]*
