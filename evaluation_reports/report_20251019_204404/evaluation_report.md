# CroissantMiner Evaluation Report

## Summary

- **Average LLM-based Accuracy**: 25.89%

## Results by Dataset

### MLS

**Overall Metrics:**

- LLM-based Accuracy: 28.26%
- Fields evaluated: 23
- CORRECT: 4
- PARTIALLY_CORRECT: 2
- INCORRECT: 5
- MISSING: 12

**Field-Level Metrics (LLM Judge):**

| Field Name | Score | Category | Reasoning |
|------------|-------|----------|-----------|
| sc:creator | 1.00 | CORRECT | No groundtruth available for comparison |
| sc:publisher | 1.00 | CORRECT | No groundtruth available for comparison |
| cr:dataModality | 1.00 | CORRECT | No groundtruth available for comparison |
| sc:inLanguage | 0.83 | CORRECT | The extracted value 'English' is a valid language ... |
| rai:dataUseCases | 0.67 | PARTIALLY_CORRECT | The extracted value mentions training low-resource... |
| rai:dataCollection | 0.50 | PARTIALLY_CORRECT | The extracted value mentions automated parsers and... |
| sc:datePublished | 0.33 | INCORRECT | The extracted date 'December 22, 2020' is signific... |
| sc:url | 0.33 | MISSING | The groundtruth value does not provide a valid URL... |
| sc:name | 0.33 | INCORRECT | The extracted value 'Multilingual LibriSpeech (MLS... |
| cr:citeAs | 0.33 | INCORRECT | The extracted value refers to a different work wit... |
| sc:description | 0.17 | INCORRECT | The extracted value mentions a large dataset of au... |
| rai:annotatorDemographics | 0.00 | MISSING | Field not extracted |
| url | 0.00 | MISSING | Field not extracted |
| https: | 0.00 | MISSING | Field not extracted |
| Pratap | 0.00 | MISSING | Field not extracted |
| sc:license | 0.00 | INCORRECT | The extracted value 'Public domain' is significant... |
| rai:dataAnnotationPlatform | 0.00 | MISSING | Field not extracted |
| name | 0.00 | MISSING | Field not extracted |
| rai:dataCollectionTimeframe | 0.00 | MISSING | Field not extracted |
| al | 0.00 | MISSING | Field not extracted |
| mls_eng_10k | 0.00 | MISSING | Field not extracted |
| rai:personalSensitiveInformation | 0.00 | MISSING | Field not extracted |
| cr:isLiveDataset | 0.00 | MISSING | Field not extracted |

### MMLU

**Overall Metrics:**

- LLM-based Accuracy: 20.14%
- Fields evaluated: 24
- CORRECT: 5
- PARTIALLY_CORRECT: 1
- INCORRECT: 5
- MISSING: 13

**Field-Level Metrics (LLM Judge):**

| Field Name | Score | Category | Reasoning |
|------------|-------|----------|-----------|
| sc:creator | 1.00 | CORRECT | No groundtruth available for comparison |
| cr:dataModality | 1.00 | CORRECT | No groundtruth available for comparison |
| rai:annotatorDemographics | 0.50 | CORRECT | No groundtruth available for comparison |
| sc:datePublished | 0.50 | CORRECT | No groundtruth available for comparison |
| rai:dataUseCases | 0.50 | CORRECT | No groundtruth available for comparison |
| sc:license | 0.33 | INCORRECT | The extracted value 'unknown' does not match the g... |
| sc:description | 0.33 | PARTIALLY_CORRECT | The extracted value captures the essence of a test... |
| rai:dataCollection | 0.33 | INCORRECT | No groundtruth available for comparison |
| cr:citeAs | 0.33 | INCORRECT | No groundtruth available for comparison |
| email | 0.00 | MISSING | Field not extracted |
|  and | 0.00 | MISSING | Field not extracted |
| ship | 0.00 | MISSING | Field not extracted |
| sc:url | 0.00 | INCORRECT | The extracted value 'github.com/hendrycks/test' is... |
| rai:dataAnnotationPlatform | 0.00 | MISSING | Field not extracted |
| Steinhardt | 0.00 | MISSING | Field not extracted |
| name | 0.00 | MISSING | Field not extracted |
| rai:dataCollectionTimeframe | 0.00 | MISSING | Field not extracted |
| class. | 0.00 | MISSING | Field not extracted |
| Hinton | 0.00 | MISSING | Field not extracted |
| sc:inLanguage | 0.00 | MISSING | Field not extracted |
| ship, | 0.00 | MISSING | Field not extracted |
| rai:personalSensitiveInformation | 0.00 | MISSING | Field not extracted |
| cr:isLiveDataset | 0.00 | MISSING | Field not extracted |
| sc:name | 0.00 | INCORRECT | The extracted value 'Massive Multitask Test' is no... |

