.PHONY: help install test reproduce table2

help:  ## Show this help
	@grep -E '^[a-z0-9_-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  %-10s %s\n", $$1, $$2}'

install:  ## Install the dependencies and the package
	pip install -r requirements.txt
	pip install -e .

test:  ## Run all tests (no API keys needed)
	python -m pytest -q

reproduce:  ## Check Table 2 and Tables 5/6 against the published numbers
	python -m pytest -q tests/test_table2_reproduction.py

table2:  ## Print the composite score and 95% CI of every system
	python scripts/figures/build_test88_headline_table.py
