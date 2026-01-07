# CroissantMiner Evaluation Report

## Summary

- **Average LLM-based Accuracy**: 29.41%

## Results by Dataset

### MLS

**Overall Metrics:**

- LLM-based Accuracy: 34.38%
- Fields evaluated: 16
- CORRECT: 3
- PARTIALLY_CORRECT: 2
- INCORRECT: 5
- MISSING: 6

**Field-Level Metrics (LLM Judge):**

| Field Name | Score | Category | Reasoning |
|------------|-------|----------|-----------|
| sc:creator | 1.00 | CORRECT | No groundtruth available for comparison |
| sc:publisher | 1.00 | CORRECT | No groundtruth available for comparison |
| sc:inLanguage | 0.83 | CORRECT | The extracted value 'English' is a valid language ... |
| rai:dataUseCases | 0.67 | PARTIALLY_CORRECT | The extracted value mentions training low-resource... |
| rai:dataCollection | 0.50 | PARTIALLY_CORRECT | The extracted value mentions automated parsers and... |
| cr:citeAs | 0.33 | INCORRECT | The extracted value refers to a different work wit... |
| sc:name | 0.33 | INCORRECT | The extracted value 'Multilingual LibriSpeech (MLS... |
| sc:datePublished | 0.33 | INCORRECT | The extracted date 'December 22, 2020' is signific... |
| sc:url | 0.33 | MISSING | The groundtruth value does not provide a valid URL... |
| sc:description | 0.17 | INCORRECT | The extracted value mentions a large dataset of au... |
| rai:dataCollectionTimeframe | 0.00 | MISSING | Field not extracted |
| sc:license | 0.00 | INCORRECT | The extracted value 'Public domain' is significant... |
| rai:annotatorDemographics | 0.00 | MISSING | Field not extracted |
| rai:dataAnnotationPlatform | 0.00 | MISSING | Field not extracted |
| rai:personalSensitiveInformation | 0.00 | MISSING | Field not extracted |
| cr:isLiveDataset | 0.00 | MISSING | Field not extracted |

### MMLU

**Overall Metrics:**

- LLM-based Accuracy: 25.56%
- Fields evaluated: 15
- CORRECT: 4
- PARTIALLY_CORRECT: 1
- INCORRECT: 5
- MISSING: 5

**Field-Level Metrics (LLM Judge):**

| Field Name | Score | Category | Reasoning |
|------------|-------|----------|-----------|
| sc:creator | 1.00 | CORRECT | No groundtruth available for comparison |
| rai:dataUseCases | 0.50 | CORRECT | No groundtruth available for comparison |
| rai:annotatorDemographics | 0.50 | CORRECT | No groundtruth available for comparison |
| sc:datePublished | 0.50 | CORRECT | No groundtruth available for comparison |
| cr:citeAs | 0.33 | INCORRECT | No groundtruth available for comparison |
| sc:license | 0.33 | INCORRECT | The extracted value 'unknown' does not match the g... |
| rai:dataCollection | 0.33 | INCORRECT | No groundtruth available for comparison |
| sc:description | 0.33 | PARTIALLY_CORRECT | The extracted value captures the essence of a mult... |
| cr:isLiveDataset | 0.00 | MISSING | Field not extracted |
| sc:name | 0.00 | INCORRECT | The extracted value 'Massive Multitask Test' is no... |
| rai:dataCollectionTimeframe | 0.00 | MISSING | Field not extracted |
| sc:url | 0.00 | INCORRECT | The extracted value 'github.com/hendrycks/test' is... |
| sc:inLanguage | 0.00 | MISSING | Field not extracted |
| rai:dataAnnotationPlatform | 0.00 | MISSING | Field not extracted |
| rai:personalSensitiveInformation | 0.00 | MISSING | Field not extracted |

### FLORES

**Overall Metrics:**

- LLM-based Accuracy: 25.00%
- Fields evaluated: 15
- CORRECT: 4
- PARTIALLY_CORRECT: 1
- INCORRECT: 3
- MISSING: 7

**Field-Level Metrics (LLM Judge):**

| Field Name | Score | Category | Reasoning |
|------------|-------|----------|-----------|
| sc:creator | 1.00 | CORRECT | No groundtruth available for comparison |
| sc:name | 0.50 | INCORRECT | The extracted value 'FLORES-101' does not match th... |
| sc:inLanguage | 0.50 | CORRECT | No groundtruth available for comparison |
| sc:url | 0.50 | INCORRECT | The extracted value is a URL pointing to a dataset... |
| rai:dataUseCases | 0.50 | CORRECT | No groundtruth available for comparison |
| rai:dataCollection | 0.50 | CORRECT | No groundtruth available for comparison |
| sc:description | 0.25 | PARTIALLY_CORRECT | The extracted value provides information about the... |
| cr:citeAs | 0.00 | MISSING | Field not extracted |
| rai:dataCollectionTimeframe | 0.00 | MISSING | Field not extracted |
| sc:license | 0.00 | INCORRECT | The extracted value 'unknown' does not match the g... |
| rai:annotatorDemographics | 0.00 | MISSING | Field not extracted |
| sc:datePublished | 0.00 | MISSING | Field not extracted |
| rai:dataAnnotationPlatform | 0.00 | MISSING | Field not extracted |
| rai:personalSensitiveInformation | 0.00 | MISSING | Field not extracted |
| cr:isLiveDataset | 0.00 | MISSING | Field not extracted |

### MSCOCO

