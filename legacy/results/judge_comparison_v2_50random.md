# LLM Judge Comparison v2 — 50 Random Cases (Stratified)

**Sample:** 50 cases, seed=42, stratified to match overall distribution
**Distribution:** Correct=41, Partial=6, Incorrect=3
**Datasets:** 40, **Fields:** 21

## Agreement with Human Ratings

| Judge | Exact Match | Overestimate | Underestimate | Cohen's κ | Spearman ρ |
|-------|-------------|-------------|---------------|-----------|------------|
| GPT-4o-mini (no CoT) | 44/50 (88%) | 6 | 0 | 0.468 | 0.615 |
| GPT-4o (CoT) | 44/50 (88%) | 6 | 0 | 0.468 | 0.615 |
| GPT-5.4 (CoT) | 44/50 (88%) | 6 | 0 | 0.468 | 0.615 |
| Claude Sonnet 4.5 (CoT) | 41/49 (84%) | 6 | 2 | 0.374 | 0.436 |

## Accuracy Stratified by Human Rating

| Judge | On Correct (n=41) | On Partial (n=6) | On Incorrect (n=3) |
|-------|-------------------|------------------|-------------------|
| GPT-4o-mini (no CoT) | 41/41 (100%) | 0/6 (0%) | 3/3 (100%) |
| GPT-4o (CoT) | 41/41 (100%) | 0/6 (0%) | 3/3 (100%) |
| GPT-5.4 (CoT) | 41/41 (100%) | 0/6 (0%) | 3/3 (100%) |
| Claude Sonnet 4.5 (CoT) | 38/40 (95%) | 0/6 (0%) | 3/3 (100%) |

## Inter-Judge Agreement

| Pair | Agreement |
|------|-----------|
| GPT-4o-mini (no CoT) ↔ GPT-4o (CoT) | 50/50 (100%) |
| GPT-4o-mini (no CoT) ↔ GPT-5.4 (CoT) | 50/50 (100%) |
| GPT-4o-mini (no CoT) ↔ Claude Sonnet 4.5 (CoT) | 47/49 (96%) |
| GPT-4o (CoT) ↔ GPT-5.4 (CoT) | 50/50 (100%) |
| GPT-4o (CoT) ↔ Claude Sonnet 4.5 (CoT) | 47/49 (96%) |
| GPT-5.4 (CoT) ↔ Claude Sonnet 4.5 (CoT) | 47/49 (96%) |

## Comparison with Previous Study (20 Tricky Cases)

| Metric | v1 (20 tricky) | v2 (50 random) | Delta |
|--------|---------------|----------------|-------|
| GPT-4o-mini (no CoT) | 40% | 88% | +48pp |
| GPT-4o (CoT) | 60% | 88% | +28pp |
| Claude Sonnet 4.5 (CoT) | 55% | 84% | +29pp |

**Key finding:** On random sample (82% Correct cases), all judges score much higher because they easily identify correct extractions. The tricky-case sample (0% Correct) was harder by design.

## Notable Disagreements (top 5)

**allenai_math_qa / rai:dataPreprocessingProtocol** (human=1)
  GPT-4o-mini (no CoT): 5/5
  GPT-4o (CoT): 5/5
  GPT-5.4 (CoT): 5/5
  Claude Sonnet 4.5 (CoT): 1/5

**MSCOCO_30field / rai:dataReleaseMaintenancePlan** (human=1)
  GPT-4o-mini (no CoT): 5/5
  GPT-4o (CoT): 5/5
  GPT-5.4 (CoT): 5/5
  Claude Sonnet 4.5 (CoT): 2/5

**AI4Math_MathVista / rai:dataPreprocessingProtocol** (human=3)
  GPT-4o-mini (no CoT): 2/5
  GPT-4o (CoT): 1/5
  GPT-5.4 (CoT): 1/5
  Claude Sonnet 4.5 (CoT): 1/5

**MINT-SJTU_RoboFAC-dataset / rai:annotationsPerItem** (human=3)
  GPT-4o-mini (no CoT): 2/5
  GPT-4o (CoT): 1/5
  GPT-5.4 (CoT): 1/5
  Claude Sonnet 4.5 (CoT): 1/5

**baber_piqa / rai:dataBiases** (human=1)
  GPT-4o-mini (no CoT): 5/5
  GPT-4o (CoT): 5/5
  GPT-5.4 (CoT): 5/5
  Claude Sonnet 4.5 (CoT): 5/5


---
Saved JSON: results/judge_comparison_v2_50random.json