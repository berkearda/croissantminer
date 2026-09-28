# Contributing

Thank you for your interest in CroissantMiner.

- **Questions and bug reports:** please open a GitHub issue. For a problem with a specific paper or field,
  include the paper id and the field name.
- **Pull requests:** create a branch, run `make test` and open the pull request. The tests must pass
  without API keys.
- **Scoring:** `scripts/figures/build_test88_headline_table.py` and `evaluation/field_metrics.py` produce
  the numbers in the paper, and `tests/test_table2_reproduction.py` checks them. A change that alters those
  numbers needs a clear reason in the pull request.
- **New systems:** write one JSON file per paper with the 30 fields to `data/extractions/<name>/`, register
  it in `evaluation/score_against_gold.py` (`STRATEGY_DIRS`), judge its RAI fields with
  `scripts/judge_rerun_test88.py`, and see "How scoring works" in the README.
