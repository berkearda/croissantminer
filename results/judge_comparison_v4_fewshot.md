
# LLM Judge Comparison v4 — Few-Shot 3-Point Scale

**Hypothesis:** Adding 7 annotated examples (2 Correct, 3 Partial, 2 Incorrect) teaches judges to detect Partially Correct cases.

## Agreement with Human Ratings

| Judge | Exact Match | Overestimate | Underestimate |
|-------|-------------|-------------|---------------|
| GPT-4o-mini | 42/50 (84%) | 7 | 1 |
| GPT-4o | 44/50 (88%) | 6 | 0 |
| GPT-5.4 | 44/50 (88%) | 6 | 0 |
| Claude 4.5 | 44/50 (88%) | 6 | 0 |

## Stratified Accuracy

| Judge | Correct (n=41) | Partial (n=6) | Incorrect (n=3) |
|-------|----------------|---------------|-----------------|
| GPT-4o-mini | 40/41 (98%) | 0/6 (0%) | 2/3 (67%) |
| GPT-4o | 41/41 (100%) | 0/6 (0%) | 3/3 (100%) |
| GPT-5.4 | 41/41 (100%) | 0/6 (0%) | 3/3 (100%) |
| Claude 4.5 | 41/41 (100%) | 0/6 (0%) | 3/3 (100%) |

## v3 (Zero-Shot) vs v4 (Few-Shot) Comparison

| Judge | v3 Agreement | v4 Agreement | v3 Partial | v4 Partial | Improved? |
|-------|-------------|-------------|------------|------------|-----------|
| GPT-4o-mini | 42/50 (84%) | 42/50 (84%) | 0/6 | 0/6 | NO |
| GPT-4o | 44/50 (88%) | 44/50 (88%) | 0/6 | 0/6 | NO |
| GPT-5.4 | 44/50 (88%) | 44/50 (88%) | 0/6 | 0/6 | NO |
| Claude 4.5 | 44/50 (88%) | 44/50 (88%) | 0/6 | 0/6 | NO |

## The 6 Partially Correct Cases — Few-Shot Results

| # | Dataset | Field | Human | GPT-4o-mini | GPT-4o | GPT-5.4 | Claude |
|---|---------|-------|-------|-------------|--------|---------|--------|
| 4 | MohamedRashad_arabic-b | rai:dataSocialImpact | 2 | 1 | 1 | 1 | 1 |
| 15 | SWE-Gym_SWE-Gym | rai:dataAnnotationAnal | 2 | 1 | 1 | 1 | 1 |
| 17 | Idavidrein_gpqa | rai:dataCollectionRawD | 2 | 1 | 1 | 1 | 1 |
| 22 | allenai_openbookqa | description | 2 | 1 | 1 | 1 | 1 |
| 27 | hiyouga_math12k | rai:dataSocialImpact | 2 | 1 | 1 | 1 | 1 |
| 47 | ScaleAI_SWE-bench_Pro | creator | 2 | 1 | 1 | 1 | 1 |

**Partially Correct detection: 0/24**
**v3 (zero-shot): 0/24, v4 (few-shot): 0/24**