### FLORES

**Overall Metrics:**

- LLM-based Accuracy: 21.59%
- Fields evaluated: 22
- CORRECT: 5
- PARTIALLY_CORRECT: 1
- INCORRECT: 3
- MISSING: 13

**Field-Level Metrics (LLM Judge):**

| Field Name | Score | Category | Reasoning |
|------------|-------|----------|-----------|
| sc:creator | 1.00 | CORRECT | No groundtruth available for comparison |
| cr:dataModality | 1.00 | CORRECT | No groundtruth available for comparison |
| rai:dataUseCases | 0.50 | CORRECT | No groundtruth available for comparison |
| sc:url | 0.50 | INCORRECT | The extracted value is a URL pointing to a dataset... |
| rai:dataCollection | 0.50 | CORRECT | No groundtruth available for comparison |
| sc:inLanguage | 0.50 | CORRECT | No groundtruth available for comparison |
| sc:name | 0.50 | INCORRECT | The extracted value 'FLORES-101' does not match th... |
| sc:description | 0.25 | PARTIALLY_CORRECT | The extracted value provides information about the... |
| rai:annotatorDemographics | 0.00 | MISSING | Field not extracted |
| sc:datePublished | 0.00 | MISSING | Field not extracted |
| email | 0.00 | MISSING | Field not extracted |
| https: | 0.00 | MISSING | Field not extracted |
| sc:license | 0.00 | INCORRECT | The extracted value 'unknown' does not match the g... |
| rai:dataAnnotationPlatform | 0.00 | MISSING | Field not extracted |
| name | 0.00 | MISSING | Field not extracted |
| Databricks, Inc. | 0.00 | MISSING | Field not extracted |
| databricks/databricks-dolly-15k | 0.00 | MISSING | Field not extracted |
| rai:dataCollectionTimeframe | 0.00 | MISSING | Field not extracted |
| affiliation | 0.00 | MISSING | Field not extracted |
| rai:personalSensitiveInformation | 0.00 | MISSING | Field not extracted |
| cr:isLiveDataset | 0.00 | MISSING | Field not extracted |
| cr:citeAs | 0.00 | MISSING | Field not extracted |

### MSCOCO

**Overall Metrics:**

- LLM-based Accuracy: 17.39%
- Fields evaluated: 23
- CORRECT: 2
- PARTIALLY_CORRECT: 3
- INCORRECT: 7
- MISSING: 11

**Field-Level Metrics (LLM Judge):**

