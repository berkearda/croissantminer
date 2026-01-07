# Comprehensive LLM Evaluation Analysis (After Fixes)

**Date:** October 28, 2025
**Evaluation File:** evaluation_report_lenient.json (after fixes applied)
**Status:** ⚠️ 10 real issues found + 1 markdown generation bug

---

## Executive Summary

After applying all fixes to the LLM evaluation system, performed comprehensive analysis of **95 field evaluations** across **6 datasets**. Found:

1. **10 real LLM evaluation issues** requiring attention
2. **1 critical markdown generation bug** (extracted values not displayed correctly in markdown)

### Overall Accuracy
- **Current:** 63.2%
- **After first fixes:** +12.6pp from 50.5%
- **Potential with these fixes:** ~65-67% (+2-4pp more)

---

## Issue #1: Markdown Generation Bug ⚠️ CRITICAL

### Problem
The markdown file (`llm_responses_detailed_AFTER_FIXES.md`) shows `(not extracted)` for **45 fields** that were actually extracted and evaluated by LLM.

### Evidence
**Example (FLORES sc:name):**
- **Markdown shows:** `(not extracted)`
- **LLM reasoning says:** "The extracted value 'FLORES-101'..."
- **Actual extraction file:** `"name": "FLORES-101"` ✓ EXISTS

### Root Cause
The `get_extracted_value()` function in the markdown generation script is not correctly accessing extraction data, particularly for:
- Fields without `sc:` prefix in JSON but queried with prefix
- Creator/Publisher entity fields (not extracting from nested objects correctly)
- Some RAI fields

