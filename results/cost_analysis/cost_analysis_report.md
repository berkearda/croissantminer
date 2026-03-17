# Cost Analysis

## Main Comparison

| Method | Composite | $/dataset | s/dataset | Total (8 DS) | $/pp |
|--------|-----------|-----------|-----------|-------------|------|
| Claude Sonnet 4.5 | 49.4% | $0.1291 | 42s | $1.0330 | $0.0026 |
| GPT-4o-mini | 31.3% | $0.0056 | 25s | $0.0452 | $0.0002 |
| HF Auto-Croissant | 8.8% | $0.0000 | 0s | $0.0000 | free |

## Scaling Projections

| Datasets | Claude | GPT-4o-mini |
|----------|--------|-------------|
| 50 | $6.46 | $0.28 |
| 100 | $12.91 | $0.56 |
| 1000 | $129.13 | $5.65 |

## Judge Evaluation Cost
- Field-type judge: 198 calls = $0.0065
- Error taxonomy: 62 calls = $0.0032
