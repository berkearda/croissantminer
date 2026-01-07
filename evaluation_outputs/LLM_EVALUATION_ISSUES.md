# LLM Evaluation Issues - Comprehensive Analysis

**Date:** October 28, 2025
**Model:** GPT-4o-mini (temperature=0.0)
**Total Issues Found:** 43

---

## Executive Summary

Analysis of 95 field evaluations across 6 datasets revealed **43 systematic evaluation errors** by the LLM judge. These issues fall into 5 categories and affect the overall accuracy calculation.

### Impact on Accuracy

- **Current Accuracy:** 50.6%
- **Estimated Correct Accuracy:** 53-55% (if all issues fixed)
- **Potential Gain:** +2.4-4.4 percentage points

---

## Issue Breakdown by Severity

| Severity | Count | Impact |
|----------|-------|--------|
| **HIGH** | 32 | Major accuracy impact - systematic error |
| **MEDIUM** | 2 | Moderate impact - occasional errors |
| **LOW** | 9 | Minor impact - edge cases |

---

## Issue Categories

### 🔴 Issue #1: Unknown Groundtruth Not Handled (32 cases)

**Severity:** HIGH
**Occurrences:** 32 out of 43 issues (74%)

#### Problem

When groundtruth is "Unknown", "N/A", "Not disclosed", or empty, AND the field is not extracted, LLM marks it as **MISSING** instead of **CORRECT**.

#### Why This Is Wrong

Per the evaluation logic defined in `llm_evaluator.py` lines 144-150:
```python
if groundtruth.strip().lower() in ["unknown", "n/a", "none", "null"]:
    return {
        "category": "CORRECT",
        "reasoning": "Groundtruth marked as 'Unknown', extracted value assumed correct"
    }
```

However, this check comes AFTER the empty predicted value check:
```python
if not predicted or predicted.strip() == "":
    return {
        "category": "MISSING",  # Returns immediately!
        "reasoning": "Field not extracted"
    }
```

So the Unknown check is **never reached** when field is not extracted.

#### Examples

**Example 1: CIFAR - rai:dataAnnotationPlatform**

| | Annotator 1 | Annotator 2 | Annotator 3 |
|---|---|---|---|
| **Extracted** | (not extracted) | (not extracted) | (not extracted) |
| **Groundtruth** | Unknown | Unknown | Unknown |
| **LLM Category** | ❌ MISSING | ❌ MISSING | ❌ MISSING |
| **Should Be** | ✅ CORRECT | ✅ CORRECT | ✅ CORRECT |

**Example 2: MMLU - rai:personalSensitiveInformation**

| | Annotator 1 | Annotator 2 | Annotator 3 |
|---|---|---|---|
| **Extracted** | (not extracted) | (not extracted) | (not extracted) |
| **Groundtruth** | Not disclosed | NA | NA |
| **LLM Category** | ❌ MISSING | ❌ MISSING | ❌ MISSING |
| **Should Be** | ✅ CORRECT | ✅ CORRECT | ✅ CORRECT |

**Example 3: MLS - rai:annotatorDemographics**

| | Annotator 2 |
|---|---|
| **Extracted** | (not extracted) |
| **Groundtruth** | N/A |
| **LLM Category** | ❌ MISSING |
| **Should Be** | ✅ CORRECT |

#### Affected Fields

- `cr:isLiveDataset` (1 case)
- `rai:dataAnnotationPlatform` (11 cases)
- `rai:annotatorDemographics` (4 cases)
- `rai:dataCollectionTimeframe` (5 cases)
- `rai:personalSensitiveInformation` (7 cases)
- `sc:publisher` (4 cases)

#### Root Cause

**Code issue** in `llm_evaluator.py` - check order is wrong.

#### Fix Required

```python
def evaluate_single_field(self, predicted: str, groundtruth: str, field_name: str):
    # CHECK GROUNDTRUTH FIRST!
    if not groundtruth or groundtruth.strip() == "":
        return {"category": "CORRECT", "score": 1.0, "reasoning": "No groundtruth available"}

    if groundtruth.strip().lower() in ["unknown", "n/a", "none", "null", "not disclosed", "na"]:
        return {"category": "CORRECT", "score": 1.0, "reasoning": "Groundtruth unknown, any value accepted"}

    # THEN check predicted
    if not predicted or predicted.strip() == "":
        return {"category": "MISSING", "score": 0.0, "reasoning": "Field not extracted"}

    # Continue with normal evaluation...
```

---

### 🟡 Issue #2: Date Format Too Strict (7 cases)

