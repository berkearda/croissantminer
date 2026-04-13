
# LLM Judge v5 (Corrected) — Field-Type-Stratified True Labels

**Sample:** 40 cases, corrected distribution: {1: 15, 3: 13, 2: 8}
**Label changes:** 4/40 cases relabeled

## Per-Judge Performance

| Judge | Overall | Correct Acc | Partial Acc | Incorrect Acc | Cohen's κ |
|-------|---------|-------------|-------------|---------------|-----------|
| GPT-4o-mini | 15/35 (43%) | 47% (7/15) | 62% (5/8) | 25% (3/12) | 0.149 |
| GPT-4o | 16/36 (44%) | 47% (7/15) | 50% (4/8) | 38% (5/13) | 0.154 |
| GPT-5.4 | 15/36 (42%) | 53% (8/15) | 38% (3/8) | 31% (4/13) | 0.102 |
| Claude 4.5 | 16/36 (44%) | 47% (7/15) | 50% (4/8) | 38% (5/13) | 0.154 |

**Partial detection: 16/32 (50%)**

## Validation

- GPT-4o-mini: weighted=42.9% vs overall=42.9% ✓, sum=35==35 ✓
- GPT-4o: weighted=44.4% vs overall=44.4% ✓, sum=36==36 ✓
- GPT-5.4: weighted=41.7% vs overall=41.7% ✓, sum=36==36 ✓
- Claude 4.5: weighted=44.4% vs overall=44.4% ✓, sum=36==36 ✓

**ALL CHECKS PASS**