# Field-Type-Aware Evaluation Results

## Main Comparison

| Method | Constrained (EM) | Short-text (F1) | RAI (Judge 1-5) | Composite |
|--------|-----------------|----------------|----------------|-----------|
| Claude Sonnet 4.5 | 54.9% (n=51) | 0.502 (n=24) | 2.59/5 (n=87) | 49.4% |
| GPT-4o-mini | 39.2% (n=51) | 0.328 (n=24) | 1.67/5 (n=87) | 31.3% |
| HF Auto-Croissant | 21.6% (n=51) | 0.137 (n=24) | 0.00/5 (n=87) | 8.8% |

## Per-Dataset Composite Scores

| Dataset | Claude Sonnet 4.5 | GPT-4o-mini | HF Auto-Croissant |
|---------|------|------|------|
| CIFAR | 28.7% | 21.6% | 6.3% |
| FLORES | 37.9% | 32.3% | 8.5% |
| MLS | 48.5% | 28.6% | 7.2% |
| MMLU | 57.5% | 34.0% | 10.9% |
| MMMU | 52.6% | 35.6% | 10.9% |
| MSCOCO | 49.2% | 22.8% | 6.6% |
| MathVista | 62.8% | 39.9% | 8.2% |
| Visual Genome | 51.6% | 30.2% | 11.4% |

## Per-Field Breakdown (Claude Sonnet 4.5)

| Field | Category | Metric | Score | n |
|-------|----------|--------|-------|---|
| sc:name | constrained | EM | 1.000 | 8 |
| sc:license | constrained | EM | 0.000 | 7 |
| sc:inLanguage | constrained | EM | 0.833 | 6 |
| cr:isLiveDataset | constrained | EM | 0.500 | 6 |
| sc:datePublished | constrained | EM | 0.750 | 8 |
| sc:publisher | constrained | EM | 0.250 | 8 |
| sc:url | constrained | EM | 0.500 | 8 |
| sc:creator | short_text | F1 | 0.482 | 8 |
| cr:citeAs | short_text | F1 | 0.530 | 8 |
| sc:description | short_text | F1 | 0.494 | 8 |
| rai:dataCollection | rai | Judge | 0.357 | 7 |
| rai:dataCollectionType | rai | Judge | 0.531 | 8 |
| rai:dataCollectionRawData | rai | Judge | 0.562 | 8 |
| rai:dataCollectionTimeframe | rai | Judge | 0.000 | 2 |
| rai:dataManipulationProtocol | rai | Judge | 0.000 | 4 |
| rai:dataPreprocessingProtocol | rai | Judge | 0.688 | 8 |
| rai:dataAnnotationProtocol | rai | Judge | 0.667 | 6 |
| rai:dataAnnotationPlatform | rai | Judge | 0.083 | 3 |
| rai:dataAnnotationAnalysis | rai | Judge | 0.550 | 5 |
| rai:annotationsPerItem | rai | Judge | 0.438 | 4 |
| rai:annotatorDemographics | rai | Judge | 0.300 | 5 |
| rai:machineAnnotationTools | rai | Judge | 0.583 | 3 |
| rai:dataReleaseMaintenancePlan | rai | Judge | 0.188 | 4 |
| rai:personalSensitiveInformation | rai | Judge | 0.000 | 2 |
| rai:dataSocialImpact | rai | Judge | 0.750 | 3 |
| rai:dataBiases | rai | Judge | 0.500 | 3 |
| rai:dataLimitations | rai | Judge | 0.571 | 7 |
| rai:dataUseCases | rai | Judge | 0.550 | 5 |