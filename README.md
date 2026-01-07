# CroissantMiner

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

Automated metadata extraction from ML dataset papers using LLMs, following the [MLCommons Croissant](https://github.com/mlcommons/croissant) RAI schema.

## Features

- Extract **30 metadata fields** (10 general + 20 RAI) from academic papers
- Full-PDF extraction mode for efficient processing
- Support for multiple LLM backends (Claude, Gemini, GPT)
- Evaluation framework with ground truth comparison
- 8 benchmark datasets included

## Installation

```bash
git clone https://github.com/berkearda/croissantminer.git
cd croissantminer
pip install -r requirements.txt
```

## Quick Start

1. Create a `.env` file with your API key:
```
ANTHROPIC_API_KEY=your_api_key_here
```

2. Run extraction on all benchmark datasets:
```bash
python test_new_prompts.py
```

## Results

| Model | Accuracy | Fill Rate |
|-------|----------|-----------|
| Claude Sonnet 4.5 | 70.6% | 63.8% |

Tested on 8 benchmark datasets: MLS, FLORES, CIFAR, Visual Genome, MSCOCO, MMLU, MMMU, MathVista

## Metadata Schema

**General Fields (10):** name, description, url, license, creator, publisher, datePublished, inLanguage, citeAs, isLiveDataset

**RAI Fields (20):** dataCollection, dataCollectionType, dataCollectionMissingData, dataCollectionRawData, dataCollectionTimeframe, dataImputationProtocol, dataManipulationProtocol, dataPreprocessingProtocol, dataAnnotationProtocol, dataAnnotationPlatform, dataAnnotationAnalysis, annotationsPerItem, annotatorDemographics, machineAnnotationTools, dataReleaseMaintenancePlan, personalSensitiveInformation, dataSocialImpact, dataBiases, dataLimitations, dataUseCases

## Documentation

- [CLAUDE.md](CLAUDE.md) - Development guide and full schema documentation
- [PROMPTS.md](PROMPTS.md) - Prompt engineering documentation
- [model_comparison/](model_comparison/) - Multi-model comparison reports

## Project Structure

```
croissantminer/
├── models/          # LLM implementations
├── evaluation/      # Evaluation framework
├── data/            # PDF papers and results
├── groundtruth/     # Ground truth annotations
└── pdf/             # PDF processing utilities
```

## License

MIT