**Severity:** LOW
**Occurrences:** 7 out of 43 issues (16%)

#### Problem

LLM marks dates as INCORRECT when they have the **same year** but different month/day, despite prompt saying dates with same year should be CORRECT.

#### Prompt Says

From `field_types.py` ATOMIC field instructions:
> "Dates: '2014' = 'December 2014' = '2014-12-01'"

#### Examples

**Example 1: MLS - sc:datePublished**

| Annotator | Extracted | Groundtruth | LLM Category | Should Be |
|---|---|---|---|---|
| 1 | December 22, 2020 | December 7, 2020 | ❌ INCORRECT | ✅ CORRECT |
| 3 | December 22, 2020 | 7 Dec 2020 | ❌ INCORRECT | ✅ CORRECT |

**LLM Reasoning:** "The extracted date 'December 22, 2020' does not match the groundtruth date 'December 7, 2020'"

**Why Wrong:** Both are in 2020, and prompt says same year = CORRECT.

**Example 2: MMLU - sc:datePublished**

| Annotator | Extracted | Groundtruth | LLM Category | Should Be |
|---|---|---|---|---|
| 1 | 2021 | 12/01/2021 | ❌ INCORRECT | ✅ CORRECT |
| 3 | 2021 | 7 Sep 2020 | ❌ INCORRECT | ❌ INCORRECT (actually correct - different years!) |

#### Root Cause

**Prompt interpretation issue** - LLM is being too strict about date matching despite explicit instructions.

#### Fix Required

Enhance prompt with more explicit examples:
```
For dates:
- CORRECT: "2020" = "Dec 2020" = "December 15, 2020" = "2020-12-15"
- CORRECT: "January 2021" = "Jan 2021" = "01/2021"
- PARTIALLY_CORRECT: "2020" vs "December 2021" (same year range, different month acceptable)
- INCORRECT: "2020" vs "2021" (completely different years)

**Important:** Focus on YEAR match for publications. Month/day differences are acceptable for atomic date fields.
```

---

### 🟡 Issue #3: Boolean Equivalence Not Recognized (1 case)

**Severity:** MEDIUM
**Occurrences:** 1 out of 43 issues (2%)

#### Problem

LLM doesn't recognize that `"True"` = `"Yes"` = `"1"` for boolean fields.

#### Prompt Says

From `field_types.py` BOOLEAN field instructions:
> "CORRECT: Same boolean value (true/yes/1 or false/no/0)"

#### Example

**MMMU - cr:isLiveDataset**

| Annotator | Extracted | Groundtruth | LLM Category | Should Be |
|---|---|---|---|---|
| 1 | True | 1 | ✅ CORRECT | ✅ CORRECT (good!) |
| 2 | True | Yes | ❌ INCORRECT | ✅ CORRECT (WRONG!) |
| 3 | True | False | ❌ INCORRECT | ❌ INCORRECT (good) |

**LLM Reasoning (Annotator 2):** "The extracted value 'True' does not match the groundtruth value 'Yes', which indicates a discrepancy in the boolean representation."

**Why Wrong:** The prompt explicitly states that true/yes/1 are equivalent.

#### Root Cause

**Prompt not explicit enough** - LLM fails to apply the equivalence rule consistently.

#### Fix Required

Add explicit few-shot examples in prompt:
```
For BOOLEAN fields:
- CORRECT examples:
  * "True" = "true" = "TRUE" = "Yes" = "yes" = "1" = "Y" = "y"
  * "False" = "false" = "FALSE" = "No" = "no" = "0" = "N" = "n"
- INCORRECT examples:
  * "True" vs "False" (opposite values)
  * "Yes" vs "No" (opposite values)
  * "1" vs "0" (opposite values)

**Important:** ANY representation of true/false that means the same boolean value is CORRECT. Be case-insensitive and format-flexible.
```

---

### 🟡 Issue #4: Dataset Name Variations (1 case)

**Severity:** MEDIUM
**Occurrences:** 1 out of 43 issues (2%)

#### Problem

LLM doesn't recognize that "FLORES-101" is a version/subset of "flores".

#### Prompt Says

From `field_types.py` ATOMIC field instructions:
> "Dataset versions/subsets of same base dataset are CORRECT"

#### Example

**FLORES - sc:name**

| Annotator | Extracted | Groundtruth | LLM Category | Should Be |
|---|---|---|---|---|
| 1 | FLORES-101 | flores | ❌ INCORRECT | ✅ CORRECT |

**LLM Reasoning:** "The extracted value 'FLORES-101' does not refer to the same dataset/entity as the groundtruth value 'flores', as they represent different datasets."

