.PHONY: install extract evaluate ablations baselines test clean help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install CroissantMiner and dependencies
	pip install -e ".[dev]"

extract: ## Extract metadata from benchmark papers (Table 1)
	python scripts/run_extraction.py --extraction-mode full-pdf

evaluate: ## Evaluate extractions against ground truth (Table 2)
	python scripts/run_evaluation.py

ablations: ## Run all ablation experiments (Table 3)
	./scripts/run_all_ablations.sh

ablations-compare: ## Show ablation comparison tables
	python scripts/run_ablations.py --compare prompt
	python scripts/run_ablations.py --compare context
	python scripts/run_ablations.py --compare few_shot

baselines: ## Run baseline experiments (Table 4)
	python scripts/baselines/keyword_baseline.py
	python scripts/baselines/hf_card_baseline.py

groundtruth: ## Build 30-field ground truth
	python scripts/build_30field_groundtruth.py

finetuning-data: ## Prepare fine-tuning data
	python scripts/prepare_finetuning_data.py --max-tokens 4096
	python scripts/validate_finetuning_data.py

annotations: ## Generate Phase 2 annotation sheets
	python scripts/prep_annotation_phase2.py

test: ## Run tests
	python -c "from croissantminer import __version__; print(f'croissantminer v{__version__}')"
	python -c "from croissantminer.metrics import bootstrap_ci, mcnemar_test, cohens_h; print('Statistical tests OK')"
	python -c "from croissantminer.extractor import setup_llm_pipeline; print('Extractor OK')"
	python scripts/run_ablations.py --list

clean: ## Clean generated files
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf build/ dist/ *.egg-info/
