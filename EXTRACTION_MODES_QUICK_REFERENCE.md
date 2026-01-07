# Extraction Modes - Quick Reference Guide

## TL;DR

**Two extraction modes available:**
- `multi-section`: Extract from 8 sections (8 LLM calls) - Original approach
- `full-pdf`: Extract from entire PDF (1 LLM call) - **New, recommended**

**Full-PDF mode is 7.88x faster, 62.5% cheaper, and extracts 30% more fields.**

---

## Quick Start

### Option 1: Change Default in Config

```python
# config.py
EXTRACTION_MODE = "full-pdf"  # Recommended
```

Then run normally:
```bash
python main.py --paper-path 1405.0312v3
```

### Option 2: CLI Override

```bash
# Use full-PDF mode
python main.py --paper-path 1405.0312v3 --extraction-mode full-pdf

# Use multi-section mode
python main.py --paper-path 1405.0312v3 --extraction-mode multi-section
```

### Option 3: Programmatic

```python
from main import process_paper

# Full-PDF mode (recommended)
metadata = process_paper(
    paper_id="dataset_1",
    paper_path="1405.0312v3",
    extraction_mode="full-pdf"
)

# Multi-section mode
metadata = process_paper(
    paper_id="dataset_2",
    paper_path="2404.00498v2",
    extraction_mode="multi-section"
)
```

---

## Comparison at a Glance

| Feature | Multi-Section | Full-PDF |
|---------|--------------|----------|
| **Speed** | 62s | 8s (7.88x faster) |
| **LLM Calls** | 8 calls | 1 call (87.5% fewer) |
| **Cost** | ~$4.80 | ~$1.80 (62.5% cheaper) |
| **Fields Extracted** | 10 | 13 (30% more) |
| **Token Limit** | Safe for long papers | Limited to 50k chars |
| **Best For** | Very long papers | Most papers (recommended) |

---

## Test Both Modes

```bash
# Compare both modes on same paper
python test_extraction_modes.py --paper-path 1405.0312v3

# Results saved to:
# data/processed/{paper_id}_comparison.json
```

---

## When to Use Each Mode

### Use Full-PDF (Recommended Default)
- ✓ Paper is <50k characters (most papers)
- ✓ Want faster processing
- ✓ Want lower costs
- ✓ Want maximum field coverage
- ✓ Need cross-section information synthesis

### Use Multi-Section
- ✓ Paper is very long (>50k characters)
- ✓ Token limits are a concern
- ✓ Want redundancy through voting

---

## Configuration Reference

```python
# config.py

# Extraction mode: "multi-section" or "full-pdf"
EXTRACTION_MODE = "full-pdf"  # Default mode

# Maximum characters for full-PDF mode (token limit safety)
MAX_PDF_CHARS = 50000  # Adjust if using different models
```

---

## Troubleshooting

### Paper Too Long Error

If you see:
```
⚠️ PDF text is 56282 chars, truncating to 50000 chars
```

**Solution 1:** Use multi-section mode
```bash
python main.py --paper-path large_paper --extraction-mode multi-section
```

**Solution 2:** Increase MAX_PDF_CHARS in config.py (if model supports)
```python
MAX_PDF_CHARS = 80000  # For models with larger context
```

### Missing Fields

If full-PDF misses fields, try multi-section mode for redundancy:
```bash
python main.py --paper-path problematic_paper --extraction-mode multi-section
```

---

## Performance Tips

1. **Use Full-PDF for batches** - 62.5% cost savings on 100+ papers
2. **Test mode on sample first** - Use `test_extraction_modes.py`
3. **Monitor token usage** - Check logs for truncation warnings
4. **Adjust MAX_PDF_CHARS** - Based on your model's context window

---

**Updated:** October 29, 2025
**Status:** Production-ready
