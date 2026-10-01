# Reproducing the paper

How to re-run the extraction systems on the benchmark, and the exact rules behind the scores. Checking the paper's
numbers from the stored outputs needs neither of these: `make reproduce`, `make table2` and `make significance`
work without API keys (see "Reproducing the paper" in the [README](../README.md)). Use the paper's environment:
Python 3.10 or 3.11 with the pinned versions in `requirements.txt`.

## Running the systems on the benchmark

The benchmark PDFs are not redistributed. Download them from their public sources into `data/raw/` with
`python scripts/download_papers.py`. The commands below use the Claude Sonnet 4.6 backbone; the backbone names
are listed in `croissantminer/systems/helpers.py` (`MODELS`).

| System | Code | Command |
|---|---|---|
| Single-pass | `scripts/experiments/model_comparison/extract_all_models.py` | `python scripts/experiments/model_comparison/extract_all_models.py --model claude-sonnet-4-6` |
| ReAct | `croissantminer/react_agent/` | `python scripts/run_react_agent.py --split test --backbone sonnet-4-6 --prompt-variant v3` |
| Parallel Specialists | `croissantminer/systems/specialists.py` | `python scripts/multi_agents/run.py --config premium --prompt-variant v4 --test-only` |
| Triage + Critique | `croissantminer/systems/triage_critique.py` | `python scripts/agentic_v2.py --backbone sonnet-4-6 --prompt-variant v4` |
| Locator-Extractor | `croissantminer/systems/locator_extractor.py` | `python scripts/agentic_lev.py --locator-backbone sonnet-4-6 --extractor-backbone sonnet-4-6 --prompt-variant v3` |

Notes on re-running:

- **Outputs** go to `data/extractions/<system>/`. The released outputs are already there, and the scripts skip
  papers that have an output, so work in a copy of the repository (or move the folder away) to re-run a system.
  The reproduction test reads these folders.
- **Single-pass rows of Table 2** were produced with the batch version of the script above,
  `scripts/experiments/model_comparison/extract_all_models_batch.py` (Claude, GPT-5.4 and Gemini models), with
  `scripts/euler/extract_api_models.py` (DeepSeek V3.2 and GLM-5.1) and with `scripts/euler/extract_openmodels.py`
  on vLLM (Llama 4 Scout, Qwen 3.6 and Mistral Small 4).
- **Triage + Critique** reads the stored Gemini 2.5 Flash triage in `data/agentic/phase1/` (included).
  **Locator-Extractor** also needs a section index of each paper, which contains the paper text and is not
  redistributed: build it with `python scripts/agentic_phase0.py` after downloading the PDFs. Its GPT-5.4 and
  Gemini 3.1 Pro rows use `--backbone <model>`, which takes the stored triage as the locator.
- **Prompts:** single-pass extraction uses the prompt in `croissantminer/config.py` at temperature 0 (Claude
  Opus 4.7 does not accept a temperature setting) and gives the model the full paper text; the ranked
  single-pass outputs record the prompt's hash (`1e1cfdd99246bbf5`) in their `_meta` block. The agentic systems
  keep their own prompts next to their code.
- **Names in the code:** Triage + Critique is `agentic_v2`, Locator-Extractor `agentic_lev` (or LEV), and
  Parallel Specialists `specialist`. Their code moved to `croissantminer/systems/`; the commands above keep working.

## How scoring works

- **Core fields (rule-based):** 7 fields are scored as match or no match after normalization: license,
  language, live dataset and URL must be equal after normalization; the date must have the same year; the name
  matches if one contains the other or their words overlap as subsets; the publisher matches if at least half
  of the words of the shorter one are shared. Creator, citation and description are scored with token F1.
  See `evaluation/field_metrics.py`.
- **RAI fields (LLM judge):** GLM-5 compares each answer with the gold value on a 3-point scale: correct (1),
  partially correct (0.5), wrong (0). Prompt and calls: `scripts/judge_rerun_test88.py`.
- **Empty values:** when the paper does not report a field, the gold value is `[NULL - not found in paper]`.
  If the system also leaves the field empty, the cell is not scored; if it fills it in, the cell scores 0.
  A field the paper reports but the system leaves empty also scores 0. An answer counts as empty only when it
  is missing, `null` or blank; a text answer such as "null" or "N/A" is scored like any other answer.
- **Composite:** the mean of each field over the test papers, then the mean over the 30 fields.

`scripts/figures/build_test88_headline_table.py` applies these rules (it is the exact file behind the paper's
numbers, so its internal comments are left as they were); `tests/test_scoring_rules.py` shows each rule on a
small example. `data/README.md` describes the data files.
