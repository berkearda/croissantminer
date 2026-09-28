# Error Taxonomy Analysis

## Summary
- Total field-dataset pairs evaluated: 162
- Perfect extractions: 70 (43%)
- Errors: 92 (57%)

## Error Distribution

| Error Type | Count | % | Fix |
|------------|-------|---|-----|
| ABSENT_IN_SOURCE | 29 | 32% | Better source coverage (web search, multiple card sources), or accept null as valid |
| HALLUCINATION | 25 | 27% | Constrained decoding, schema validation, confidence thresholds, null preference in prompts |
| INCOMPLETE | 33 | 36% | Multi-pass extraction, chain-of-thought prompting, longer context windows |
| GRANULARITY_MISMATCH | 4 | 4% | Schema-aware post-processing, standardization layer (SPDX for licenses, ISO for dates) |
| WRONG_SECTION | 1 | 1% | Section-aware extraction, improved field boundary definitions in prompts |
| FORMAT_ERROR | 0 | 0% | Output validators, format-specific post-processing (date parser, license normalizer) |
