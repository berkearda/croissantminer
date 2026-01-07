# CroissantMiner Evaluation Report

## Summary

- **Average Accuracy (0.8 threshold)**: 1.53%
- **Average Accuracy (0.6 threshold)**: 1.53%
- **Average Inter-Annotator Agreement**: 59.23%

## Results by Dataset

### LibriSpeech

**Overall Metrics:**

- Accuracy (0.8 threshold): 0.00%
- Accuracy (0.6 threshold): 0.00%
- Number of annotators: 3
- Fields evaluated: 20
- Avg inter-annotator agreement: 55.00%

**Field-Level Metrics:**

| Field Name | F1 Score | Precision | Recall | Exact Match Rate |
|------------|----------|-----------|--------|------------------|
| sc:description | 15.02% | 12.59% | 18.79% | 0.00% |
| rai:dataCollection | 10.13% | 8.33% | 12.92% | 0.00% |
| rai:dataUseCases | 4.17% | 2.78% | 8.33% | 0.00% |
| Povey | 0.00% | 0.00% | 0.00% | 0.00% |
| sc:datePublished | 0.00% | 0.00% | 0.00% | 0.00% |
| cr:isLiveDataset | 0.00% | 0.00% | 0.00% | 0.00% |
| @type | 0.00% | 0.00% | 0.00% | 0.00% |
| sc:license | 0.00% | 0.00% | 0.00% | 0.00% |
| al. | 0.00% | 0.00% | 0.00% | 0.00% |
| rai:dataAnnotationPlatform | 0.00% | 0.00% | 0.00% | 0.00% |
| sc:url | 0.00% | 0.00% | 0.00% | 0.00% |
| rai:dataCollectionTimeframe | 0.00% | 0.00% | 0.00% | 0.00% |
| rai:annotatorDemographics | 0.00% | 0.00% | 0.00% | 0.00% |
| sc:name | 0.00% | 0.00% | 0.00% | 0.00% |
| rai:personalSensitiveInformation | 0.00% | 0.00% | 0.00% | 0.00% |
| librispeech_asr | 0.00% | 0.00% | 0.00% | 0.00% |
| sc:inLanguage | 0.00% | 0.00% | 0.00% | 0.00% |
| https: | 0.00% | 0.00% | 0.00% | 0.00% |
| cr:citeAs | 0.00% | 0.00% | 0.00% | 0.00% |
| name | 0.00% | 0.00% | 0.00% | 0.00% |

### MLS

**Overall Metrics:**

- Accuracy (0.8 threshold): 6.67%
- Accuracy (0.6 threshold): 6.67%
- Number of annotators: 3
- Fields evaluated: 20
- Avg inter-annotator agreement: 68.25%

**Field-Level Metrics:**

| Field Name | F1 Score | Precision | Recall | Exact Match Rate |
|------------|----------|-----------|--------|------------------|
| sc:inLanguage | 61.11% | 100.00% | 56.25% | 50.00% |
| sc:datePublished | 50.00% | 50.00% | 50.00% | 0.00% |
| sc:description | 29.11% | 31.06% | 27.78% | 0.00% |
| sc:url | 25.00% | 20.00% | 33.33% | 0.00% |
| rai:dataCollection | 17.48% | 15.52% | 20.19% | 0.00% |
| rai:dataUseCases | 11.14% | 8.33% | 17.14% | 0.00% |
| sc:license | 10.26% | 33.33% | 6.06% | 0.00% |
| cr:citeAs | 6.25% | 6.25% | 6.25% | 0.00% |
| url | 0.00% | 0.00% | 0.00% | 0.00% |
| al | 0.00% | 0.00% | 0.00% | 0.00% |
| cr:isLiveDataset | 0.00% | 0.00% | 0.00% | 0.00% |
| Pratap | 0.00% | 0.00% | 0.00% | 0.00% |
| @type | 0.00% | 0.00% | 0.00% | 0.00% |
| rai:dataAnnotationPlatform | 0.00% | 0.00% | 0.00% | 0.00% |
| mls_eng_10k | 0.00% | 0.00% | 0.00% | 0.00% |
| rai:annotatorDemographics | 0.00% | 0.00% | 0.00% | 0.00% |
| sc:name | 0.00% | 0.00% | 0.00% | 0.00% |
| rai:personalSensitiveInformation | 0.00% | 0.00% | 0.00% | 0.00% |
| https: | 0.00% | 0.00% | 0.00% | 0.00% |
| name | 0.00% | 0.00% | 0.00% | 0.00% |