| Field Name | Score | Category | Reasoning |
|------------|-------|----------|-----------|
| sc:creator | 1.00 | CORRECT | No groundtruth available for comparison |
| cr:dataModality | 1.00 | CORRECT | No groundtruth available for comparison |
| rai:dataUseCases | 0.50 | PARTIALLY_CORRECT | The extracted value mentions practical application... |
| rai:dataCollection | 0.50 | PARTIALLY_CORRECT | The extracted value mentions the collection of ima... |
| sc:datePublished | 0.33 | INCORRECT | The extracted value '2014' does not match the grou... |
| sc:description | 0.33 | PARTIALLY_CORRECT | The extracted value provides information about the... |
| sc:name | 0.33 | INCORRECT | No groundtruth available for comparison |
| rai:annotatorDemographics | 0.00 | INCORRECT | The groundtruth value is 'Unknown', which indicate... |
| Tsung-Yi Lin Google Brain Genevieve Patterson MSR, Trash TV Matteo R. Ronchi Caltech Yin Cui Google Michael Maire TTI-Chicago Serge Belongie Cornell Tech Lubomir Bourdev WaveOne, Inc. Ross Girshick FAIR James Hays Georgia Tech Pietro Perona Caltech Deva Ramanan CMU Larry Zitnick FAIR Piotr Dollár FAIR | 0.00 | MISSING | Field not extracted |
| https: | 0.00 | MISSING | Field not extracted |
| sc:license | 0.00 | INCORRECT | The extracted value 'unknown' does not match the g... |
| yes | 0.00 | MISSING | Field not extracted |
| Coco | 0.00 | MISSING | Field not extracted |
| sc:url | 0.00 | MISSING | Field not extracted |
| rai:dataAnnotationPlatform | 0.00 | INCORRECT | The extracted value 'Modified user interface devel... |
| rai:dataCollectionTimeframe | 0.00 | INCORRECT | The extracted value specifies a timeframe (2014 fo... |
| sc | 0.00 | MISSING | Field not extracted |
| al | 0.00 | MISSING | Field not extracted |
| COCO Consortium: Tsung-Yi Lin, Michael Maire, Serge Belongie, Lubomir Bourdev, Ross Girshick, James Hays, Pietro Perona, Deva Ramanan, C. Lawrence Zitnick, Piotr Dollar | 0.00 | MISSING | Field not extracted |
| sc:inLanguage | 0.00 | MISSING | Field not extracted |
| rai:personalSensitiveInformation | 0.00 | MISSING | Field not extracted |
| cr:isLiveDataset | 0.00 | MISSING | Field not extracted |
| cr:citeAs | 0.00 | INCORRECT | The extracted value is a reference to an arXiv pre... |

### MMMU

**Overall Metrics:**

- LLM-based Accuracy: 42.11%
- Fields evaluated: 19
- CORRECT: 11
- PARTIALLY_CORRECT: 0
- INCORRECT: 4
- MISSING: 4

**Field-Level Metrics (LLM Judge):**

| Field Name | Score | Category | Reasoning |
|------------|-------|----------|-----------|
| cr:dataModality | 1.00 | CORRECT | No groundtruth available for comparison |
| rai:annotatorDemographics | 0.83 | CORRECT | No groundtruth available for comparison |
| sc:inLanguage | 0.83 | CORRECT | No groundtruth available for comparison |
| sc:datePublished | 0.67 | CORRECT | No groundtruth available for comparison |
| sc:creator | 0.67 | CORRECT | No groundtruth available for comparison |
| rai:dataUseCases | 0.67 | CORRECT | No groundtruth available for comparison |
| sc:publisher | 0.67 | CORRECT | No groundtruth available for comparison |
| rai:dataCollection | 0.67 | CORRECT | No groundtruth available for comparison |
| rai:dataCollectionTimeframe | 0.67 | CORRECT | No groundtruth available for comparison |
| cr:isLiveDataset | 0.67 | CORRECT | No groundtruth available for comparison |
| cr:citeAs | 0.67 | CORRECT | No groundtruth available for comparison |
| email | 0.00 | MISSING | Field not extracted |
| sc:license | 0.00 | INCORRECT | The extracted value 'unknown' does not match the g... |
| sc:description | 0.00 | INCORRECT | The extracted value discusses clinical cases and d... |
| sc:url | 0.00 | INCORRECT | The extracted URL does not match the groundtruth v... |
| rai:dataAnnotationPlatform | 0.00 | MISSING | Field not extracted |
| name | 0.00 | MISSING | Field not extracted |
| rai:personalSensitiveInformation | 0.00 | MISSING | Field not extracted |
| sc:name | 0.00 | INCORRECT | The extracted value 'MMMU validation and test set'... |

### CIFAR

**Overall Metrics:**

- LLM-based Accuracy: 25.83%
- Fields evaluated: 20
- CORRECT: 3
- PARTIALLY_CORRECT: 4
- INCORRECT: 3
- MISSING: 10

**Field-Level Metrics (LLM Judge):**

| Field Name | Score | Category | Reasoning |
|------------|-------|----------|-----------|
| sc:creator | 1.00 | CORRECT | No groundtruth available for comparison |
| sc:inLanguage | 1.00 | CORRECT | Exact match (case-insensitive) |
| cr:dataModality | 1.00 | CORRECT | No groundtruth available for comparison |
| rai:dataUseCases | 0.50 | PARTIALLY_CORRECT | The extracted value mentions training and image cl... |
| sc:datePublished | 0.33 | INCORRECT | The extracted value '2009' does not match the grou... |
| sc:description | 0.33 | PARTIALLY_CORRECT | The extracted value provides a general overview of... |
| rai:dataCollection | 0.33 | PARTIALLY_CORRECT | The extracted value provides some relevant informa... |
| sc:name | 0.33 | INCORRECT | Exact match (case-insensitive) |
| cr:citeAs | 0.33 | PARTIALLY_CORRECT | The extracted value includes the authors and year ... |
| rai:annotatorDemographics | 0.00 | MISSING | Field not extracted |
| Research | 0.00 | MISSING | Field not extracted |
| https: | 0.00 | MISSING | Field not extracted |
| sc:license | 0.00 | INCORRECT | The groundtruth value is 'NA', indicating that no ... |
| 2009 | 0.00 | MISSING | Field not extracted |
| sc:url | 0.00 | MISSING | The groundtruth value is not a valid URL and appea... |
| rai:dataAnnotationPlatform | 0.00 | MISSING | Field not extracted |
| rai:dataCollectionTimeframe | 0.00 | MISSING | Field not extracted |
| rai:personalSensitiveInformation | 0.00 | MISSING | Field not extracted |
| cr:isLiveDataset | 0.00 | MISSING | Field not extracted |
| Krizhevsky | 0.00 | MISSING | Field not extracted |

## Recommendations

Based on the evaluation results:
