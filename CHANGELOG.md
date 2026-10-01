# Changelog

Notable changes to CroissantMiner. Versions follow [semantic versioning](https://semver.org).

## 0.2.0 (1 October 2026)

### Added
- `croissantminer extract`: runs one of the paper's systems on a PDF, text or Markdown file and writes a
  Croissant 1.1 file with the Responsible AI fields; `croissantminer methods` lists the systems and
  `croissantminer validate` checks a Croissant file with the MLCommons validator.
- Python API: `croissantminer.extract()`.
- Optional extras: `validate` (MLCommons validator), `eval` (reproducing the paper) and `demo`.
- `croissantminer merge` and `croissantminer extract --merge-into`: add the extracted fields to the Croissant file
  a data host generates (for example Hugging Face's), keeping the host's own values.
- A guide for NeurIPS dataset submissions (`docs/neurips.md`).
- A release workflow that publishes the package to PyPI, and a CI job that builds the package and runs it outside
  the repository.
- A leaderboard (`leaderboard/README.md` and a tab in the demo) and `make evaluate`, which scores a new system with
  the paper's scorer without changing the scoring files. Every row is judged by GLM-5 served by Z.AI through
  OpenRouter, because DeepInfra, which served the paper's judge, retired GLM-5 on 10 September 2026.
- Tests for the command line and the Croissant output, run on Python 3.10 to 3.13.
- Code of conduct, security policy, issue and pull-request templates.

### Changed
- The basic install needs six packages; the libraries for the paper's evaluation moved to the `eval` extra.
  Python 3.12 and 3.13 are supported.
- The demo's code moved into the package (`croissantminer/methods.py` and `croissantminer/croissant.py`), so the
  command line, the Python API and the demo share one implementation.
- The code of the agentic systems moved from `scripts/` and `validation/` into `croissantminer/systems/`, so the
  installed package runs all six methods. The old files keep the paper's imports and commands working.
- `anthropic` is limited to versions below 1.0 and `openai` below 2.0: anthropic 1.x no longer accepts the
  temperature setting the systems use.
- `import croissantminer` no longer loads the earlier prototype; its names are loaded when first used.

### Fixed
- Croissant output: the publisher is written as an Organization, dates as ISO dates, and the file declares
  Croissant 1.1, so dataset names with spaces pass the validator.
- API calls are retried after server errors (HTTP 5xx) instead of failing.

### Removed
- The `croissantminer` command of the earlier prototype (`extract --paper`, `evaluate`).

## 0.1.0 (28 September 2026)

- Code release with the paper: benchmark, systems, scorer, the Table 2 reproduction tests and the demo.
