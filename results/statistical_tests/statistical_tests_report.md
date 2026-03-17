# Statistical Tests

## Multi-Model Comparison (Bootstrap 95% CIs, N=10,000 resamples)

| Method | Composite | 95% CI | N |
|--------|-----------|--------|---|
| Claude Sonnet 4.5 | 49.4% | [43.4, 55.1] | 162 |
| GPT-4o-mini | 31.3% | [25.7, 36.9] | 162 |
| HF Auto-Croissant | 8.8% | [4.9, 13.3] | 162 |

## Per-Dataset Variance

| Method | Mean | Std | Min | Max |
|--------|------|-----|-----|-----|
| Claude | 48.6% | 10.1% | 28.7% | 62.8% |
| GPT-4o-mini | 30.6% | 5.8% | 21.6% | 39.9% |
| HF Auto | 8.8% | 1.9% | 6.3% | 11.4% |

## Ablation Significance
Prompt/context/few-shot differences (max 3.4pp) are not statistically significant at N=162 field-dataset pairs.