### MMLU

**Overall Metrics:**

- Accuracy (0.8 threshold): 0.00%
- Accuracy (0.6 threshold): 0.00%
- Number of annotators: 3
- Fields evaluated: 22
- Avg inter-annotator agreement: 50.00%

**Field-Level Metrics:**

| Field Name | F1 Score | Precision | Recall | Exact Match Rate |
|------------|----------|-----------|--------|------------------|
| sc:datePublished | 33.33% | 50.00% | 25.00% | 0.00% |
| sc:license | 33.33% | 33.33% | 33.33% | 33.33% |
| sc:description | 24.93% | 27.13% | 24.82% | 0.00% |
| rai:annotatorDemographics | 20.00% | 12.50% | 50.00% | 0.00% |
| rai:dataUseCases | 15.20% | 15.38% | 23.11% | 0.00% |
| rai:dataCollection | 13.33% | 13.79% | 14.15% | 0.00% |
| cr:citeAs | 1.92% | 12.50% | 1.04% | 0.00% |
| cr:isLiveDataset | 0.00% | 0.00% | 0.00% | 0.00% |
| ship | 0.00% | 0.00% | 0.00% | 0.00% |
| ship, | 0.00% | 0.00% | 0.00% | 0.00% |
| rai:dataAnnotationPlatform | 0.00% | 0.00% | 0.00% | 0.00% |
| sc:url | 0.00% | 0.00% | 0.00% | 0.00% |
| Hinton | 0.00% | 0.00% | 0.00% | 0.00% |
| class. | 0.00% | 0.00% | 0.00% | 0.00% |
| rai:dataCollectionTimeframe | 0.00% | 0.00% | 0.00% | 0.00% |
| Steinhardt | 0.00% | 0.00% | 0.00% | 0.00% |
| sc:name | 0.00% | 0.00% | 0.00% | 0.00% |
| rai:personalSensitiveInformation | 0.00% | 0.00% | 0.00% | 0.00% |
| email | 0.00% | 0.00% | 0.00% | 0.00% |
| sc:inLanguage | 0.00% | 0.00% | 0.00% | 0.00% |
|  and | 0.00% | 0.00% | 0.00% | 0.00% |
| name | 0.00% | 0.00% | 0.00% | 0.00% |

### FLORES

**Overall Metrics:**

- Accuracy (0.8 threshold): 0.00%
- Accuracy (0.6 threshold): 0.00%
- Number of annotators: 2
- Fields evaluated: 20
- Avg inter-annotator agreement: 90.00%

**Field-Level Metrics:**

| Field Name | F1 Score | Precision | Recall | Exact Match Rate |
|------------|----------|-----------|--------|------------------|
| sc:description | 17.38% | 26.83% | 13.22% | 0.00% |
| sc:url | 14.29% | 11.11% | 20.00% | 0.00% |
| sc:inLanguage | 14.29% | 8.33% | 50.00% | 0.00% |
| sc:name | 13.33% | 50.00% | 7.69% | 0.00% |
| rai:dataUseCases | 12.61% | 30.43% | 7.95% | 0.00% |
| rai:dataCollection | 9.94% | 26.67% | 6.11% | 0.00% |
| sc:datePublished | 0.00% | 0.00% | 0.00% | 0.00% |
| cr:isLiveDataset | 0.00% | 0.00% | 0.00% | 0.00% |
| sc:license | 0.00% | 0.00% | 0.00% | 0.00% |
| rai:dataAnnotationPlatform | 0.00% | 0.00% | 0.00% | 0.00% |
| databricks/databricks-dolly-15k | 0.00% | 0.00% | 0.00% | 0.00% |
| Databricks, Inc. | 0.00% | 0.00% | 0.00% | 0.00% |
| rai:dataCollectionTimeframe | 0.00% | 0.00% | 0.00% | 0.00% |
| affiliation | 0.00% | 0.00% | 0.00% | 0.00% |
| rai:annotatorDemographics | 0.00% | 0.00% | 0.00% | 0.00% |
| rai:personalSensitiveInformation | 0.00% | 0.00% | 0.00% | 0.00% |
| email | 0.00% | 0.00% | 0.00% | 0.00% |
| https: | 0.00% | 0.00% | 0.00% | 0.00% |
| cr:citeAs | 0.00% | 0.00% | 0.00% | 0.00% |
| name | 0.00% | 0.00% | 0.00% | 0.00% |

### CIFAR

**Overall Metrics:**

