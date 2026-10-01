.PHONY: help install test reproduce table2 significance evaluate

help:  ## Show this help
	@grep -E '^[a-z0-9_-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  %-10s %s\n", $$1, $$2}'

install:  ## Install the dependencies and the package
	pip install -r requirements.txt
	pip install -e .

test:  ## Run all tests (no API keys needed)
	python -m pytest -q

reproduce:  ## Check Table 2 and Tables 5/6 against the published numbers
	python -m pytest -q tests/test_table2_reproduction.py

table2:  ## Print Table 2 with Core, RAI, Composite and 95% CIs
	python scripts/figures/print_table2.py

significance:  ## Pairwise significance tests between the Table 2 systems (about 1 minute)
	python scripts/figures/pairwise_significance.py

evaluate:  ## Score your own system: make evaluate OUTPUTS=folder NAME=name (see leaderboard/README.md)
	python scripts/evaluate_system.py $(OUTPUTS) --name $(NAME)
