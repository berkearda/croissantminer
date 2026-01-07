# CroissantMiner Evaluation Report

## Summary

- **Average Accuracy (0.8 threshold)**: 2.96%
- **Average Accuracy (0.6 threshold)**: 2.96%
- **Average Inter-Annotator Agreement**: 62.80%

## Results by Dataset

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
| rai:dataAnnotationPlatform | 0.00% | 0.00% | 0.00% | 0.00% |
| rai:personalSensitiveInformation | 0.00% | 0.00% | 0.00% | 0.00% |
| mls_eng_10k | 0.00% | 0.00% | 0.00% | 0.00% |
| al | 0.00% | 0.00% | 0.00% | 0.00% |
| Pratap | 0.00% | 0.00% | 0.00% | 0.00% |
| name | 0.00% | 0.00% | 0.00% | 0.00% |
| cr:isLiveDataset | 0.00% | 0.00% | 0.00% | 0.00% |
| rai:annotatorDemographics | 0.00% | 0.00% | 0.00% | 0.00% |
| @type | 0.00% | 0.00% | 0.00% | 0.00% |
| sc:name | 0.00% | 0.00% | 0.00% | 0.00% |
| https: | 0.00% | 0.00% | 0.00% | 0.00% |

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
| Steinhardt | 0.00% | 0.00% | 0.00% | 0.00% |
|  and | 0.00% | 0.00% | 0.00% | 0.00% |
| rai:dataCollectionTimeframe | 0.00% | 0.00% | 0.00% | 0.00% |
| rai:dataAnnotationPlatform | 0.00% | 0.00% | 0.00% | 0.00% |
| rai:personalSensitiveInformation | 0.00% | 0.00% | 0.00% | 0.00% |
| class. | 0.00% | 0.00% | 0.00% | 0.00% |
| ship | 0.00% | 0.00% | 0.00% | 0.00% |
| name | 0.00% | 0.00% | 0.00% | 0.00% |
| cr:isLiveDataset | 0.00% | 0.00% | 0.00% | 0.00% |
| Hinton | 0.00% | 0.00% | 0.00% | 0.00% |
| email | 0.00% | 0.00% | 0.00% | 0.00% |
| sc:url | 0.00% | 0.00% | 0.00% | 0.00% |
| sc:inLanguage | 0.00% | 0.00% | 0.00% | 0.00% |
| sc:name | 0.00% | 0.00% | 0.00% | 0.00% |
| ship, | 0.00% | 0.00% | 0.00% | 0.00% |

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
| sc:license | 0.00% | 0.00% | 0.00% | 0.00% |
| rai:dataCollectionTimeframe | 0.00% | 0.00% | 0.00% | 0.00% |
| rai:dataAnnotationPlatform | 0.00% | 0.00% | 0.00% | 0.00% |
| rai:personalSensitiveInformation | 0.00% | 0.00% | 0.00% | 0.00% |
| cr:citeAs | 0.00% | 0.00% | 0.00% | 0.00% |
| databricks/databricks-dolly-15k | 0.00% | 0.00% | 0.00% | 0.00% |
| name | 0.00% | 0.00% | 0.00% | 0.00% |
| cr:isLiveDataset | 0.00% | 0.00% | 0.00% | 0.00% |
| rai:annotatorDemographics | 0.00% | 0.00% | 0.00% | 0.00% |
| email | 0.00% | 0.00% | 0.00% | 0.00% |
| Databricks, Inc. | 0.00% | 0.00% | 0.00% | 0.00% |
| https: | 0.00% | 0.00% | 0.00% | 0.00% |
| affiliation | 0.00% | 0.00% | 0.00% | 0.00% |

### MSCOCO

**Overall Metrics:**

- Accuracy (0.8 threshold): 0.00%
- Accuracy (0.6 threshold): 0.00%
- Number of annotators: 3
- Fields evaluated: 21
- Avg inter-annotator agreement: 44.44%

**Field-Level Metrics:**

| Field Name | F1 Score | Precision | Recall | Exact Match Rate |
|------------|----------|-----------|--------|------------------|
| sc:datePublished | 33.33% | 33.33% | 33.33% | 33.33% |
| sc:description | 16.86% | 16.30% | 25.54% | 0.00% |
| rai:dataCollection | 16.34% | 50.00% | 17.41% | 0.00% |
| rai:dataUseCases | 16.06% | 14.81% | 25.76% | 0.00% |
| rai:annotatorDemographics | 10.03% | 12.96% | 12.67% | 0.00% |
| rai:dataCollectionTimeframe | 2.78% | 4.76% | 1.96% | 0.00% |
| sc:license | 0.00% | 0.00% | 0.00% | 0.00% |
| Tsung-Yi Lin Google Brain Genevieve Patterson MSR, Trash TV Matteo R. Ronchi Caltech Yin Cui Google Michael Maire TTI-Chicago Serge Belongie Cornell Tech Lubomir Bourdev WaveOne, Inc. Ross Girshick FAIR James Hays Georgia Tech Pietro Perona Caltech Deva Ramanan CMU Larry Zitnick FAIR Piotr Dollár FAIR | 0.00% | 0.00% | 0.00% | 0.00% |
| rai:dataAnnotationPlatform | 0.00% | 0.00% | 0.00% | 0.00% |
| rai:personalSensitiveInformation | 0.00% | 0.00% | 0.00% | 0.00% |
| COCO Consortium: Tsung-Yi Lin, Michael Maire, Serge Belongie, Lubomir Bourdev, Ross Girshick, James Hays, Pietro Perona, Deva Ramanan, C. Lawrence Zitnick, Piotr Dollar | 0.00% | 0.00% | 0.00% | 0.00% |
| cr:citeAs | 0.00% | 0.00% | 0.00% | 0.00% |
| yes | 0.00% | 0.00% | 0.00% | 0.00% |
| Coco | 0.00% | 0.00% | 0.00% | 0.00% |
| sc | 0.00% | 0.00% | 0.00% | 0.00% |
| al | 0.00% | 0.00% | 0.00% | 0.00% |
| cr:isLiveDataset | 0.00% | 0.00% | 0.00% | 0.00% |
| sc:url | 0.00% | 0.00% | 0.00% | 0.00% |
| sc:inLanguage | 0.00% | 0.00% | 0.00% | 0.00% |
| sc:name | 0.00% | 0.00% | 0.00% | 0.00% |
| https: | 0.00% | 0.00% | 0.00% | 0.00% |

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
| rai:dataUseCases | 26.67% | 18.18% | 50.00% | 0.00% |
| sc:name | 22.22% | 13.33% | 66.67% | 0.00% |
| sc:url | 20.45% | 16.67% | 30.00% | 0.00% |
| rai:dataCollection | 16.95% | 33.33% | 11.36% | 0.00% |
| rai:annotatorDemographics | 16.67% | 11.11% | 33.33% | 0.00% |
| sc:description | 9.32% | 14.41% | 6.91% | 0.00% |
| rai:dataCollectionTimeframe | 9.09% | 33.33% | 5.26% | 0.00% |
| cr:citeAs | 3.33% | 6.67% | 2.22% | 0.00% |
| sc:datePublished | 0.00% | 0.00% | 0.00% | 0.00% |
| sc:license | 0.00% | 0.00% | 0.00% | 0.00% |
| sc:creator | 0.00% | 0.00% | 0.00% | 0.00% |
| name | 0.00% | 0.00% | 0.00% | 0.00% |
| cr:isLiveDataset | 0.00% | 0.00% | 0.00% | 0.00% |
| sc:publisher | 0.00% | 0.00% | 0.00% | 0.00% |
| email | 0.00% | 0.00% | 0.00% | 0.00% |
| rai:dataAnnotationPlatform | 0.00% | 0.00% | 0.00% | 0.00% |

### CIFAR

**Overall Metrics:**

- Accuracy (0.8 threshold): 11.11%
- Accuracy (0.6 threshold): 11.11%
- Number of annotators: 3
- Fields evaluated: 18
- Avg inter-annotator agreement: 40.74%

**Field-Level Metrics:**

| Field Name | F1 Score | Precision | Recall | Exact Match Rate |
|------------|----------|-----------|--------|------------------|
| sc:inLanguage | 100.00% | 100.00% | 100.00% | 100.00% |
| sc:name | 33.33% | 33.33% | 33.33% | 33.33% |
| sc:datePublished | 25.00% | 50.00% | 16.67% | 0.00% |
| rai:dataUseCases | 22.58% | 14.04% | 58.33% | 0.00% |
| sc:url | 22.22% | 16.67% | 33.33% | 0.00% |
| rai:dataCollection | 19.48% | 41.67% | 13.13% | 0.00% |
| sc:description | 17.59% | 19.82% | 15.93% | 0.00% |
| cr:citeAs | 13.90% | 21.21% | 11.83% | 0.00% |
| sc:license | 8.33% | 16.67% | 5.56% | 0.00% |
| Research | 0.00% | 0.00% | 0.00% | 0.00% |
| rai:personalSensitiveInformation | 0.00% | 0.00% | 0.00% | 0.00% |
| Krizhevsky | 0.00% | 0.00% | 0.00% | 0.00% |
| 2009 | 0.00% | 0.00% | 0.00% | 0.00% |
| cr:isLiveDataset | 0.00% | 0.00% | 0.00% | 0.00% |
| rai:dataCollectionTimeframe | 0.00% | 0.00% | 0.00% | 0.00% |
| rai:annotatorDemographics | 0.00% | 0.00% | 0.00% | 0.00% |
| https: | 0.00% | 0.00% | 0.00% | 0.00% |
| rai:dataAnnotationPlatform | 0.00% | 0.00% | 0.00% | 0.00% |

## Recommendations

Based on the evaluation results:

### Fields Needing Improvement

- **url**: 0.00% average F1 score
- **rai:dataAnnotationPlatform**: 0.00% average F1 score
- **rai:personalSensitiveInformation**: 0.00% average F1 score
- **mls_eng_10k**: 0.00% average F1 score
- **al**: 0.00% average F1 score