- Accuracy (0.8 threshold): 0.00%
- Accuracy (0.6 threshold): 0.00%
- Number of annotators: 3
- Fields evaluated: 18
- Avg inter-annotator agreement: 40.74%

**Field-Level Metrics:**

| Field Name | F1 Score | Precision | Recall | Exact Match Rate |
|------------|----------|-----------|--------|------------------|
| sc:license | 33.33% | 33.33% | 33.33% | 33.33% |
| sc:url | 33.33% | 33.33% | 33.33% | 0.00% |
| sc:datePublished | 25.00% | 25.00% | 25.00% | 0.00% |
| rai:dataCollection | 21.20% | 41.67% | 14.75% | 0.00% |
| sc:description | 17.66% | 17.39% | 18.11% | 0.00% |
| rai:dataUseCases | 8.21% | 4.76% | 30.00% | 0.00% |
| cr:citeAs | 0.00% | 0.00% | 0.00% | 0.00% |
| rai:dataCollectionTimeframe | 0.00% | 0.00% | 0.00% | 0.00% |
| 2009 | 0.00% | 0.00% | 0.00% | 0.00% |
| sc:inLanguage | 0.00% | 0.00% | 0.00% | 0.00% |
| https: | 0.00% | 0.00% | 0.00% | 0.00% |
| rai:personalSensitiveInformation | 0.00% | 0.00% | 0.00% | 0.00% |
| rai:dataAnnotationPlatform | 0.00% | 0.00% | 0.00% | 0.00% |
| cr:isLiveDataset | 0.00% | 0.00% | 0.00% | 0.00% |
| Krizhevsky | 0.00% | 0.00% | 0.00% | 0.00% |
| rai:annotatorDemographics | 0.00% | 0.00% | 0.00% | 0.00% |
| sc:name | 0.00% | 0.00% | 0.00% | 0.00% |
| Research | 0.00% | 0.00% | 0.00% | 0.00% |

### DOLLY

**Overall Metrics:**

- Accuracy (0.8 threshold): 0.00%
- Accuracy (0.6 threshold): 0.00%
- Number of annotators: 3
- Fields evaluated: 19
- Avg inter-annotator agreement: 42.11%

**Field-Level Metrics:**

| Field Name | F1 Score | Precision | Recall | Exact Match Rate |
|------------|----------|-----------|--------|------------------|
| sc:url | 28.57% | 25.00% | 33.33% | 0.00% |
| rai:dataCollection | 15.57% | 24.44% | 12.04% | 0.00% |
| sc:description | 14.54% | 15.00% | 15.92% | 0.00% |
| rai:dataUseCases | 11.50% | 15.56% | 11.25% | 0.00% |
| rai:annotatorDemographics | 2.38% | 1.67% | 4.17% | 0.00% |
| cr:citeAs | 1.93% | 8.33% | 1.09% | 0.00% |
| sc:datePublished | 0.00% | 0.00% | 0.00% | 0.00% |
| cr:isLiveDataset | 0.00% | 0.00% | 0.00% | 0.00% |
| Waterloo, | 0.00% | 0.00% | 0.00% | 0.00% |
| sc:license | 0.00% | 0.00% | 0.00% | 0.00% |
| Databricks | 0.00% | 0.00% | 0.00% | 0.00% |
| rai:dataAnnotationPlatform | 0.00% | 0.00% | 0.00% | 0.00% |
| rai:dataCollectionTimeframe | 0.00% | 0.00% | 0.00% | 0.00% |
| sc:name | 0.00% | 0.00% | 0.00% | 0.00% |
| rai:personalSensitiveInformation | 0.00% | 0.00% | 0.00% | 0.00% |
| 12/21/2023 | 0.00% | 0.00% | 0.00% | 0.00% |
| databricks | 0.00% | 0.00% | 0.00% | 0.00% |
| sc:inLanguage | 0.00% | 0.00% | 0.00% | 0.00% |
| https: | 0.00% | 0.00% | 0.00% | 0.00% |

### MSCOCO

**Overall Metrics:**

- Accuracy (0.8 threshold): 5.56%
- Accuracy (0.6 threshold): 5.56%
- Number of annotators: 3
- Fields evaluated: 21
- Avg inter-annotator agreement: 44.44%

**Field-Level Metrics:**

