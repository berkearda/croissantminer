# Robustness Analysis Across 6 PDFs

## Overall Results

**Success Rate:** 6/6 (100%) ✅

### Coverage Statistics:
- **Abstract:** 6/6 (100%) ✅
- **Introduction:** 5/6 (83%) ⚠️
- **Dataset sections:** 4/6 (67%) ⚠️
- **Methods sections:** 1/6 (17%) ❌
- **RAI sections:** 0/6 (0%) ❌

---

## Critical Issues Found

### 🚨 Issue #1: PDF with NO Section Headers (2311.16502v4.pdf - 119 pages!)
**Problem:**
- Found ONLY 2 headers: "Abstract" and "9.17 AVERAGE EXPLANATION LENGTH"
- The entire paper (245,917 chars!) was treated as one giant "Abstract"
- Split into 21 chunks, all labeled "Abstract"
- Missing: Introduction, Dataset, Methods, Results, Conclusion, etc.

**Root Cause:**
- Paper likely uses a non-standard format (single-column, no numbered sections?)
- Our regex patterns `(\d{1,2}(?:\.\d{1,2}){0,3})\s+([A-Z]...)` require section NUMBERS
- Many papers use unnumbered sections like "Introduction", "Methods", "Discussion"

**Impact:** CRITICAL - We extract almost nothing useful from papers without numbered sections

---

### 🚨 Issue #2: False Positives from Author Names/References
**Example from 1602.07332v1.pdf (Visual Genome paper):**
- Detected as valid sections:
  - "2 RANJAY KRISHNA ET AL"
  - "3 MAO ET AL"
  - "4 RANJAY KRISHNA ET AL"
  - "6 RANJAY KRISHNA ET AL"
  - "8 RANJAY KRISHNA ET AL"
  - "10 RANJAY KRISHNA ET AL"
  - "12 RANJAY KRISHNA ET AL"
  - "14 RANJAY KRISHNA ET AL"

**Root Cause:**
- Two-column PDF layout → page numbers appear next to author names
- Pattern matches: `NUMBER + CAPITAL_WORDS`
- "ET AL" passes our keyword filter (not in noise patterns!)

**Impact:** HIGH - Adds garbage sections, wastes processing

---

### 🚨 Issue #3: Missing Subsections Due to Strict Sequential Logic
**Example from 1602.07332v1.pdf:**
```
✔️ Added: 2.2 MULTIPLE OBJECTS...
⚠️ SKIPPED: 2.6 ONE SCENE GRAPH...  (gap: 2.2 → 2.6)
✔️ Added: 3 MAO ET AL
⚠️ SKIPPED: 3 RELATED WORK...       (duplicate section 3!)
✔️ Added: 4.1 CROWD WORKERS...
⚠️ SKIPPED: 4.5 SCENE GRAPHS...     (gap: 4.1 → 4.5)
⚠️ SKIPPED: 4.6 QUESTIONS...        (gap continues)
⚠️ SKIPPED: 4.7 VERIFICATION...
⚠️ SKIPPED: 4.8 CANONICALIZATION...
```

**Root Cause:**
- Sequential filter expects 4.1 → 4.2 → 4.3... (no gaps)
- Real papers skip subsection numbers (4.1 → 4.5 → 4.8)
- We're losing valuable sections!

**Impact:** MEDIUM-HIGH - Missing important content

---

###  🚨 Issue #4: No RAI Sections Detected (0/6 papers!)
**Even though:**
- We added RAI keywords (ethics, limitations, etc.)
- We prioritize RAI sections
- Some papers likely have these sections

**Possible Causes:**
1. Papers don't have dedicated Ethics/Limitations sections
2. RAI content is embedded in other sections (Discussion, Conclusion)
3. TF-IDF not catching RAI keywords effectively
4. Need to check if RAI keywords are actually in the papers

**Impact:** HIGH - Core requirement for Croissant metadata!

---

### ⚠️ Issue #5: Variable Detection of Methods Sections (17%)
**Results:**
- 2110.14168v2.pdf: ✓ (detected 2 Methods sections)
- 2106.03193v1.pdf: ✓ (detected 2 Methods sections)
- 2009.03300v3.pdf: ✓ (detected 1 Methods section)
- Others: ✗ (no Methods detected)

