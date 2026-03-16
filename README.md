# CroissantMiner

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-green.svg)](LICENSE)
[![Paper](https://img.shields.io/badge/NeurIPS_2026-D%26B_Track-orange.svg)](#citation)
[![Dataset](https://img.shields.io/badge/HuggingFace-Dataset-yellow.svg)](#dataset)

Automated metadata extraction from ML dataset papers using LLMs, following the [MLCommons Croissant](https://github.com/mlcommons/croissant) RAI schema.

CroissantMiner reads academic papers describing ML datasets and extracts **30 structured metadata fields** (10 general + 20 Responsible AI) in a single LLM call, achieving **71.7% accuracy** on 30-field evaluation with Claude Sonnet 4.5.

## Quick Start

### Installation

```bash
pip install -e .
```

### As a library

```python
from croissantminer import setup_llm_pipeline, extract_metadata_full_pdf

model = setup_llm_pipeline("claude-sonnet-4-5")
metadata = extract_metadata_full_pdf(paper_text, model, output_dir="./output")
```

### As a CLI

```bash
# Extract metadata from a paper
croissantminer extract --paper path/to/paper.pdf --model claude-sonnet-4-5

# Evaluate extractions against ground truth
croissantminer evaluate --results evaluation_outputs/ --groundtruth data/groundtruth/
```

### Using Make

```bash
make install          # Install package
make extract          # Run extraction pipeline
make evaluate         # Evaluate against ground truth
make ablations        # Run all ablation experiments
make test             # Verify installation
```

## Reproducing Paper Results

Each table in the paper can be reproduced with a single command:

| Paper Table | Command | Description |
|-------------|---------|-------------|
| Table 1: Model comparison | `python scripts/run_evaluation.py` | Claude vs Gemini vs GPT accuracy |
| Table 2: Prompt ablation | `python scripts/run_ablations.py --type prompt --all` | Full vs minimal prompt |
| Table 3: Context ablation | `python scripts/run_ablations.py --type context --all` | Full vs truncated input |
| Table 4: Few-shot ablation | `python scripts/run_ablations.py --type few_shot --all` | 0-shot vs 1-shot vs 3-shot |
| Table 5: Field accuracy | `python scripts/run_ablations.py --compare prompt` | Per-field breakdown |
| Table 6: Statistical tests | `python -c "from croissantminer.metrics import run_all_significance_tests; run_all_significance_tests('evaluation_outputs')"` | Bootstrap CIs, McNemar's test |

Full step-by-step reproduction guide: [docs/REPRODUCTION.md](docs/REPRODUCTION.md)

## Project Structure

```
croissantminer/
  croissantminer/          # Main package
    config.py              # Prompts, field definitions, extraction guides
    extractor.py           # Core extraction pipeline
    evaluator.py           # Evaluation logic
    metrics.py             # Statistical tests (bootstrap CI, McNemar, Cohen's h)
    models/                # Model backends (Claude, Gemini, GPT, Qwen)
  scripts/
    run_extraction.py      # Extract metadata from papers
    run_evaluation.py      # Evaluate against ground truth
    run_ablations.py       # Ablation experiments
    build_30field_groundtruth.py  # Build 30-field ground truth
    prepare_finetuning_data.py    # Prepare LoRA training data
  data/
    groundtruth/           # 16-field human annotations (8 datasets)
    groundtruth_30field/   # 30-field ground truth (8 datasets)
    annotations/           # Pilot and Phase 2 annotation study
  experiments/             # Experiment scripts and results
  docs/                    # Documentation
```

## Key Results

- **71.7% accuracy** on 30-field evaluation (8 benchmark datasets)
- **+13.9pp improvement** from extraction guides on RAI fields
- **Context ablation**: 75% input reduction loses only 0.4pp accuracy
- **Prompt ablation**: Field-specific extraction guides improve RAI fields by +25pp (dataAnnotationProtocol) while general fields perform well with minimal prompting
- **Pilot annotation study**: 17 annotators, 252 annotations, 80.6% AI extraction accuracy

## Supported Models

| Model | Accuracy | Notes |
|-------|----------|-------|
| Claude Sonnet 4.5 | **71.7%** | Primary model, best RAI field performance |
| Gemini 2.5 Pro | 70.8% | Comparable overall, different field strengths |
| GPT-4o-mini | 64.7% | Lower cost, lower accuracy |
| Qwen 2.5 7B | TBD | Fine-tuning target (LoRA + DPO) |

## Citation

```bibtex
@inproceedings{arda2026croissantminer,
  title={CroissantMiner: Automated Responsible AI Metadata Extraction for ML Datasets},
  author={Arda, Berke and Akhtar, Mubashara and others},
  booktitle={Advances in Neural Information Processing Systems (NeurIPS), Datasets and Benchmarks Track},
  year={2026}
}
```

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Update Log

| Date | Update |
|------|--------|
| 2026-03-16 | Ablation experiments complete (prompt, context, few-shot) |
| 2026-03-15 | Phase 2 annotation sheets generated (23 annotators, 2,490 annotations) |
| 2026-03-15 | 30-field ground truth built, evaluation expanded from 16 to 30 fields |
| 2026-03-15 | Pilot annotation analysis: 17 annotators, 80.6% accuracy, kappa=0.005 |
| 2026-03-15 | Statistical significance testing added (bootstrap CI, McNemar, Cohen's h) |
| 2026-03-15 | Extraction prompt improvements: +30pp datePublished, +25pp dataAnnotationProtocol |
