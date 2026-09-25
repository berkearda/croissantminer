# Contributing to CroissantMiner

## Development Setup

```bash
git clone https://github.com/croissantminer/croissantminer.git
cd croissantminer
pip install -e ".[dev]"
cp .env.example .env  # Add your API keys
make test             # Verify installation
```

## Branch Naming

- `feat/description` — New features
- `fix/description` — Bug fixes
- `exp/description` — Experiments (ablations, baselines)
- `docs/description` — Documentation

## PR Process

1. Create a branch from `main`
2. Make changes and test locally (`make test`)
3. Open PR with description of changes
4. Tag `@berkearda` for review

## Contributor Tasks

### Contributor: Keyword Baseline + Figures

**Branch:** `feat/keyword-baseline`

**Task:** Build a regex/keyword extraction baseline that extracts metadata without using any LLM.

**Files to create/modify:**
- `scripts/baselines/keyword_baseline.py` — Main baseline script
  - Input: PDF text
  - Output: 30-field metadata JSON
  - Strategy: regex patterns, section headers, keyword matching
- `scripts/baselines/generate_figures.py` — Publication figures
  - Accuracy bar chart (per-dataset)
  - Field-level heatmap (dataset x field)
  - Model comparison radar chart

**Evaluation:** Run against same 8 benchmark datasets using `make evaluate`.

### Nobin: HuggingFace Card Baseline + Annotation Analysis

**Branch:** `feat/hf-card-baseline`

**Task 1:** Build a baseline that extracts metadata from HuggingFace dataset cards (README.md) instead of papers.

**Files to create/modify:**
- `scripts/baselines/hf_card_baseline.py`
  - Use `huggingface_hub` library to fetch dataset cards
  - Parse YAML frontmatter + markdown sections
  - Map to 30 Croissant fields
  - Compare: card-only vs paper-only vs combined

**Task 2:** Annotation quality analysis for the paper.

**Files to create/modify:**
- `scripts/analyze_annotations.py` (update existing)
  - Compute Fleiss' kappa, Krippendorff's alpha on Phase 2 data
  - Generate IAA tables for the paper
  - Error categorization (hallucination vs incomplete vs wrong field)

### Sebastian: Health Domain Extension

**Branch:** `feat/health-domain`

**Task:** Test CroissantMiner on biomedical/health ML datasets.

**Files to create/modify:**
- `scripts/health_domain_eval.py`
  - Select 10-15 health/medical ML dataset papers
  - Run extraction pipeline
  - Create domain-specific ground truth
  - Evaluate: does CroissantMiner generalize beyond CS datasets?
- Additional RAI fields relevant to health (PII, consent, IRB)

## Code Style

- Python 3.10+ type hints where useful
- No unnecessary abstractions — keep it simple
- `ruff` for formatting (run `ruff check .`)
