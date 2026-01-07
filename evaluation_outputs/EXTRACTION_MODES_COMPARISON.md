# Extraction Modes Comparison Report

**Generated:** 2025-10-29 16:16:58  
**Datasets Evaluated:** 8  
**Total Fields:** 16 per dataset  
**Evaluation Strategy:** LLM-as-Judge with Lenient Scoring

---

## Executive Summary

| Mode | Accuracy | Fields Correct | Total Fields | LLM Calls | Avg Time/Paper | Estimated Cost |
|------|----------|----------------|--------------|-----------|----------------|----------------|
| **Multi-Section** | 62.20% | 79.0 | 127 | 64 | ~60s | $38.40 |
| **Full-PDF** | 64.57% | 82.0 | 127 | 8 | 8.0s | $14.40 |
| **Difference** | **+2.36pp** | **+3.0** | - | **-87.5%** | **-86.6%** | **-62.5%** |

---

## Per-Dataset Results

| Dataset | Multi-Section | Full-PDF | Difference |
|---------|---------------|----------|------------|
| CIFAR | 80.0% | 80.0% | +0.0pp |
| MLS | 75.0% | 87.5% | +12.5pp |
| Visual Genome | 75.0% | 68.8% | -6.2pp |
| FLORES | 68.8% | 68.8% | +0.0pp |
| MSCOCO | 68.8% | 68.8% | +0.0pp |
| MMLU | 43.8% | 46.9% | +3.1pp |
| MMMU | 43.8% | 46.9% | +3.1pp |
| MathVista | 43.8% | 50.0% | +6.2pp |

---

## Per-Field Results

| Field | Multi-Section | Full-PDF | Difference |
|-------|---------------|----------|------------|
| cr:citeAs | 31.2% | 31.2% | +0.0pp |
| cr:isLiveDataset | 37.5% | 50.0% | +12.5pp |
| rai:annotatorDemographics | 75.0% | 50.0% | -25.0pp |
| rai:dataAnnotationPlatform | 62.5% | 62.5% | +0.0pp |
| rai:dataCollection | 56.2% | 68.8% | +12.5pp |
| rai:dataCollectionTimeframe | 100.0% | 100.0% | +0.0pp |
| rai:dataUseCases | 75.0% | 81.2% | +6.2pp |
| rai:personalSensitiveInformation | 37.5% | 50.0% | +12.5pp |
| sc:creator | 75.0% | 81.2% | +6.2pp |
| sc:datePublished | 75.0% | 62.5% | -12.5pp |
| sc:description | 75.0% | 81.2% | +6.2pp |
| sc:inLanguage | 37.5% | 43.8% | +6.2pp |
| sc:license | 62.5% | 62.5% | +0.0pp |
| sc:name | 87.5% | 100.0% | +12.5pp |
| sc:publisher | 35.7% | 14.3% | -21.4pp |
| sc:url | 68.8% | 87.5% | +18.8pp |

---

## Category Distribution

### Multi-Section Mode

| Category | Count | Percentage |
|----------|-------|------------|
| CORRECT | 72 | 56.7% |
| PARTIALLY_CORRECT | 14 | 11.0% |
| INCORRECT | 17 | 13.4% |
| MISSING | 24 | 18.9% |
| **Total** | **127** | **100.0%** |

### Full-PDF Mode

| Category | Count | Percentage |
|----------|-------|------------|
| CORRECT | 73 | 57.5% |
| PARTIALLY_CORRECT | 18 | 14.2% |
| INCORRECT | 5 | 3.9% |
| MISSING | 31 | 24.4% |
| **Total** | **127** | **100.0%** |

---

## Performance Metrics

### Extraction Time

| Metric | Multi-Section | Full-PDF |
|--------|---------------|----------|
| Total Time (8 papers) | ~480s | 64.3s |
| Average per Paper | ~60s | 8.0s |
| Speedup | - | 7.5x faster |

### LLM Call Efficiency

| Metric | Multi-Section | Full-PDF |
|--------|---------------|----------|
| Calls per Paper | 8 | 1 |
| Total Calls (8 papers) | 64 | 8 |
| Reduction | - | 87.5% fewer calls |

### Cost Analysis

| Metric | Multi-Section | Full-PDF |
|--------|---------------|----------|
| Cost per Paper | $4.80 | $1.80 |
| Total Cost (8 papers) | $38.40 | $14.40 |
| Savings | - | $24.00 (62.5%) |

**Pricing Assumptions:** GPT-4o-mini @ $0.150/1M input tokens, $0.600/1M output tokens

---

## Field Performance Analysis

### Top 5 Best Performing Fields (Full-PDF)

| Rank | Field | Accuracy | Status |
|------|-------|----------|--------|
| 1 | sc:name | 100.0% | Excellent |
| 2 | rai:dataCollectionTimeframe | 100.0% | Excellent |
| 3 | sc:url | 87.5% | Excellent |
| 4 | sc:description | 81.2% | Excellent |
| 5 | sc:creator | 81.2% | Excellent |

### Top 5 Worst Performing Fields (Full-PDF)

| Rank | Field | Accuracy | Status |
|------|-------|----------|--------|
| 1 | rai:personalSensitiveInformation | 50.0% | Needs Improvement |
| 2 | cr:isLiveDataset | 50.0% | Needs Improvement |
| 3 | sc:inLanguage | 43.8% | Poor |
| 4 | cr:citeAs | 31.2% | Poor |
| 5 | sc:publisher | 14.3% | Critical |

---

## Datasets Information

| Dataset | Paper | Fields Evaluated |
|---------|-------|------------------|
| CIFAR | 2404.00498v2.pdf | 15-16 |
| MLS | 2012.03411v2.pdf | 16 |
| Visual Genome | 1602.07332v1.pdf | 15-16 |
| FLORES | 2106.03193v1.pdf | 16 |
| MSCOCO | 1405.0312v3.pdf | 16 |
| MMLU | 2009.03300v3.pdf | 16 |
| MMMU | 2311.16502v4.pdf | 16 |
| MathVista | 2310.02255v3.pdf | 16 |

---

**Report Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**Evaluation System:** LLM-as-Judge (GPT-4o-mini, temperature=0.0)  
**Total Evaluations:** {multi_total_cats + full_total_cats}  
