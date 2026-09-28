# 16-Field Evaluation Results

**Fields:** 16 (7 Constrained + 3 Short-text + 6 RAI)
**Datasets:** 8 (MLS, FLORES, CIFAR, Visual Genome, MSCOCO, MMLU, MMMU, MathVista)

## Main Results

| Method | Constrained (EM) | Short-text (F1) | RAI (Judge 1-5) | Composite [95% CI] | N |
|--------|-----------------|----------------|----------------|-------------------|---|
| Claude Sonnet 4.5 | 54.9% (n=51) | 0.502 (n=24) | 2.65/5 (n=26) | 51.8% [43.4, 59.4] | 101 |
| GPT-4o-mini | 39.2% (n=51) | 0.328 (n=24) | 2.54/5 (n=26) | 38.2% [30.4, 46.0] | 101 |
| HF Auto-Croissant | 21.6% (n=51) | 0.137 (n=24) | 0.00/5 (n=26) | 14.2% [7.8, 21.0] | 101 |

## Source Ablation

| Source | Composite [95% CI] |
|--------|-------------------|
| Paper Only | 51.8% [43.4, 59.4] |
| Card Only | 47.0% [37.9, 56.1] |
| Combined | 57.2% [48.9, 65.8] |

## AAAI Comparison

- AAAI (Mistral 7B): 59.4%
- NeurIPS (Claude Sonnet 4.5): 51.8%
- Delta: +-7.6pp