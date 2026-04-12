# Contributing to CroissantMiner

Thank you for your interest in contributing to CroissantMiner!

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/croissantminer-dev.git`
3. Install dependencies: `pip install -e .`
4. Create a feature branch: `git checkout -b feature/your-feature`

## Development Setup

```bash
# Install in development mode
pip install -e .

# Set up API keys (copy and fill in)
cp .env.example .env

# Run validation tests
python validation/run_all.py --quick
```

## Making Changes

1. Make your changes on a feature branch
2. Run the validation suite: `python validation/run_all.py --quick`
3. Ensure all tests pass before submitting a PR
4. Write clear commit messages describing what and why

## Code Style

- Python 3.10+
- Follow existing code patterns and naming conventions
- Add validation tests for new evaluation metrics
- Use type hints where practical

## What to Contribute

- Bug fixes and improvements to the extraction pipeline
- New evaluation metrics or validators
- Documentation improvements
- Additional experiment scripts
- Support for new LLM providers

## Data

Large data files (PDFs, extraction outputs, annotation sheets) are NOT stored in git. They are hosted on HuggingFace and Zenodo. See the README for data access instructions.

## Questions?

Open an issue on GitHub or reach out to the maintainers.