**Overall Metrics:**

- LLM-based Accuracy: 20.00%
- Fields evaluated: 15
- CORRECT: 1
- PARTIALLY_CORRECT: 3
- INCORRECT: 5
- MISSING: 6

**Field-Level Metrics (LLM Judge):**

| Field Name | Score | Category | Reasoning |
|------------|-------|----------|-----------|
| sc:creator | 1.00 | CORRECT | No groundtruth available for comparison |
| rai:dataUseCases | 0.50 | PARTIALLY_CORRECT | The extracted value mentions practical application... |
| rai:dataCollection | 0.50 | PARTIALLY_CORRECT | The extracted value mentions the collection of ima... |
| sc:name | 0.33 | INCORRECT | No groundtruth available for comparison |
| sc:datePublished | 0.33 | MISSING | The groundtruth value is 'Unknown', which indicate... |
| sc:description | 0.33 | PARTIALLY_CORRECT | The extracted value provides information about the... |
| rai:dataCollectionTimeframe | 0.00 | MISSING | The groundtruth value is 'Unknown', which indicate... |
| cr:citeAs | 0.00 | INCORRECT | The extracted value is a reference to an arXiv pre... |
| sc:inLanguage | 0.00 | MISSING | Field not extracted |
| sc:license | 0.00 | INCORRECT | The extracted value 'unknown' does not match the g... |
| rai:annotatorDemographics | 0.00 | INCORRECT | The groundtruth value is 'Unknown', which indicate... |
| sc:url | 0.00 | MISSING | Field not extracted |
| rai:dataAnnotationPlatform | 0.00 | INCORRECT | The extracted value 'Modified user interface devel... |
| rai:personalSensitiveInformation | 0.00 | MISSING | Field not extracted |
| cr:isLiveDataset | 0.00 | MISSING | Field not extracted |

### MMMU

**Overall Metrics:**

- LLM-based Accuracy: 43.75%
- Fields evaluated: 16
- CORRECT: 10
- PARTIALLY_CORRECT: 0
- INCORRECT: 4
- MISSING: 2

**Field-Level Metrics (LLM Judge):**

| Field Name | Score | Category | Reasoning |
|------------|-------|----------|-----------|
| sc:inLanguage | 0.83 | CORRECT | No groundtruth available for comparison |
| rai:annotatorDemographics | 0.83 | CORRECT | No groundtruth available for comparison |
| rai:dataCollectionTimeframe | 0.67 | CORRECT | No groundtruth available for comparison |
| cr:citeAs | 0.67 | CORRECT | No groundtruth available for comparison |
| sc:creator | 0.67 | CORRECT | No groundtruth available for comparison |
| sc:datePublished | 0.67 | CORRECT | No groundtruth available for comparison |
| rai:dataUseCases | 0.67 | CORRECT | No groundtruth available for comparison |
| sc:publisher | 0.67 | CORRECT | No groundtruth available for comparison |
| cr:isLiveDataset | 0.67 | CORRECT | No groundtruth available for comparison |
| rai:dataCollection | 0.67 | CORRECT | No groundtruth available for comparison |
| sc:name | 0.00 | INCORRECT | The extracted value 'MMMU validation and test set'... |
| sc:license | 0.00 | INCORRECT | The extracted value 'unknown' does not match the g... |
| sc:url | 0.00 | INCORRECT | The extracted URL does not match the groundtruth v... |
| rai:dataAnnotationPlatform | 0.00 | MISSING | Field not extracted |
| rai:personalSensitiveInformation | 0.00 | MISSING | Field not extracted |
| sc:description | 0.00 | INCORRECT | The extracted value discusses clinical cases and d... |

### CIFAR

**Overall Metrics:**

- LLM-based Accuracy: 27.78%
- Fields evaluated: 15
- CORRECT: 2
- PARTIALLY_CORRECT: 4
- INCORRECT: 3
- MISSING: 6

**Field-Level Metrics (LLM Judge):**

| Field Name | Score | Category | Reasoning |
|------------|-------|----------|-----------|
| sc:creator | 1.00 | CORRECT | No groundtruth available for comparison |
| sc:inLanguage | 1.00 | CORRECT | Exact match (case-insensitive) |
| rai:dataUseCases | 0.50 | PARTIALLY_CORRECT | The extracted value mentions training and evaluati... |
| cr:citeAs | 0.33 | PARTIALLY_CORRECT | The extracted value includes the authors and year ... |
| sc:name | 0.33 | INCORRECT | Exact match (case-insensitive) |
| sc:datePublished | 0.33 | INCORRECT | The extracted value '2009' does not match the grou... |
| rai:dataCollection | 0.33 | PARTIALLY_CORRECT | The extracted value provides some relevant informa... |
| sc:description | 0.33 | PARTIALLY_CORRECT | The extracted value provides information about the... |
| rai:dataCollectionTimeframe | 0.00 | MISSING | Field not extracted |
| sc:license | 0.00 | INCORRECT | The groundtruth value is 'NA', indicating that no ... |
| rai:annotatorDemographics | 0.00 | MISSING | Field not extracted |
| sc:url | 0.00 | MISSING | The groundtruth value is not a valid URL and appea... |
| rai:dataAnnotationPlatform | 0.00 | MISSING | Field not extracted |
| rai:personalSensitiveInformation | 0.00 | MISSING | Field not extracted |
| cr:isLiveDataset | 0.00 | MISSING | Field not extracted |

## Recommendations

Based on the evaluation results:
