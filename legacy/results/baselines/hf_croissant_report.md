# HuggingFace Auto-Croissant vs CroissantMiner

## Summary (lenient — includes null-null matches)

| Method | General (10) | RAI (20) | Overall (30) |
|--------|-------------|---------|-------------|
| HF Auto-Croissant | 21.2% | 40.6% | 34.2% |
| **CroissantMiner** | **81.2%** | **66.9%** | **71.7%** |
| Delta | +60.0pp | +26.2pp | +37.5pp |

## Strict Evaluation (only fields where ground truth has a non-null value)

| Method | General (strict) | RAI (strict) | Overall (strict) | Avg fields filled |
|--------|-----------------|-------------|-----------------|-------------------|
| HF Auto-Croissant | 11.7% | 0.0% | 4.2% | 4.9/30 |
| **CroissantMiner** | **76.0%** | **45.6%** | **56.4%** | **18.2/30** |
| Delta | +64.3pp | +45.6pp | +52.2pp | +13.4 |

## Key Finding

HuggingFace auto-generates basic structural metadata (name, URL, license) but provides
**zero RAI metadata**. CroissantMiner extracts 45.6% of RAI fields from papers
(strict evaluation) — information that HF's automated system cannot access because it only
reads dataset cards, not the academic papers that describe collection methodology, biases,
and limitations.

## Per-Field Comparison

| Field | HF Auto | CroissantMiner | Delta |
|-------|---------|---------------|-------|
| sc:name | 50.0% | 100.0% | +50.0pp |
| sc:description | 0.0% | 93.8% | +93.8pp |
| sc:url | 0.0% | 87.5% | +87.5pp |
| sc:license | 37.5% | 62.5% | +25.0pp |
| sc:creator | 12.5% | 93.8% | +81.2pp |
| sc:publisher | 25.0% | 87.5% | +62.5pp |
| sc:datePublished | 25.0% | 87.5% | +62.5pp |
| sc:inLanguage | 25.0% | 87.5% | +62.5pp |
| cr:citeAs | 12.5% | 50.0% | +37.5pp |
| cr:isLiveDataset | 25.0% | 62.5% | +37.5pp |
| rai:dataCollection | 12.5% | 62.5% | +50.0pp |
| rai:dataCollectionType | 0.0% | 50.0% | +50.0pp |
| rai:dataCollectionMissingData | 100.0% | 100.0% | +0.0pp |
| rai:dataCollectionRawData | 0.0% | 56.2% | +56.2pp |
| rai:dataCollectionTimeframe | 37.5% | 100.0% | +62.5pp |
| rai:dataImputationProtocol | 100.0% | 100.0% | +0.0pp |
| rai:dataManipulationProtocol | 50.0% | 50.0% | +0.0pp |
| rai:dataPreprocessingProtocol | 0.0% | 43.8% | +43.8pp |
| rai:dataAnnotationProtocol | 25.0% | 50.0% | +25.0pp |
| rai:dataAnnotationPlatform | 37.5% | 62.5% | +25.0pp |
| rai:dataAnnotationAnalysis | 37.5% | 56.2% | +18.8pp |
| rai:annotationsPerItem | 50.0% | 68.8% | +18.8pp |
| rai:annotatorDemographics | 37.5% | 56.2% | +18.8pp |
| rai:machineAnnotationTools | 62.5% | 75.0% | +12.5pp |
| rai:dataReleaseMaintenancePlan | 50.0% | 56.2% | +6.2pp |
| rai:personalSensitiveInformation | 37.5% | 62.5% | +25.0pp |
| rai:dataSocialImpact | 62.5% | 81.2% | +18.8pp |
| rai:dataBiases | 62.5% | 75.0% | +12.5pp |
| rai:dataLimitations | 12.5% | 50.0% | +37.5pp |
| rai:dataUseCases | 37.5% | 81.2% | +43.8pp |

## Datasets Evaluated

8 benchmark datasets from the CroissantMiner evaluation suite.
HF dataset IDs: {
  "MLS": "facebook/multilingual_librispeech",
  "MMLU": "cais/mmlu",
  "FLORES": "facebook/flores",
  "CIFAR": "uoft-cs/cifar10",
  "MSCOCO": "detection-datasets/coco",
  "MMMU": "MMMU/MMMU",
  "Visual Genome": "ranjaykrishna/visual_genome",
  "MathVista": "AI4Math/MathVista"
}
