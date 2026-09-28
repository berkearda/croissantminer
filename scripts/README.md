# Scripts

The scripts behind the paper, by purpose. Other scripts in this folder come from earlier stages of the
project and are not needed to reproduce the paper.

**Extraction systems**

| Script | Purpose |
|---|---|
| `experiments/model_comparison/extract_all_models.py` | Single-pass extraction (real-time APIs) |
| `experiments/model_comparison/extract_all_models_batch.py` | Single-pass extraction through the providers' batch APIs |
| `run_react_agent.py` | ReAct (agent code in `croissantminer/react_agent/`) |
| `multi_agents/` | Parallel Specialists |
| `agentic_v2.py` | Triage + Critique |
| `agentic_lev.py` | Locator-Extractor |
| `agentic_phase0.py` | Builds the section index Locator-Extractor needs (`data/agentic/phase0/`, not redistributed because it contains the paper text); run it after downloading the PDFs |
| `agentic_phase1.py` | Gemini 2.5 Flash triage; its outputs for the benchmark papers are included in `data/agentic/phase1/` |
| `_agentic_helpers.py` | Shared model clients, output handling and the `_meta` provenance block |
| `euler/` | Open-weight models served with vLLM on a Slurm cluster (`extract_openmodels.py`), and the hosted-API runs for DeepSeek V3.2 and GLM-5.1 (`extract_api_models.py`) |
| `download_papers.py` | Downloads the benchmark PDFs into `data/raw/` |

**Evaluation, tables and figures**

| Script | Purpose |
|---|---|
| `judge_rerun_test88.py` | GLM-5 judge for the RAI fields (prompt and calls) |
| `figures/build_test88_headline_table.py` | Table 2 scorer: cell rules, field-weighted composite, bootstrap CIs |
| `figures/print_table2.py` | Prints Table 2 grouped as in the paper (`make table2`) |
| `figures/pairwise_significance.py` | Paired bootstrap, Wilcoxon and McNemar tests with BH-FDR over all Table 2 pairs (`make significance`) |
| `camera_ready/` | Per-field tables, cost table, coverage figures, judge gap-fill and the Locator-Extractor re-run |
| `judge_sweep_qwen3.py`, `score_qwen3_sweep.py` | Qwen3 model-size sweep (appendix; its outputs are not in the repository yet) |
| `pilot_aggregate_and_score.py`, `pilot_ranking_stability.py`, `pilot_table2_style.py`, `judge_pilot_gold.py` | Re-annotation pilot for the seed-model check (appendix; its data will be released with the dataset) |
| `compare_judges_test88.py` | Composite scores under different judge versions |
| `audit/` | Judge audit sheets and rubric calibration |
| `annotations/build_croissant.py` | Croissant JSON-LD description of the dataset |