| Field Name | F1 Score | Precision | Recall | Exact Match Rate |
|------------|----------|-----------|--------|------------------|
| sc:inLanguage | 66.67% | 66.67% | 66.67% | 66.67% |
| sc:datePublished | 27.78% | 22.22% | 44.44% | 0.00% |
| sc:url | 25.40% | 16.67% | 66.67% | 0.00% |
| cr:citeAs | 14.34% | 33.33% | 9.14% | 0.00% |
| sc:description | 7.73% | 9.01% | 10.06% | 0.00% |
| rai:dataCollection | 7.69% | 21.67% | 8.86% | 0.00% |
| rai:dataUseCases | 7.58% | 7.58% | 7.58% | 0.00% |
| rai:annotatorDemographics | 1.08% | 3.70% | 0.63% | 0.00% |
| Tsung-Yi Lin Google Brain Genevieve Patterson MSR, Trash TV Matteo R. Ronchi Caltech Yin Cui Google Michael Maire TTI-Chicago Serge Belongie Cornell Tech Lubomir Bourdev WaveOne, Inc. Ross Girshick FAIR James Hays Georgia Tech Pietro Perona Caltech Deva Ramanan CMU Larry Zitnick FAIR Piotr Dollár FAIR | 0.00% | 0.00% | 0.00% | 0.00% |
| al | 0.00% | 0.00% | 0.00% | 0.00% |
| cr:isLiveDataset | 0.00% | 0.00% | 0.00% | 0.00% |
| sc:license | 0.00% | 0.00% | 0.00% | 0.00% |
| sc | 0.00% | 0.00% | 0.00% | 0.00% |
| rai:dataAnnotationPlatform | 0.00% | 0.00% | 0.00% | 0.00% |
| rai:dataCollectionTimeframe | 0.00% | 0.00% | 0.00% | 0.00% |
| sc:name | 0.00% | 0.00% | 0.00% | 0.00% |
| rai:personalSensitiveInformation | 0.00% | 0.00% | 0.00% | 0.00% |
| COCO Consortium: Tsung-Yi Lin, Michael Maire, Serge Belongie, Lubomir Bourdev, Ross Girshick, James Hays, Pietro Perona, Deva Ramanan, C. Lawrence Zitnick, Piotr Dollar | 0.00% | 0.00% | 0.00% | 0.00% |
| https: | 0.00% | 0.00% | 0.00% | 0.00% |
| yes | 0.00% | 0.00% | 0.00% | 0.00% |
| Coco | 0.00% | 0.00% | 0.00% | 0.00% |

### MMMU

**Overall Metrics:**

- Accuracy (0.8 threshold): 0.00%
- Accuracy (0.6 threshold): 0.00%
- Number of annotators: 3
- Fields evaluated: 17
- Avg inter-annotator agreement: 83.33%

**Field-Level Metrics:**

| Field Name | F1 Score | Precision | Recall | Exact Match Rate |
|------------|----------|-----------|--------|------------------|
| sc:inLanguage | 50.00% | 100.00% | 33.33% | 0.00% |
| rai:dataUseCases | 22.22% | 15.79% | 37.50% | 0.00% |
| sc:url | 20.45% | 16.67% | 30.00% | 0.00% |
| sc:description | 17.37% | 27.03% | 12.84% | 0.00% |
| rai:dataCollection | 13.79% | 28.57% | 9.09% | 0.00% |
| sc:license | 11.11% | 16.67% | 8.33% | 0.00% |
| cr:citeAs | 3.57% | 9.09% | 2.22% | 0.00% |
| email | 0.00% | 0.00% | 0.00% | 0.00% |
| rai:dataCollectionTimeframe | 0.00% | 0.00% | 0.00% | 0.00% |
| sc:publisher | 0.00% | 0.00% | 0.00% | 0.00% |
| sc:creator | 0.00% | 0.00% | 0.00% | 0.00% |
| name | 0.00% | 0.00% | 0.00% | 0.00% |
| rai:dataAnnotationPlatform | 0.00% | 0.00% | 0.00% | 0.00% |
| sc:datePublished | 0.00% | 0.00% | 0.00% | 0.00% |
| cr:isLiveDataset | 0.00% | 0.00% | 0.00% | 0.00% |
| rai:annotatorDemographics | 0.00% | 0.00% | 0.00% | 0.00% |
| sc:name | 0.00% | 0.00% | 0.00% | 0.00% |

## Recommendations

Based on the evaluation results:

### Fields Needing Improvement

- **Povey**: 0.00% average F1 score
- **cr:isLiveDataset**: 0.00% average F1 score
- **@type**: 0.00% average F1 score
- **al.**: 0.00% average F1 score
- **rai:dataAnnotationPlatform**: 0.00% average F1 score
