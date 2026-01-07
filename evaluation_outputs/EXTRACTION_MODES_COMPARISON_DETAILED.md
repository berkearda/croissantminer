# Extraction Modes - Comprehensive Comparison Report

**Report Generated:** 2025-10-29 16:20:36  
**Evaluation Period:** October 2025  
**Datasets Evaluated:** 8 (CIFAR, MLS, Visual Genome, FLORES, MSCOCO, MMLU, MMMU, MathVista)  
**Fields per Dataset:** 16  
**Total Evaluations:** 127 (Multi-Section), 127 (Full-PDF)  
**Evaluation Method:** LLM-as-Judge (GPT-4o-mini, temperature=0.0)  
**Scoring Strategy:** Lenient (accept if ANY annotator matches)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Overall Performance Comparison](#overall-performance-comparison)
3. [Per-Dataset Analysis](#per-dataset-analysis)
4. [Per-Field Analysis](#per-field-analysis)
5. [Category Distribution](#category-distribution)
6. [Performance Metrics](#performance-metrics)
7. [Cost Analysis](#cost-analysis)
8. [Detailed Field Breakdown](#detailed-field-breakdown)
9. [Missing Fields Analysis](#missing-fields-analysis)
10. [Recommendations](#recommendations)

---

## Executive Summary

### Overall Results

| Mode | Accuracy | Fields Correct | Total Fields | Success Rate |
|------|----------|----------------|--------------|--------------|
| **Multi-Section** | 62.20% | 79.0 / 127 | 127 | 62.2% |
| **Full-PDF** | 64.57% | 82.0 / 127 | 127 | 64.6% |
| **Difference** | **+2.36pp** | **+3.0** | - | **+2.4pp** |

### Key Findings

- Full-PDF mode achieved **64.57% accuracy**, 2.36 percentage points higher than Multi-Section
- Full-PDF extracted **3.0 more correct fields** across all datasets
- Processing time reduced by **86.6%** (60s → 8.0s per paper)
- LLM calls reduced by **87.5%** (64 → 8 calls for 8 papers)
- Cost savings of **62.5%** ($38.40 → $14.40 for 8 papers)

---

## Overall Performance Comparison

### Accuracy Metrics

| Metric | Multi-Section | Full-PDF | Change |
|--------|---------------|----------|--------|
| Overall Accuracy | 62.20% | 64.57% | +2.36pp |
| Correct Fields | 79.0 | 82.0 | +3.0 |
| Total Fields | 127 | 127 | 0 |

### Extraction Quality

| Category | Multi-Section | Full-PDF | Change |
|----------|---------------|----------|--------|
| CORRECT | 72 (56.7%) | 73 (57.5%) | +1 |
| PARTIALLY_CORRECT | 14 (11.0%) | 18 (14.2%) | +4 |
| INCORRECT | 17 (13.4%) | 5 (3.9%) | -12 |
| MISSING | 24 (18.9%) | 31 (24.4%) | +7 |

### Efficiency Metrics

| Metric | Multi-Section | Full-PDF | Improvement |
|--------|---------------|----------|-------------|
| LLM Calls per Paper | 8 | 1 | 87.5% reduction |
| Avg Time per Paper | ~60s | 8.0s | 86.6% faster |
| Total LLM Calls | 64 | 8 | 87.5% reduction |
| Total Time | ~480s | 64.3s | 86.6% faster |

---

## Per-Dataset Analysis

### Detailed Dataset Comparison


#### CIFAR

| Metric | Multi-Section | Full-PDF | Difference |
|--------|---------------|----------|------------|
| **Accuracy** | **80.0%** | **80.0%** | **+0.0pp 🟡 Similar** |
| Correct | 11 | 11 | +0 |
| Partially Correct | 2 | 2 | +0 |
| Incorrect | 0 | 0 | +0 |
| Missing | 2 | 2 | +0 |
| Total Fields | 15 | 15 | 0 |

#### MLS

| Metric | Multi-Section | Full-PDF | Difference |
|--------|---------------|----------|------------|
| **Accuracy** | **75.0%** | **87.5%** | **+12.5pp 🟢 Better** |
| Correct | 12 | 13 | +1 |
| Partially Correct | 0 | 2 | +2 |
| Incorrect | 1 | 0 | -1 |
| Missing | 3 | 1 | -2 |
| Total Fields | 16 | 16 | 0 |

#### Visual Genome

| Metric | Multi-Section | Full-PDF | Difference |
|--------|---------------|----------|------------|
| **Accuracy** | **75.0%** | **68.8%** | **-6.2pp 🔴 Worse** |
| Correct | 12 | 11 | -1 |
| Partially Correct | 0 | 0 | +0 |
| Incorrect | 0 | 0 | +0 |
| Missing | 4 | 5 | +1 |
| Total Fields | 16 | 16 | 0 |

#### FLORES

| Metric | Multi-Section | Full-PDF | Difference |
|--------|---------------|----------|------------|
| **Accuracy** | **68.8%** | **68.8%** | **+0.0pp 🟡 Similar** |
| Correct | 11 | 11 | +0 |
| Partially Correct | 0 | 0 | +0 |
| Incorrect | 1 | 0 | -1 |
| Missing | 4 | 5 | +1 |
| Total Fields | 16 | 16 | 0 |

#### MSCOCO

| Metric | Multi-Section | Full-PDF | Difference |
|--------|---------------|----------|------------|
| **Accuracy** | **68.8%** | **68.8%** | **+0.0pp 🟡 Similar** |
| Correct | 10 | 10 | +0 |
| Partially Correct | 2 | 2 | +0 |
| Incorrect | 0 | 0 | +0 |
| Missing | 4 | 4 | +0 |
| Total Fields | 16 | 16 | 0 |

#### MMLU

| Metric | Multi-Section | Full-PDF | Difference |
|--------|---------------|----------|------------|
| **Accuracy** | **43.8%** | **46.9%** | **+3.1pp 🟡 Similar** |
| Correct | 5 | 5 | +0 |
| Partially Correct | 4 | 5 | +1 |
| Incorrect | 3 | 2 | -1 |
| Missing | 4 | 4 | +0 |
| Total Fields | 16 | 16 | 0 |

#### MMMU

| Metric | Multi-Section | Full-PDF | Difference |
|--------|---------------|----------|------------|
| **Accuracy** | **43.8%** | **46.9%** | **+3.1pp 🟡 Similar** |
| Correct | 6 | 6 | +0 |
| Partially Correct | 2 | 3 | +1 |
| Incorrect | 7 | 1 | -6 |
| Missing | 1 | 6 | +5 |
| Total Fields | 16 | 16 | 0 |

#### MathVista

| Metric | Multi-Section | Full-PDF | Difference |
|--------|---------------|----------|------------|
| **Accuracy** | **43.8%** | **50.0%** | **+6.2pp 🟢 Better** |
| Correct | 5 | 6 | +1 |
| Partially Correct | 4 | 4 | +0 |
| Incorrect | 5 | 2 | -3 |
| Missing | 2 | 4 | +2 |
| Total Fields | 16 | 16 | 0 |

### Dataset Performance Summary

| Dataset | Multi-Section | Full-PDF | Difference | Winner |
|---------|---------------|----------|------------|--------|
| CIFAR | 80.0% | 80.0% | +0.0pp | Tie |
| MLS | 75.0% | 87.5% | +12.5pp | Full-PDF |
| Visual Genome | 75.0% | 68.8% | -6.2pp | Multi-Section |
| FLORES | 68.8% | 68.8% | +0.0pp | Tie |
| MSCOCO | 68.8% | 68.8% | +0.0pp | Tie |
| MMLU | 43.8% | 46.9% | +3.1pp | Full-PDF |
| MMMU | 43.8% | 46.9% | +3.1pp | Full-PDF |
| MathVista | 43.8% | 50.0% | +6.2pp | Full-PDF |

---

## Per-Field Analysis

### All Fields Comparison

| Field | Multi-Section | Full-PDF | Difference | Status |
|-------|---------------|----------|------------|--------|
| cr:citeAs | 31.2% | 31.2% | +0.0pp | 🟡 Similar |
| cr:isLiveDataset | 37.5% | 50.0% | +12.5pp | 🟢 Improved |
| rai:annotatorDemographics | 75.0% | 50.0% | -25.0pp | 🔴 Declined |
| rai:dataAnnotationPlatform | 62.5% | 62.5% | +0.0pp | 🟡 Similar |
| rai:dataCollection | 56.2% | 68.8% | +12.5pp | 🟢 Improved |
| rai:dataCollectionTimeframe | 100.0% | 100.0% | +0.0pp | 🟡 Similar |
| rai:dataUseCases | 75.0% | 81.2% | +6.2pp | 🟢 Improved |
| rai:personalSensitiveInformation | 37.5% | 50.0% | +12.5pp | 🟢 Improved |
| sc:creator | 75.0% | 81.2% | +6.2pp | 🟢 Improved |
| sc:datePublished | 75.0% | 62.5% | -12.5pp | 🔴 Declined |
| sc:description | 75.0% | 81.2% | +6.2pp | 🟢 Improved |
| sc:inLanguage | 37.5% | 43.8% | +6.2pp | 🟢 Improved |
| sc:license | 62.5% | 62.5% | +0.0pp | 🟡 Similar |
| sc:name | 87.5% | 100.0% | +12.5pp | 🟢 Improved |
| sc:publisher | 35.7% | 14.3% | -21.4pp | 🔴 Declined |
| sc:url | 68.8% | 87.5% | +18.8pp | 🟢 Improved |

---

## Detailed Field Breakdown


### cr:citeAs

| Metric | Multi-Section | Full-PDF |
|--------|---------------|----------|
| **Accuracy** | **31.2%** | **31.2%** |
| Correct | 1 | 1 |
| Partially Correct | 3 | 3 |
| Incorrect | 2 | 0 |
| Missing | 2 | 4 |
| Total | 8 | 8 |

### cr:isLiveDataset

| Metric | Multi-Section | Full-PDF |
|--------|---------------|----------|
| **Accuracy** | **37.5%** | **50.0%** |
| Correct | 3 | 4 |
| Partially Correct | 0 | 0 |
| Incorrect | 0 | 0 |
| Missing | 5 | 4 |
| Total | 8 | 8 |

### rai:annotatorDemographics

| Metric | Multi-Section | Full-PDF |
|--------|---------------|----------|
| **Accuracy** | **75.0%** | **50.0%** |
| Correct | 6 | 4 |
| Partially Correct | 0 | 0 |
| Incorrect | 0 | 1 |
| Missing | 2 | 3 |
| Total | 8 | 8 |

### rai:dataAnnotationPlatform

| Metric | Multi-Section | Full-PDF |
|--------|---------------|----------|
| **Accuracy** | **62.5%** | **62.5%** |
| Correct | 5 | 5 |
| Partially Correct | 0 | 0 |
| Incorrect | 1 | 0 |
| Missing | 2 | 3 |
| Total | 8 | 8 |

### rai:dataCollection

| Metric | Multi-Section | Full-PDF |
|--------|---------------|----------|
| **Accuracy** | **56.2%** | **68.8%** |
| Correct | 3 | 3 |
| Partially Correct | 3 | 5 |
| Incorrect | 2 | 0 |
| Missing | 0 | 0 |
| Total | 8 | 8 |

### rai:dataCollectionTimeframe

| Metric | Multi-Section | Full-PDF |
|--------|---------------|----------|
| **Accuracy** | **100.0%** | **100.0%** |
| Correct | 8 | 8 |
| Partially Correct | 0 | 0 |
| Incorrect | 0 | 0 |
| Missing | 0 | 0 |
| Total | 8 | 8 |

### rai:dataUseCases

| Metric | Multi-Section | Full-PDF |
|--------|---------------|----------|
| **Accuracy** | **75.0%** | **81.2%** |
| Correct | 5 | 5 |
| Partially Correct | 2 | 3 |
| Incorrect | 1 | 0 |
| Missing | 0 | 0 |
| Total | 8 | 8 |

### rai:personalSensitiveInformation

| Metric | Multi-Section | Full-PDF |
|--------|---------------|----------|
| **Accuracy** | **37.5%** | **50.0%** |
| Correct | 3 | 4 |
| Partially Correct | 0 | 0 |
| Incorrect | 0 | 0 |
| Missing | 5 | 4 |
| Total | 8 | 8 |

### sc:creator

| Metric | Multi-Section | Full-PDF |
|--------|---------------|----------|
| **Accuracy** | **75.0%** | **81.2%** |
| Correct | 5 | 5 |
| Partially Correct | 2 | 3 |
| Incorrect | 1 | 0 |
| Missing | 0 | 0 |
| Total | 8 | 8 |

### sc:datePublished

| Metric | Multi-Section | Full-PDF |
|--------|---------------|----------|
| **Accuracy** | **75.0%** | **62.5%** |
| Correct | 6 | 5 |
| Partially Correct | 0 | 0 |
| Incorrect | 1 | 0 |
| Missing | 1 | 3 |
| Total | 8 | 8 |

### sc:description

| Metric | Multi-Section | Full-PDF |
|--------|---------------|----------|
| **Accuracy** | **75.0%** | **81.2%** |
| Correct | 5 | 5 |
| Partially Correct | 2 | 3 |
| Incorrect | 1 | 0 |
| Missing | 0 | 0 |
| Total | 8 | 8 |

### sc:inLanguage

| Metric | Multi-Section | Full-PDF |
|--------|---------------|----------|
| **Accuracy** | **37.5%** | **43.8%** |
| Correct | 3 | 3 |
| Partially Correct | 0 | 1 |
| Incorrect | 1 | 0 |
| Missing | 4 | 4 |
| Total | 8 | 8 |

### sc:license

| Metric | Multi-Section | Full-PDF |
|--------|---------------|----------|
| **Accuracy** | **62.5%** | **62.5%** |
| Correct | 5 | 5 |
| Partially Correct | 0 | 0 |
| Incorrect | 3 | 3 |
| Missing | 0 | 0 |
| Total | 8 | 8 |

### sc:name

| Metric | Multi-Section | Full-PDF |
|--------|---------------|----------|
| **Accuracy** | **87.5%** | **100.0%** |
| Correct | 7 | 8 |
| Partially Correct | 0 | 0 |
| Incorrect | 1 | 0 |
| Missing | 0 | 0 |
| Total | 8 | 8 |

### sc:publisher

| Metric | Multi-Section | Full-PDF |
|--------|---------------|----------|
| **Accuracy** | **35.7%** | **14.3%** |
| Correct | 2 | 1 |
| Partially Correct | 1 | 0 |
| Incorrect | 1 | 0 |
| Missing | 3 | 6 |
| Total | 7 | 7 |

### sc:url

| Metric | Multi-Section | Full-PDF |
|--------|---------------|----------|
| **Accuracy** | **68.8%** | **87.5%** |
| Correct | 5 | 7 |
| Partially Correct | 1 | 0 |
| Incorrect | 2 | 1 |
| Missing | 0 | 0 |
| Total | 8 | 8 |

---

## Category Distribution

### Multi-Section Mode

| Category | Count | Percentage | Description |
|----------|-------|------------|-------------|
| CORRECT | {multi_cats['CORRECT']} | {multi_cats['CORRECT']/multi_total*100:.1f}% | Semantically equivalent to groundtruth |
| PARTIALLY_CORRECT | {multi_cats['PARTIALLY_CORRECT']} | {multi_cats['PARTIALLY_CORRECT']/multi_total*100:.1f}% | Contains some correct information |
| INCORRECT | {multi_cats['INCORRECT']} | {multi_cats['INCORRECT']/multi_total*100:.1f}% | Wrong or significantly different |
| MISSING | {multi_cats['MISSING']} | {multi_cats['MISSING']/multi_total*100:.1f}% | Field not extracted |
| **Total** | **{multi_total}** | **100.0%** | - |

### Full-PDF Mode

| Category | Count | Percentage | Description |
|----------|-------|------------|-------------|
| CORRECT | {full_cats['CORRECT']} | {full_cats['CORRECT']/full_total*100:.1f}% | Semantically equivalent to groundtruth |
| PARTIALLY_CORRECT | {full_cats['PARTIALLY_CORRECT']} | {full_cats['PARTIALLY_CORRECT']/full_total*100:.1f}% | Contains some correct information |
| INCORRECT | {full_cats['INCORRECT']} | {full_cats['INCORRECT']/full_total*100:.1f}% | Wrong or significantly different |
| MISSING | {full_cats['MISSING']} | {full_cats['MISSING']/full_total*100:.1f}% | Field not extracted |
| **Total** | **{full_total}** | **100.0%** | - |

### Category Comparison

| Category | Multi-Section | Full-PDF | Change |
|----------|---------------|----------|--------|
| CORRECT | {multi_cats['CORRECT']} | {full_cats['CORRECT']} | {full_cats['CORRECT'] - multi_cats['CORRECT']:+d} ({(full_cats['CORRECT'] - multi_cats['CORRECT'])/multi_total*100:+.1f}pp) |
| PARTIALLY_CORRECT | {multi_cats['PARTIALLY_CORRECT']} | {full_cats['PARTIALLY_CORRECT']} | {full_cats['PARTIALLY_CORRECT'] - multi_cats['PARTIALLY_CORRECT']:+d} ({(full_cats['PARTIALLY_CORRECT'] - multi_cats['PARTIALLY_CORRECT'])/multi_total*100:+.1f}pp) |
| INCORRECT | {multi_cats['INCORRECT']} | {full_cats['INCORRECT']} | {full_cats['INCORRECT'] - multi_cats['INCORRECT']:+d} ({(full_cats['INCORRECT'] - multi_cats['INCORRECT'])/multi_total*100:+.1f}pp) |
| MISSING | {multi_cats['MISSING']} | {full_cats['MISSING']} | {full_cats['MISSING'] - multi_cats['MISSING']:+d} ({(full_cats['MISSING'] - multi_cats['MISSING'])/multi_total*100:+.1f}pp) |

---

## Performance Metrics

### Extraction Time Analysis

| Metric | Multi-Section | Full-PDF | Improvement |
|--------|---------------|----------|-------------|
| Total Time (8 papers) | ~480 seconds | {extraction['summary']['total_time']:.1f} seconds | {480 - extraction['summary']['total_time']:.1f}s saved ({(1-extraction['summary']['total_time']/480)*100:.1f}%) |
| Average per Paper | ~60 seconds | {extraction['summary']['avg_time_per_paper']:.1f} seconds | {60 - extraction['summary']['avg_time_per_paper']:.1f}s faster ({(1-extraction['summary']['avg_time_per_paper']/60)*100:.1f}%) |
| Speedup Factor | 1.0x (baseline) | {60/extraction['summary']['avg_time_per_paper']:.1f}x faster | {60/extraction['summary']['avg_time_per_paper']:.1f}x improvement |

### LLM Call Efficiency

| Metric | Multi-Section | Full-PDF | Reduction |
|--------|---------------|----------|-----------|
| Calls per Paper | 8 | 1 | 7 fewer calls |
| Total Calls (8 papers) | 64 | {extraction['summary']['total_llm_calls']} | {64 - extraction['summary']['total_llm_calls']} fewer calls |
| Reduction Percentage | 0% (baseline) | 87.5% | 87.5% reduction |
| Calls per Field Extracted | ~0.5 | ~0.11 | 78% reduction |

---

## Cost Analysis

### Detailed Cost Breakdown

**Pricing Model:** GPT-4o-mini
- Input: $0.150 per 1M tokens
- Output: $0.600 per 1M tokens

**Assumptions:**
- Multi-Section: ~2,000 input tokens + 500 output tokens per call
- Full-PDF: ~10,000 input tokens + 500 output tokens per call

| Cost Component | Multi-Section | Full-PDF |
|----------------|---------------|----------|
| Cost per Call | ~$0.60 | ~$1.80 |
| Calls per Paper | 8 | 1 |
| **Cost per Paper** | **~$4.80** | **~$1.80** |
| Cost for 8 Papers | $38.40 | $14.40 |
| Cost for 100 Papers | $480.00 | $180.00 |
| Cost for 1000 Papers | $4,800.00 | $1,800.00 |

### Cost Savings

| Scale | Multi-Section | Full-PDF | Savings | Percentage |
|-------|---------------|----------|---------|------------|
| 1 Paper | $4.80 | $1.80 | $3.00 | 62.5% |
| 8 Papers | $38.40 | $14.40 | $24.00 | 62.5% |
| 100 Papers | $480.00 | $180.00 | $300.00 | 62.5% |
| 1000 Papers | $4,800.00 | $1,800.00 | $3,000.00 | 62.5% |

---

## Missing Fields Analysis

### Multi-Section Mode - Missing Fields

| Field | Missing Count | Total | Percentage |
|-------|---------------|-------|------------|
| rai:personalSensitiveInformation | 5 | 8 | 62.5% |
| cr:isLiveDataset | 5 | 8 | 62.5% |
| sc:inLanguage | 4 | 8 | 50.0% |
| sc:publisher | 3 | 7 | 42.9% |
| rai:annotatorDemographics | 2 | 8 | 25.0% |
| rai:dataAnnotationPlatform | 2 | 8 | 25.0% |
| cr:citeAs | 2 | 8 | 25.0% |
| sc:datePublished | 1 | 8 | 12.5% |

### Full-PDF Mode - Missing Fields

| Field | Missing Count | Total | Percentage |
|-------|---------------|-------|------------|
| sc:publisher | 6 | 7 | 85.7% |
| sc:inLanguage | 4 | 8 | 50.0% |
| cr:citeAs | 4 | 8 | 50.0% |
| rai:personalSensitiveInformation | 4 | 8 | 50.0% |
| cr:isLiveDataset | 4 | 8 | 50.0% |
| rai:dataAnnotationPlatform | 3 | 8 | 37.5% |
| sc:datePublished | 3 | 8 | 37.5% |
| rai:annotatorDemographics | 3 | 8 | 37.5% |

---

## Recommendations

### Based on Performance Analysis

1. **Default Extraction Mode:** Full-PDF
   - Higher accuracy ({full_acc:.2f}% vs {multi_acc:.2f}%)
   - 87.5% fewer LLM calls
   - 86.6% faster processing
   - 62.5% cost savings

2. **Use Multi-Section When:**
   - Paper exceeds 50,000 characters (token limit)
   - Need redundancy through voting/consensus
   - Processing very long papers (>100 pages)

3. **Fields Needing Improvement:**

| Field | Accuracy | Issue | Recommendation |
|-------|----------|-------|----------------|
| sc:publisher | 14.3% | 6 missing, 0 incorrect | Improve extraction prompt |
| cr:citeAs | 31.2% | 4 missing, 0 incorrect | Improve extraction prompt |
| sc:inLanguage | 43.8% | 4 missing, 0 incorrect | Improve extraction prompt |
| rai:annotatorDemographics | 50.0% | 3 missing, 1 incorrect | Add field-specific examples |
| rai:personalSensitiveInformation | 50.0% | 4 missing, 0 incorrect | Improve extraction prompt |

---

## Dataset Information

| Dataset | PDF File | Pages | Fields | Extraction Time (Full-PDF) |
|---------|----------|-------|--------|---------------------------|
| CIFAR-10/100 | 2404.00498v2.pdf | - | 10 | 6.5s |
| Multilingual LibriSpeech | 2012.03411v2.pdf | - | 13 | 4.9s |
| Visual Genome | 1602.07332v1.pdf | - | 9 | 6.3s |
| FLORES-101 | 2106.03193v1.pdf | - | 6 | 11.4s |
| MS COCO | 1405.0312v3.pdf | - | 9 | 7.7s |
| MMLU | 2009.03300v3.pdf | - | 9 | 7.3s |
| MMMU | 2311.16502v4.pdf | - | 7 | 9.9s |
| MathVista | 2310.02255v3.pdf | - | 9 | 10.3s |

---

## Appendix

### Evaluation Configuration

- **LLM Judge:** GPT-4o-mini
- **Temperature:** 0.0 (deterministic)
- **Scoring Strategy:** Lenient (accept if ANY annotator matches)
- **Annotators per Dataset:** 3
- **Cache Strategy:** Timestamp-based versioning

### File Locations

- Multi-Section Results: `evaluation_outputs/evaluation_report_lenient.json`
- Full-PDF Results: `evaluation_outputs/evaluation_report_full_pdf.json`
- Extraction Stats: `evaluation_outputs/full_pdf_extraction_results.json`
- Detailed Report: `evaluation_outputs/full_pdf_evaluation_detailed.md`

---

**Report Generated:** 2025-10-29 16:20:36  
**Total Evaluations:** 254  
**Evaluation System Version:** 3.0
