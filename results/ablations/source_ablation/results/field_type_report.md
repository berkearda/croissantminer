# Field-Type-Aware Evaluation Results

## Main Comparison

| Method | Constrained (EM) | Short-text (F1) | RAI (Judge 1-5) | Composite |
|--------|-----------------|----------------|----------------|-----------|
| paper_only | 54.9% (n=51) | 0.502 (n=24) | 2.59/5 (n=87) | 49.4% |
| card_only | 49.0% (n=51) | 0.623 (n=24) | 0.99/5 (n=87) | 33.0% |
| combined | 58.8% (n=51) | 0.646 (n=24) | 2.37/5 (n=87) | 50.3% |

## Per-Dataset Composite Scores

| Dataset | paper_only | card_only | combined |
|---------|------|------|------|
| CIFAR | 28.7% | 47.5% | 41.7% |
| FLORES | 37.9% | 20.4% | 33.4% |
| MLS | 48.5% | 29.9% | 50.6% |
| MMLU | 57.5% | 48.9% | 54.7% |
| MMMU | 52.6% | 45.7% | 60.7% |
| MSCOCO | 49.2% | 0.0% | 47.2% |
| MathVista | 62.8% | 35.4% | 54.9% |
| Visual Genome | 51.6% | 41.2% | 59.5% |