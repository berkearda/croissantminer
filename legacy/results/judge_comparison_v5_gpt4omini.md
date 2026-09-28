
# LLM Judge v5 — GPT-4o-mini Extractions vs Human GT

**Key difference from v1-v4:** GPT-4o-mini extractions genuinely differ from Claude-derived GT.
**50 cases from 8 benchmark datasets.** Expected: {2: 15, 1: 3, 3: 15}

## Agreement with Expected Ratings

| Judge | Exact Match | Overestimate | Underestimate | Cohen's κ |
|-------|-------------|-------------|---------------|-----------|
| GPT-4o-mini | 25/31 (81%) | 3 | 3 | 0.664 |
| GPT-4o | 22/33 (67%) | 7 | 4 | 0.455 |
| GPT-5.4 | 25/33 (76%) | 7 | 1 | 0.617 |
| Claude 4.5 | 23/33 (70%) | 7 | 3 | 0.505 |

## Stratified Accuracy

| Judge | Expected=Correct | Expected=Partial | Expected=Incorrect |
|-------|-----------------|------------------|-------------------|
| GPT-4o-mini | 0/3 (0%) | 14/15 (93%) | 11/13 (85%) |
| GPT-4o | 0/3 (0%) | 13/15 (87%) | 9/15 (60%) |
| GPT-5.4 | 2/3 (67%) | 14/15 (93%) | 9/15 (60%) |
| Claude 4.5 | 0/3 (0%) | 14/15 (93%) | 9/15 (60%) |

## Partial Detection Detail

Cases where GPT-4o-mini partially matches GT (n=15):

| # | Dataset | Field | GPT-mini | GPT-4o | GPT-5.4 | Claude |
|---|---------|-------|----------|--------|---------|--------|
| 1 | MLS | creator | 2 | 2 | 2 | 2 |
| 3 | FLORES | description | 2 | 2 | 2 | 2 |
| 8 | FLORES | datePublished | 2 | 2 | 2 | 2 |
| 12 | MMLU | creator | 2 | 3 | 2 | 2 |
| 13 | MSCOCO | rai:dataAnnotationProt | 2 | 2 | 2 | 2 |
| 15 | MathVista | citeAs | 2 | 2 | 2 | 2 |
| 16 | MLS | description | 2 | 2 | 2 | 2 |
| 17 | FLORES | rai:dataSocialImpact | 2 | 2 | 2 | 2 |
| 18 | MathVista | creator | 2 | 1 | 2 | 2 |
| 19 | MLS | citeAs | 2 | 2 | 2 | 2 |
| 20 | MMMU | rai:annotationsPerItem | 1 | 2 | 1 | 1 |
| 22 | MSCOCO | description | 2 | 2 | 2 | 2 |
| 25 | MMLU | publisher | 2 | 2 | 2 | 2 |
| 27 | FLORES | citeAs | 2 | 2 | 2 | 2 |
| 32 | Visual Genom | citeAs | 2 | 2 | 2 | 2 |

**Partial detection: 55/60 (92% across all judges)**

## Comparison Across All Experiments

| Experiment | What was judged | Partial Detection | Overall Match |
|-----------|----------------|-------------------|--------------|
| v1-v4 | Claude ext vs Claude-derived GT | 0/24 (0%) | 84-88% |
| **v5** | **GPT-4o-mini ext vs human GT** | **55/60 (92%)** | **95/130 (73%)** |

## Conclusion

**The judge CAN detect Partially Correct when extractions genuinely differ from GT.**
v1-v4's 0% was an artifact of circular evaluation (same text on both sides).
For cross-model comparison in the paper, the LLM judge is viable.