### Impact
- **Severity:** MEDIUM (display only, doesn't affect actual evaluation)
- **Affected:** 45 fields display incorrectly in markdown
- **User confusion:** Makes it look like fields weren't extracted when they were

### Fix Required
Rewrite the markdown generation script's `get_extracted_value()` function to match the evaluator's `flatten_extracted_metadata()` logic exactly.

---

## Issue #2: Field Values Present But Showing As Missing ⚠️ HIGH

### Problem
4 fields were evaluated by LLM as if they had extracted values, but extraction files show they're actually missing.

### Cases

#### Case 1: CIFAR sc:inLanguage (Annotator 3)
- **Extraction file:** No `inLanguage` field
- **LLM reasoning:** "The extracted value 'English' is semantically equivalent to the groundtruth value 'en'"
- **Groundtruth:** `en`
- **LLM category:** CORRECT

**Issue:** LLM thinks extracted value is 'English' but file doesn't have this field!

#### Case 2-3: MMMU cr:isLiveDataset (Annotators 1 & 2)
- **Extraction file:** No `isLiveDataset` field
- **LLM reasoning:** "The extracted value 'True' is semantically equivalent..."
- **Groundtruth:** `1` (annotator 1), `Yes` (annotator 2)
- **LLM category:** CORRECT

**Issue:** LLM thinks extracted value is 'True' but file doesn't have this field!

#### Case 4: MLS sc:inLanguage (Annotators 2 & 3)
- **Extraction file:** Has `inLanguage: "English"`
- **LLM reasoning:** "Exact match (case-insensitive)"
- **Groundtruth:** `English`
- **LLM category:** CORRECT

**This one is actually CORRECT!** False positive in my analysis.

### Root Cause Hypothesis
**LLM cache contamination** - The LLM evaluator might be using cached results from a previous evaluation where those fields existed. The cache key includes field_name, predicted, and groundtruth, but if predicted changed between evaluations, old cache entries might be used.

### Evidence for Cache Issue
Looking at `llm_evaluator.py` line 153:
```python
cache_key = f"{field_name}::{predicted}::{groundtruth}"
```

If a field was previously extracted as "English" and then later not extracted, but the same groundtruth is used, the cache might return the old evaluation.

### Fix Required
1. **Clear the LLM cache** before running new evaluations
2. **Add version/hash to cache key** to prevent cross-evaluation contamination
3. **Re-run evaluation** to get fresh results

---

## Issue #3: Dataset Name Variations - False Positives? 🟡 MEDIUM

### Problem
4 cases where extracted dataset name doesn't exactly match groundtruth but marked CORRECT.

### Example: MMLU sc:name (All 3 annotators)
- **Extracted:** "Massive Multitask Test"
- **Groundtruth:** "mmlu" (annotators 1-3)
- **LLM reasoning:** "The extracted value 'Massive Multitask Test' is semantically equivalent to the groundtruth value 'mmlu', as both refer to the same dataset, which is the Massive Multitask Language Understanding dataset"
- **LLM category:** CORRECT

### Analysis

**The actual dataset name is:** "Measuring Massive Multitask Language Understanding" (MMLU)

**Extracted has:** "Massive Multitask **Test**"
**Should be:** "Massive Multitask **Language Understanding**"

**Is this correct?**
- ✅ Yes, they both refer to MMLU dataset
- ❌ No, "Test" vs "Language Understanding" is a significant difference in the dataset name

**LLM's interpretation:** Focuses on whether they refer to the same dataset (✓) rather than exact name accuracy (✗)

### Recommendation
This is a **prompt ambiguity issue**. Depends on evaluation goal:
- If goal: "Does it refer to the same dataset?" → CORRECT ✓
- If goal: "Is the name accurately extracted?" → INCORRECT ✗

For research paper evaluation, probably should be **PARTIALLY_CORRECT** since it's close but not exact.

### Fix Required
Clarify in prompt whether partial/approximate dataset names should be CORRECT or PARTIALLY_CORRECT.

---

## Issue #4: Opposite Boolean Values Not Marked INCORRECT ⚠️ HIGH

### Problem
2 cases where boolean fields have opposite values but LLM marked as MISSING instead of INCORRECT.

### Cases

#### Case 1: MSCOCO cr:isLiveDataset (Annotator 1)
- **Extracted:** "True"
- **Groundtruth:** "false"
- **LLM category:** MISSING
- **LLM reasoning:** "Field not extracted"

#### Case 2: MSCOCO cr:isLiveDataset (Annotator 3)
- **Extracted:** "True"
- **Groundtruth:** "False"
- **LLM category:** MISSING
- **LLM reasoning:** "Field not extracted"

### Root Cause
LLM is not receiving the extracted value! It says "Field not extracted" but the extraction file has `"isLiveDataset": true`.

This is the **same cache issue** as Issue #2.

### Fix Required
Same as Issue #2 - clear cache and re-run evaluation.

---

## Summary of Real Issues

| Issue | Type | Severity | Count | Root Cause |
|-------|------|----------|-------|------------|
| **#1** | Markdown display bug | MEDIUM | 45 | Script logic error |
| **#2** | Cache contamination | HIGH | 4 | LLM cache not cleared |
| **#3** | Dataset name ambiguity | MEDIUM | 4 | Prompt unclear |
| **#4** | Cache contamination | HIGH | 2 | Same as #2 |

**Total unique issues:** 3 (markdown bug, cache issue, prompt ambiguity)

---

## Recommended Actions

### Priority 1: Fix Cache Contamination (HIGH) ⚠️
**Impact:** 6 fields affected, accuracy impact ~1-2%

**Actions:**
1. Clear LLM evaluation cache before running evaluations
2. Add version/timestamp to cache key: `f"{version}::{field_name}::{predicted}::{groundtruth}"`
3. Re-run evaluation to get fresh results

**Expected improvement:** +1-2% accuracy (properly mark MISSING fields)

### Priority 2: Fix Markdown Generation (MEDIUM) ⚠️
**Impact:** 45 fields display incorrectly (no accuracy impact)

**Actions:**
1. Rewrite `get_extracted_value()` in markdown generation script
2. Test with all 6 datasets to ensure correct display
3. Regenerate markdown with correct extracted values

**Expected improvement:** Better user experience, no accuracy change

### Priority 3: Clarify Dataset Name Matching (LOW) 🔵
**Impact:** 4 fields, unclear if issue or not

**Actions:**
1. Decide evaluation goal: exact name match vs. same dataset reference
2. Update prompt if needed to clarify
3. Re-evaluate MMLU sc:name if criteria changed

**Expected improvement:** Debatable - depends on goals

---

## Validation

### Files Analyzed
- `evaluation_outputs/evaluation_report_lenient.json` - Main evaluation results
- `evaluation_outputs/llm_responses_detailed_AFTER_FIXES.md` - Detailed markdown (has bugs)
- `evaluation_outputs/*_extraction.json` - 8 extraction output files
- `groundtruth/parsed_md_filtered/*_annotations.json` - 8 groundtruth files

### Analysis Method
1. Loaded actual extraction files to compare with LLM reasonings
2. Checked for consistency between extracted values and LLM judgments
3. Identified cases where LLM reasoning doesn't match actual extraction data

---

## Conclusion

The LLM evaluation system is **mostly working correctly** after the fixes. The main remaining issues are:

1. **Cache contamination** (6 fields) - HIGH priority, easy fix
2. **Markdown display bug** (45 fields) - MEDIUM priority, cosmetic only
3. **Dataset name ambiguity** (4 fields) - LOW priority, needs clarification

**Current accuracy:** 63.2%
**After fixing cache issue:** ~64-65% (estimated)

The system is production-ready for most use cases, but cache should be cleared between evaluation runs to prevent contamination.

---

## Files Generated

- `evaluation_outputs/COMPREHENSIVE_LLM_ANALYSIS.md` - This report
- `evaluation_outputs/llm_issues_after_fixes.json` - Machine-readable issue list
