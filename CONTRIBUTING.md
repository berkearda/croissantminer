# Contributing

Thank you for helping improve CroissantMiner. Questions and ideas are welcome in
[Discussions](https://github.com/berkearda/croissantminer/discussions); bugs and wrong extractions go to
[issues](https://github.com/berkearda/croissantminer/issues/new/choose), which have templates. Everyone taking part
follows the [code of conduct](CODE_OF_CONDUCT.md).

## Setting up

```bash
git clone https://github.com/berkearda/croissantminer
cd croissantminer
pip install -e ".[dev,validate]"     # the extraction tool and its tests (Python 3.10 to 3.13)
pip install -r requirements.txt      # the paper's pinned environment, for the evaluation (Python 3.10 or 3.11)
```

## Tests and pull requests

- `make test` runs all tests without API keys. The tool's tests alone, with the light install:
  `python -m pytest --noconftest tests/test_cli.py tests/test_croissant_output.py`.
- Create a branch, run the tests and open a pull request; its template has a short checklist.
- For a problem with a specific paper or field, include the paper and the field name.

## What to keep in mind

- **Scoring:** `scripts/figures/build_test88_headline_table.py` and `evaluation/field_metrics.py` produce
  the numbers in the paper, and `tests/test_table2_reproduction.py` checks them. A change that alters those
  numbers needs a clear reason in the pull request.
- **Released data:** results go to new files; files in `data/` that the paper's numbers depend on are not
  overwritten.
- **A new method for the tool:** add a `Method` to `METHODS` and a branch to `run()` in
  `croissantminer/methods.py`, give it a name in `METHOD_NAMES` (`croissantminer/api.py`), and add a test.
- **New systems:** `make evaluate OUTPUTS=folder NAME=name` scores a system with the paper's scorer and judge,
  without changing the scoring files; [leaderboard/README.md](leaderboard/README.md) describes the output format
  and how to add an entry. The scoring rules are in [docs/reproducing.md](docs/reproducing.md#how-scoring-works).