**Possible Causes:**
- Papers use different terms: "Methods", "Approach", "Methodology", "Model"
- Methods might be part of "4 EXPERIMENTS" or similar
- Title-based detection might be too strict

**Impact:** MEDIUM - Methods sections often contain dataset details

---

### ⚠️ Issue #6: Sequential Logic Too Strict (loses 20-30% of sections)
**Example gaps being rejected:**
- 2.2 → 2.6 (skipped 2.3, 2.4, 2.5)
- 4.1 → 4.5 (skipped 4.2, 4.3, 4.4)
- 5.7 → 5.8 (skipped one subsection, but this was kept!)

**Current Rules:**
```python
# Allows gaps up to 3 subsections:
max_sublevel_gap = 3
# So 4.1 → 4.4 is OK, but 4.1 → 4.5 is rejected
```

**Impact:** MEDIUM - Losing valid content, especially in long papers

---

## Recommendations for Robustness

### Priority 1: Support Unnumbered Sections (CRITICAL)
**Problem:** Papers like 2311.16502v4.pdf have zero numbered sections
**Solution:**
1. Add pattern to detect unnumbered section headers:
   - `^(Introduction|Methods|Results|Discussion|Conclusion)$` (at line start, all caps)
   - Look for formatting cues: bold, larger font, isolation on line
2. Fallback: If < 3 sections found, use paragraph-based splitting

### Priority 2: Filter Out Author Names (HIGH)
**Problem:** "2 RANJAY KRISHNA ET AL" detected as section
**Solution:**
1. Add "ET AL" to noise patterns
2. Reject titles with only 2-3 capitalized words that are likely names
3. Check if title ends with "ET AL" or contains "REFERENCES"

### Priority 3: Relax Sequential Logic (MEDIUM-HIGH)
**Problem:** Losing subsections due to numbering gaps
**Solution:**
1. Allow subsection gaps up to 5-6 (not just 3)
2. If we see pattern like 4.1 → 4.5, accept it (common in papers)
3. Don't reject based on gaps in well-structured papers

### Priority 4: Improve RAI Detection (HIGH)
**Problem:** 0/6 papers have RAI sections detected
**Solution:**
1. Check if RAI keywords actually appear in test papers
2. Lower TF-IDF threshold further for RAI content
3. Add more RAI keyword variations
4. Look for RAI content in Conclusion/Discussion sections

### Priority 5: Better Methods Detection (MEDIUM)
**Problem:** Only 17% of papers have Methods detected
**Solution:**
1. Add more method-related keywords: "model", "algorithm", "procedure"
2. Detect "Experiments" sections (often describe methods)
3. Check subsections of numbered sections

---

## Test Data Summary

| PDF | Pages | Sections | Has Intro | Has Dataset | Has Methods | Has RAI | Issues |
|-----|-------|----------|-----------|-------------|-------------|---------|--------|
| 1405.0312v3 | 15 | 12 | ✓ | ✓ | ✗ | ✗ | Good coverage |
| 1602.07332v1 | 44 | 24 | ✓ | ✓ | ✗ | ✗ | Author name false positives, missing subsections |
| 2009.03300v3 | ? | 10 | ✓ | ✗ | ✓ | ✗ | Good but marked dataset as false |
| 2106.03193v1 | ? | 15 | ✓ | ✓ | ✗ | ✗ | Good coverage |
| 2110.14168v2 | 22 | 10 | ✓ | ✓ | ✓ | ✗ | Good (our test case) |
| 2311.16502v4 | 119! | 1 | ✗ | ✗ | ✗ | ✗ | **FAILED** - no sections detected |

---

## Action Items

**Must Fix:**
1. ✅ ~~Section header detection~~ (mostly done, but needs unnumbered support)
2. 🔴 Add support for unnumbered sections
3. 🔴 Filter out author names ("ET AL", reference patterns)
4. 🟡 Relax sequential logic (allow larger gaps)
5. 🟡 Investigate why no RAI sections found

**Nice to Have:**
6. Better Methods detection
7. Fallback paragraph-based splitting for papers with no sections
8. OCR error correction
9. Token-aware chunking

---

## Next Steps

1. **Add unnumbered section detection** - highest priority!
2. **Fix author name false positives** - add "et al" filter
3. **Relax sequential logic** - allow gaps up to 5-6
4. **Retest with same 6 PDFs** - validate improvements
5. Then move to text cleaning, token-aware chunking, etc.
