# LLM Judge Comparison v3 — 3-Point Scale (Direct)

**Hypothesis:** Giving judges the same 3-point scale as human annotators (instead of 5-point mapped to 3) improves Partially Correct detection.

**Same 50 cases as v2**, seed=42. Distribution: Correct=41, Partial=6, Incorrect=3

## Agreement with Human Ratings

| Judge | Exact Match | Overestimate | Underestimate | Cohen's κ | Spearman ρ |
|-------|-------------|-------------|---------------|-----------|------------|
| GPT-4o-mini | 42/50 (84%) | 7 | 1 | 0.329 | 0.512 |
| GPT-4o | 44/50 (88%) | 6 | 0 | 0.468 | 0.615 |
| GPT-5.4 | 44/50 (88%) | 6 | 0 | 0.468 | 0.615 |
| Claude Sonnet 4.5 | 44/50 (88%) | 6 | 0 | 0.468 | 0.615 |

## Accuracy Stratified by Human Rating

| Judge | On Correct (n=41) | On Partial (n=6) | On Incorrect (n=3) |
|-------|-------------------|------------------|-------------------|
| GPT-4o-mini | 40/41 (98%) | 0/6 (0%) | 2/3 (67%) |
| GPT-4o | 41/41 (100%) | 0/6 (0%) | 3/3 (100%) |
| GPT-5.4 | 41/41 (100%) | 0/6 (0%) | 3/3 (100%) |
| Claude Sonnet 4.5 | 41/41 (100%) | 0/6 (0%) | 3/3 (100%) |

## v2 (5-point mapped) vs v3 (3-point direct) Comparison

| Judge | v2 Agreement | v3 Agreement | v2 Partial Acc | v3 Partial Acc | Improved? |
|-------|-------------|-------------|----------------|----------------|-----------|
| GPT-4o-mini | 44/50 (88%) | 42/50 (84%) | 0/6 (0%) | 0/6 (0%) | NO |
| GPT-4o | 44/50 (88%) | 44/50 (88%) | 0/6 (0%) | 0/6 (0%) | NO |
| GPT-5.4 | 44/50 (88%) | 44/50 (88%) | 0/6 (0%) | 0/6 (0%) | NO |
| Claude Sonnet 4.5 | 41/49 (84%) | 44/50 (88%) | 0/6 (0%) | 0/6 (0%) | NO |

## Detail: The 6 Partially Correct Cases

| # | Dataset | Field | Human | v2 GPT-4o | v3 GPT-4o | v3 GPT-5.4 | v3 Claude |
|---|---------|-------|-------|-----------|-----------|------------|-----------|
| 4 | MohamedRashad_arabic-book | rai:dataSocialImpact | 2 | 1 | 1 | 1 | 1 |
| 15 | SWE-Gym_SWE-Gym | rai:dataAnnotationAnalysi | 2 | 1 | 1 | 1 | 1 |
| 17 | Idavidrein_gpqa | rai:dataCollectionRawData | 2 | 1 | 1 | 1 | 1 |
| 22 | allenai_openbookqa | description | 2 | 1 | 1 | 1 | 1 |
| 27 | hiyouga_math12k | rai:dataSocialImpact | 2 | 1 | 1 | 1 | 1 |
| 47 | ScaleAI_SWE-bench_Pro | creator | 2 | 1 | 1 | 1 | 1 |

## Conclusion

**Partially Correct detection:** 0/24 (0%) across all judges on 3-point scale
**(vs 0% on 5-point mapped scale in v2)**

The 3-point scale **does NOT improve** Partially Correct detection. The bottleneck is not the scale but the judges' inability to distinguish partial from full matches when extraction and GT are semantically similar.

**Recommendation:** Use the 3-point scale for automated evaluation in the paper. It aligns with human annotation protocol and is easier to interpret.