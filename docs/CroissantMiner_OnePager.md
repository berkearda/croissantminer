# CroissantMiner: Automated Croissant Metadata Extraction for ML Datasets

---

## The Problem

The NeurIPS Datasets & Benchmarks track now requires Croissant metadata for all submissions. While platforms like HuggingFace and Kaggle auto-generate basic Croissant files, the **Responsible AI (RAI) fields** — covering data collection, annotation protocols, biases, limitations, and social impact — must be filled manually by authors. This is time-consuming, inconsistent, and often incomplete.

## What CroissantMiner Does

CroissantMiner is an automated framework that **extracts Croissant-compatible metadata from academic papers and dataset cards using LLMs**. It targets all 30 key Croissant fields: 10 general metadata fields (name, license, language, etc.) and 20 RAI fields (data collection, annotation protocols, biases, limitations, etc.).

**Pipeline:**
```
Paper (PDF) / Dataset Card (HF)  →  Text Extraction  →  LLM-based Field Extraction  →  Croissant JSON-LD
```

## Current Results

- **103 datasets** processed across vision, NLP, speech, and multimodal domains
- **70.6% accuracy** on 8 benchmark datasets against human-annotated ground truth
- **63.8% fill rate** across 30 metadata fields
- Human evaluation with 10+ annotators currently underway (Croissant community members)

## How It Helps Authors

- **Pre-fills RAI metadata** from their submitted manuscript — authors review and correct rather than write from scratch
- Reduces documentation burden while improving completeness and consistency
- Works with any PDF paper — no platform dependency

## How It Helps Reviewers

- Provides **structured, field-level metadata** extracted from the paper for quick assessment
- Highlights which RAI fields are covered vs. missing — enabling targeted review feedback
- Enables **automated completeness checks** (e.g., "Does the paper describe data collection methodology?")

## Potential Integration with NeurIPS D&B Track

1. **Author support tool**: At submission time, authors upload their paper and receive a pre-filled Croissant metadata file with RAI fields populated — they review, correct, and submit alongside their manuscript
2. **Reviewer support tool**: Reviewers receive a structured metadata summary extracted from the paper, highlighting documentation gaps and enabling more consistent evaluation of dataset descriptions
3. **Complementary to Eclair**: CroissantMiner extracts metadata from papers; Eclair handles the submitted dataset files — together they provide full coverage

## Team

- **Berke Arda**, MSc Data Science, ETH Zurich — Development & Evaluation
- **Dr. Mubashara Akhtar**, ETH AI Center — Supervision

Built on the Croissant metadata format (Akhtar et al., NeurIPS 2024 Spotlight).

---

**Contact:** See README.md | GitHub: [croissantminer](https://github.com/berkearda/croissantminer)
