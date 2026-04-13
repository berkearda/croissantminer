# LLM Judge Comparison — 20 Tricky Cases

**Goal:** Compare GPT-4o-mini (no CoT) vs GPT-4o (CoT) vs Claude Sonnet 4.5 (CoT) as judges
**Cases:** 20 annotation pairs rated Partially Correct or Incorrect by human annotators
**Mapping:** Judge 4-5 → Correct (1), Judge 3 → Partial (2), Judge 1-2 → Incorrect (3)

## Results Table

| # | Dataset | Field | Human | GPT-4o-mini | GPT-4o | Claude | GPT-4o-mini→H | GPT-4o→H | Claude→H |
|---|---------|-------|-------|-------------|--------|--------|--------------|----------|----------|
| 1 | FLORES_30field | dataReleaseMaintenance | 2 | 4/5 | 4/5 | 4/5 | ✗ | ✗ | ✗ |
| 2 | google_fleurs | dataManipulationProtoc | 3 | 3/5 | 1/5 | 1/5 | ✗ | ✓ | ✓ |
| 3 | DigitalLearningGmbH_MA | dataLimitations | 3 | 5/5 | 5/5 | 1/5 | ✗ | ✗ | ✓ |
| 4 | Idavidrein_gpqa | dataUseCases | 3 | 3/5 | 3/5 | 3/5 | ✗ | ✗ | ✗ |
| 5 | allenai_ai2_arc | dataSocialImpact | 3 | 1/5 | 1/5 | 1/5 | ✓ | ✓ | ✓ |
| 6 | CIFAR_30field | dataCollection | 3 | 1/5 | 1/5 | 1/5 | ✓ | ✓ | ✓ |
| 7 | ChongyanChen_VQAonline | dataBiases | 2 | 4/5 | 4/5 | 4/5 | ✗ | ✗ | ✗ |
| 8 | AI4Math_MathVista | dataManipulationProtoc | 3 | 1/5 | 1/5 | 1/5 | ✓ | ✓ | ✓ |
| 9 | ChongyanChen_VQAonline | dataLimitations | 2 | 5/5 | 5/5 | 5/5 | ✗ | ✗ | ✗ |
| 10 | AI4Math_MathVista | dataPreprocessingProto | 3 | 2/5 | 1/5 | 1/5 | ✓ | ✓ | ✓ |
| 11 | AI4Math_MathVista | dataLimitations | 3 | 3/5 | 1/5 | 2/5 | ✗ | ✓ | ✓ |
| 12 | DigitalLearningGmbH_MA | dataUseCases | 3 | 3/5 | 2/5 | 1/5 | ✗ | ✓ | ✓ |
| 13 | chcorbi_helvipad | personalSensitiveInfor | 2 | 4/5 | 3/5 | 4/5 | ✗ | ✓ | ✗ |
| 14 | AI4Math_MathVista | dataSocialImpact | 3 | 1/5 | 1/5 | 1/5 | ✓ | ✓ | ✓ |
| 15 | MLS_30field | dataPreprocessingProto | 2 | 3/5 | 1/5 | 1/5 | ✓ | ✗ | ✗ |
| 16 | asahi417_seamless-alig | personalSensitiveInfor | 3 | 2/5 | 1/5 | 3/5 | ✓ | ✓ | ✗ |
| 17 | hails_mmlu_no_train | dataAnnotationProtocol | 2 | 1/5 | 1/5 | 1/5 | ✗ | ✗ | ✗ |
| 18 | CIFAR_30field | dataManipulationProtoc | 3 | 1/5 | 1/5 | 1/5 | ✓ | ✓ | ✓ |
| 19 | MINT-SJTU_RoboFAC-data | dataReleaseMaintenance | 2 | 1/5 | 5/5 | 5/5 | ✗ | ✗ | ✗ |
| 20 | ChongyanChen_VQAonline | dataAnnotationProtocol | 2 | 4/5 | 3/5 | 3/5 | ✗ | ✓ | ✓ |

## Agreement with Human Ratings

**GPT-4o-mini (no CoT):**
- Exact match: 8/20 (40%)
- Within ±1: 19/20 (95%)
- Too lenient (judge says Correct, human says Incorrect): 10
- Too strict (judge says Incorrect, human says Correct): 2

**GPT-4o (CoT):**
- Exact match: 12/20 (60%)
- Within ±1: 19/20 (95%)
- Too lenient (judge says Correct, human says Incorrect): 6
- Too strict (judge says Incorrect, human says Correct): 2

**Claude Sonnet 4.5 (CoT):**
- Exact match: 11/20 (55%)
- Within ±1: 20/20 (100%)
- Too lenient (judge says Correct, human says Incorrect): 7
- Too strict (judge says Incorrect, human says Correct): 2

## CoT Effect (GPT-4o-mini vs GPT-4o)

- Cases where CoT changed the verdict: 7/20
- CoT improved agreement with human: 5
- CoT worsened agreement: 1
- CoT neutral: 1

## Inter-Judge Agreement

- All 3 judges agree: 11/20 (55%)
- GPT-4o-mini ↔ GPT-4o: 13/20 (65%)
- GPT-4o-mini ↔ Claude: 12/20 (60%)
- GPT-4o ↔ Claude: 17/20 (85%)

## Notable Disagreements

**Case 3: DigitalLearningGmbH_MATH-light / rai:dataLimitations**
- Human: 3, GPT-4o-mini: 5/5, GPT-4o: 5/5, Claude: 1/5
- GPT-4o reasoning: Reasoning: The extracted metadata value is an exact match to the ground truth metadata value. It captures all the key information regarding the datase
- Claude reasoning: Reasoning: 
The extracted metadata is identical to the ground truth, which initially seems positive. However, I need to evaluate whether this content 

**Case 19: MINT-SJTU_RoboFAC-dataset / rai:dataReleaseMaintenancePlan**
- Human: 2, GPT-4o-mini: 1/5, GPT-4o: 5/5, Claude: 5/5
- GPT-4o reasoning: Reasoning: The extracted metadata value is "[NULL - not found in paper]," which indicates that no information was extracted for the field "rai:dataRel
- Claude reasoning: Reasoning: 
The field being evaluated is "rai:dataReleaseMaintenancePlan" which refers to plans for releasing and maintaining the dataset over time. T

## Key Findings

- **GPT-4o-mini:** 8/20 exact match (40%), 10 too-lenient errors
- **GPT-4o:** 12/20 exact match (60%), 6 too-lenient errors
- **Claude:** 11/20 exact match (55%), 7 too-lenient errors

**Recommendation:** Based on this small sample:
- Best judge: **GPT-4o** (12/20 agreement)
- CoT reasoning helps identify hallucination and wrong-section errors
- All judges struggle with 'Partially Correct' cases — tend to rate higher than humans