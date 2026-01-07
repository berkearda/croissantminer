# Parsing Issues Found in Test (2110.14168v2.pdf)

## Major Issues Identified:

###  1. **False Positive Section Headers**
The section detection is picking up numbers from **figures, tables, and text** as section headers:
- `18 NOV` (date)
- `50 EPOCH` (figure axis label)
- `100 FIGURE` (figure reference)
- `8000 TRAINING SET SIZE` (table/figure label) - appeared 5 times!
- `3200 NUMBER OF COMPLETIONS PER TEST PROBLEM` (axis label)
- `2015 CONFERENCE ON EMPIRICAL METHODS...` (reference year)
- `50000 OPTIMIZER ADAM` (hyperparameter table)
- `10 HER SISTER GAVE HER` (example problem text!)

**Root Cause**: The regex pattern `(\d+)\s+([A-Z]+)` matches ANY number followed by capital letters, not just section headers.

### 2. **Sequential Filtering Correctly Rejects These**
Good news: The sequential numbering logic DOES reject most false positives:
- Sections 1→2→3→3.1→3.2→4→4.1→4.2→4.3→5→5.1→5.2→6 were accepted
- But then it accepted section `10` (which is actually example text "10 HER SISTER GAVE HER")
- Then rejected everything after because 10→18, 10→50, etc. aren't sequential

**Problem**: Even with sequential filtering, garbage still gets through occasionally.

### 3. **Missing RAI-Specific Sections**
The current TF-IDF keywords focus on "dataset", "data", "training", etc. but miss RAI-related content:
- No keywords for: consent, demographics, ethics, privacy, bias, fairness, limitations, annotators, workers, compensation
- These are critical for Croissant Responsible AI fields!

### 4. **Text Extraction Issues**
Looking at the section titles, there are OCR/extraction errors:
- "Veri Cation" instead of "Verification"
- "netuning" instead of "finetuning"
- Spaces in unexpected places

### 5. **TF-IDF Threshold Too High**
- Current threshold: 0.5 in `processor.py`
- Current threshold: 1.0 in `relevance.py`
- Some sections with scores 0.8-0.9 might be getting excluded unnecessarily
- Sections like "5.2 REGULARIZATION" (score unknown) might have RAI info but get filtered out

### 6. **Relevant Sections Being Excluded**
The final filter in `relevance.py` excluded 4 out of 10 sections:
- 3 sections with TF-IDF scores below 1.8 were excluded
- "Related Work" sections auto-excluded (might mention dataset details!)

### 7. **No Section for Limitations/Ethics**
- Papers often have "Limitations", "Ethics Statement", "Broader Impact" sections
- These contain RAI metadata but aren't being targeted

## What's Working Well:

✅ **Sequential numbering** mostly works to filter garbage
✅ **TF-IDF** successfully identified Methods sections (4.1, 4, 4.2) as dataset-relevant
✅ **Abstract, Intro, Dataset** sections correctly identified by title
✅ **Text cleaning** removed page breaks properly

## Priority Fixes Needed:

1. **Better section header detection** - distinguish real headers from figure/table labels
2. **Add RAI keywords** to TF-IDF (consent, demographics, ethics, etc.)
3. **Lower TF-IDF thresholds** (0.5 → 0.3, 1.0 → 0.4)
4. **Don't auto-exclude Related Work** - might have dataset info
5. **Add target sections**: Limitations, Ethics, Broader Impact, Appendix
6. **Better text cleaning** - fix OCR errors like "Veri Cation"
7. **Context-aware header detection** - use formatting cues, not just regex

## Test Results Summary:
- Headers found: 34 (many false positives!)
- Valid sections extracted: 13
- Targeted sections: 10
- Final chunks sent to LLM: 6
- **Missing**: Limitations, Ethics, Appendix sections (if they exist)