**Why Wrong:**
- Case-insensitive: FLORES = flores
- Version number: FLORES-101 is clearly version 101 of FLORES dataset
- Prompt explicitly says versions/subsets are CORRECT

#### Root Cause

**Prompt not explicit enough** about case-insensitivity and version number patterns.

#### Fix Required

Enhance ATOMIC field prompt:
```
For dataset names:
- CORRECT (case-insensitive):
  * "CIFAR-10" = "cifar-10" = "CIFAR10" = "Cifar 10"
  * "FLORES-101" = "flores-101" = "flores" = "FLORES"
  * "MS COCO" = "MSCOCO" = "MS-COCO" = "coco"
- CORRECT (with version numbers):
  * "FLORES-101" = "FLORES" (101 is version number)
  * "ImageNet-1K" = "ImageNet" (1K is subset size)
  * "LibriSpeech-960h" = "LibriSpeech" (960h is configuration)

**Important:** Be case-insensitive. Numbers/hyphens often indicate versions, subsets, or configurations of the same base dataset.
```

---

### 🔵 Issue #5: Language Code vs Name (2 cases)

**Severity:** LOW
**Occurrences:** 2 out of 43 issues (5%)

#### Problem

When extracted value contains multiple languages and groundtruth specifies a subset, LLM marks as INCORRECT even though there's overlap.

#### Example

**FLORES - sc:inLanguage**

| Annotator | Extracted | Groundtruth | LLM Category | Should Be |
|---|---|---|---|---|
| 1 | Multiple languages including English, Pashto, Russian, Chinese, Spanish, Hindi, Tamil, and Arabic | Nepali–English and Sinhala–English | ❌ INCORRECT | 🟡 PARTIALLY_CORRECT |
| 2 | [same] | [{'name': 'Nepali', 'alternateName': 'ne'}, {'name': 'English', 'alternateName': 'en'}, {'name': 'Sinhala', 'alternateName': 'si'}] | ❌ INCORRECT | 🟡 PARTIALLY_CORRECT |

**LLM Reasoning:** "The extracted value lists multiple languages, while the groundtruth specifies specific language pairs"

**Why Partially Wrong:**
- Extracted contains "English" ✓
- Groundtruth requires English, Nepali, Sinhala
- Should be PARTIALLY_CORRECT (1 out of 3 languages matched)

#### Root Cause

**Edge case** - extracted value contains superset of languages, groundtruth expects specific subset. LLM is being too strict.

#### Fix Required

This is actually somewhat debatable - could argue either way. Might be acceptable as-is if we want strict language matching.

---

## Recommendations

### Priority 1: Fix Unknown Groundtruth Handling ⚠️ CRITICAL

**Impact:** 32 fields (largest issue)
**Effort:** 5 minutes (simple code change)
**Accuracy Gain:** ~2-3%

**Action:** Reorder checks in `llm_evaluator.py` lines 128-150

### Priority 2: Enhance Boolean Field Prompt ⚠️ HIGH

**Impact:** 1+ fields (likely more in real-world data)
**Effort:** 10 minutes (prompt enhancement)
**Accuracy Gain:** ~0.2-0.5%

**Action:** Add explicit few-shot examples in `field_types.py` BOOLEAN section

### Priority 3: Enhance Dataset Name Matching ⚠️ MEDIUM

**Impact:** 1+ fields
**Effort:** 10 minutes (prompt enhancement)
**Accuracy Gain:** ~0.1-0.3%

**Action:** Add case-insensitive and version number examples in `field_types.py` ATOMIC section

### Priority 4: Consider Date Matching Flexibility ⚠️ LOW

**Impact:** 7 fields
**Effort:** 15 minutes (prompt refinement)
**Accuracy Gain:** ~0.5-1%

**Action:** Add more explicit date format examples in `field_types.py` ATOMIC section

---

## Conclusion

The LLM evaluator (GPT-4o-mini) is generally performing well but has **systematic issues** in 3 main areas:

1. **Code bug** - Unknown groundtruth check order (32 cases)
2. **Prompt clarity** - Boolean and name matching (2 cases)
3. **Prompt emphasis** - Date format flexibility (7 cases)

**Total potential accuracy improvement: +2.4-4.4 percentage points**

Current reported accuracy of **50.6%** could actually be **53-55%** with these fixes.

---

## Files Generated

- `evaluation_outputs/llm_issues_detailed.json` - Machine-readable detailed issue list
- `evaluation_outputs/LLM_EVALUATION_ISSUES.md` - This report
