# CroissantMiner Evaluation Results

## Main Comparison

| Strategy | Constrained (EM) | Short-text | RAI | Composite [95% CI] | N |
|----------|-----------------|------------|-----|-------------------|---|
| claude_sonnet | 54.9% (n=51) | 38.9% (n=24) | 5.5% (n=87) | 26.0% [20.0, 32.1] | 162 |

## Null Handling

| Strategy | Miss (GT has, pred null) | Skip (no GT) | Non-null |
|----------|------------------------|-------------|----------|
| claude_sonnet | 63 | 78 | 99 |

## Per-Field Breakdown (claude_sonnet)

| Field | Category | Score | N |
|-------|----------|-------|---|
| sc:name | constrained | 100.0% | 8 |
| sc:license | constrained | 0.0% | 7 |
| sc:inLanguage | constrained | 83.3% | 6 |
| cr:isLiveDataset | constrained | 50.0% | 6 |
| sc:datePublished | constrained | 75.0% | 8 |
| sc:publisher | constrained | 25.0% | 8 |
| sc:url | constrained | 50.0% | 8 |
| sc:creator | short_text | 9.2% | 8 |
| cr:citeAs | short_text | 61.0% | 8 |
| sc:description | short_text | 46.6% | 8 |
| rai:dataCollection | rai | 21.1% | 7 |
| rai:dataCollectionType | rai | 0.0% | 8 |
| rai:dataCollectionRawData | rai | 0.0% | 8 |
| rai:dataCollectionTimeframe | rai | 0.0% | 2 |
| rai:dataManipulationProtocol | rai | 0.0% | 4 |
| rai:dataPreprocessingProtocol | rai | 0.0% | 8 |
| rai:dataAnnotationProtocol | rai | 0.0% | 6 |
| rai:dataAnnotationPlatform | rai | 18.5% | 3 |
| rai:dataAnnotationAnalysis | rai | 0.0% | 5 |
| rai:annotationsPerItem | rai | 0.0% | 4 |
| rai:annotatorDemographics | rai | 29.0% | 5 |
| rai:machineAnnotationTools | rai | 0.0% | 3 |
| rai:dataReleaseMaintenancePlan | rai | 0.0% | 4 |
| rai:personalSensitiveInformation | rai | 17.9% | 2 |
| rai:dataSocialImpact | rai | 0.0% | 3 |
| rai:dataBiases | rai | 0.0% | 3 |
| rai:dataLimitations | rai | 0.0% | 7 |
| rai:dataUseCases | rai | 19.4% | 5 |