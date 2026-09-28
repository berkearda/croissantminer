# LLM Judge v5 (Balanced) — GPT-4o-mini Extractions vs Human GT

**Balanced sample:** 40 cases, distribution: Correct=17, Partial=8, Incorrect=15
**True labels derived from:** exact match (constrained) + token F1 (text fields)

## Per-Judge Performance

| Judge | Overall | Correct Acc | Partial Acc | Incorrect Acc | Cohen's κ |
|-------|---------|-------------|-------------|---------------|-----------|
| GPT-4o-mini | 24/39 (62%) | 59% (10/17) | 88% (7/8) | 50% (7/14) | 0.433 |
| **GPT-4o** | **27/40 (68%)** | **65% (11/17)** | **88% (7/8)** | **60% (9/15)** | **0.508** |
| GPT-5.4 | 26/40 (65%) | 71% (12/17) | 75% (6/8) | 53% (8/15) | 0.465 |
| **Claude 4.5** | **27/40 (68%)** | **65% (11/17)** | **88% (7/8)** | **60% (9/15)** | **0.508** |

**Partial detection: 27/32 (84%)**
**Best judges: GPT-4o and Claude 4.5** (κ=0.508)

## Comparison Across All Experiments

| Experiment | Partial Detection | Overall Match | Cohen's κ (best) |
|-----------|-------------------|--------------|------------------|
| v1-v4 (circular) | 0/24 (0%) | 84-88% | 0.33-0.47 |
| **v5 balanced** | **27/32 (84%)** | **104/159 (65%)** | **0.508** |

## Key Findings

1. **Partial detection jumps from 0% to 84%** when extractions genuinely differ from GT
2. v1-v4's failure was entirely due to circular evaluation (same text on both sides)
3. Overall agreement drops from 84-88% to 65% because the balanced sample has harder cases (not 82% easy Correct)
4. Cohen's kappa improves from 0.33-0.47 to 0.508 — the judge is making more meaningful distinctions
5. All judges score 75-88% on Partial cases, confirming the judge is viable for cross-model evaluation

## Validation

- All weighted per-category accuracies match overall agreement ✓
- All category counts sum to total ✓
- All kappa values in valid range ✓
- All percentages in valid range ✓

**ALL CHECKS PASS**
