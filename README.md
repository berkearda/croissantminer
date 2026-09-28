# CroissantMiner

Code for **CroissantMiner: Automated Extraction and Validation of Croissant Metadata for ML Datasets**
(NeurIPS 2026, Evaluations and Datasets Track).

Paper: arXiv link follows · [Dataset](https://huggingface.co/datasets/croissantminer/croissantminer) · [Demo](https://huggingface.co/spaces/bearda/croissantminer)

CroissantMiner is a benchmark and a set of systems for extracting [Croissant](https://github.com/mlcommons/croissant)
metadata from ML dataset papers. The benchmark covers all 30 fields of the Croissant 1.1 schema: 10 core fields
and 20 Responsible AI (RAI) fields.

- **Benchmark:** 602 dataset papers. 102 have human-validated gold annotations (3,060 cells, 22 annotators) and
  500 have LLM-generated silver annotations. The 102 gold papers are split into 14 development and 88 test papers.
- **Systems:** single-pass extraction and four agentic architectures (ReAct, Parallel Specialists,
  Triage + Critique, Locator-Extractor), each with several LLM backbones.
- **Evaluation:** rule-based scoring for the 10 core fields, an LLM judge (GLM-5) for the 20 RAI fields, and tests
  that check the scorer against the numbers in the paper.

## Results

Test split (88 papers). *Core* averages the 10 core fields, *RAI* the 20 RAI fields, and *Composite* weights all
30 fields equally; 95% confidence intervals come from 2,000 bootstrap samples over papers. The gold annotations
were first drafted by Claude Sonnet 4.5 and then checked and corrected by annotators, so Anthropic-family
systems are marked with \*. Claude Sonnet 4.5 itself is shown for reference and not ranked.

| System | Architecture | Core | RAI | Composite [95% CI] |
|---|---|---|---|---|
| Claude Sonnet 4.6\* | Single-pass | 0.752 | 0.687 | **0.709** [0.688, 0.729] |
| Claude Opus 4.7\* | Single-pass | 0.676 | 0.711 | 0.699 [0.665, 0.732] |
| GPT-5.4 | Single-pass | 0.653 | 0.671 | 0.665 [0.648, 0.692] |
| Qwen 3.6 35B-A3B | Single-pass | 0.698 | 0.601 | 0.634 [0.615, 0.654] |
| GLM-5.1 | Single-pass | 0.675 | 0.599 | 0.625 [0.604, 0.645] |
| Gemini 2.5 Flash | Single-pass | 0.615 | 0.616 | 0.616 [0.592, 0.639] |
| GPT-5.4 Mini | Single-pass | 0.561 | 0.614 | 0.596 [0.573, 0.620] |
| Gemini 3.1 Pro Preview | Single-pass | 0.577 | 0.596 | 0.590 [0.571, 0.609] |
| DeepSeek V3.2 | Single-pass | 0.617 | 0.555 | 0.575 [0.547, 0.604] |
| Mistral Small 4 | Single-pass | 0.616 | 0.482 | 0.527 [0.510, 0.544] |
| Llama 4 Scout 17B | Single-pass | 0.506 | 0.334 | 0.391 [0.374, 0.409] |
| ReAct (Sonnet 4.6)\* | ReAct | 0.734 | 0.610 | 0.652 [0.626, 0.687] |
| ReAct (GPT-5.4) | ReAct | 0.688 | 0.603 | 0.631 [0.601, 0.663] |
| ReAct (Gemini 3.1 Pro) | ReAct | 0.723 | 0.511 | 0.582 [0.556, 0.605] |
| Parallel Specialists (Sonnet 4.6)\* | Parallel Specialists | 0.699 | 0.621 | 0.647 [0.626, 0.667] |
| Parallel Specialists (GPT-5.4) | Parallel Specialists | 0.627 | 0.570 | 0.589 [0.572, 0.611] |
| Parallel Specialists (Gemini 3.1 Pro) | Parallel Specialists | 0.607 | 0.505 | 0.539 [0.518, 0.559] |
| Triage + Critique (Sonnet 4.6)\* | Triage + Critique | 0.675 | 0.599 | 0.624 [0.606, 0.653] |
| Triage + Critique (GPT-5.4) | Triage + Critique | 0.592 | 0.540 | 0.557 [0.537, 0.585] |
| Triage + Critique (Gemini 3.1 Pro) | Triage + Critique | 0.513 | 0.397 | 0.436 [0.415, 0.457] |
| Locator-Extractor (Sonnet 4.6)\* | Locator-Extractor | 0.643 | 0.528 | 0.566 [0.543, 0.592] |
| Locator-Extractor (GPT-5.4) | Locator-Extractor | 0.523 | 0.492 | 0.502 [0.481, 0.528] |
| Locator-Extractor (Gemini 3.1 Pro + GPT-5.4 Mini) | Locator-Extractor | 0.560 | 0.436 | 0.478 [0.456, 0.502] |
| Locator-Extractor (Gemini 3.1 Pro) | Locator-Extractor | 0.500 | 0.422 | 0.448 [0.423, 0.471] |
| *Claude Sonnet 4.5\* (reference)* | *Single-pass* | *0.903* | *0.840* | *0.861 [0.830, 0.893]* |

## Installation

Python 3.10 or newer.

```bash
git clone https://github.com/berkearda/croissantminer
cd croissantminer
pip install -r requirements.txt
pip install -e .
```

API keys are only needed to run the systems or the judge. Copy `.env.example` to `.env` and fill in the keys for
the providers you use.

## Reproducing the paper's numbers

No API keys and no cost: the scores are recomputed from the stored system outputs
(`data/extractions/`), judge verdicts (`data/judged/`) and gold annotations
(`data/annotations/gold.parquet`), which are included in this repository.

1. Check Table 2 and the per-field Tables 5 and 6 against the published numbers:
   ```bash
   pytest tests/test_table2_reproduction.py
   ```
2. Print the composite score and confidence interval of every system:
   ```bash
   python scripts/figures/build_test88_headline_table.py
   ```

## Running the systems

The benchmark PDFs are not redistributed. Download them from their public sources into `data/raw/` with
`python scripts/download_papers.py`. The commands below use the Claude Sonnet 4.6 backbone; each script lists
the other backbones in `--help`.

| System | Code | Command |
|---|---|---|
| Single-pass | `scripts/experiments/model_comparison/extract_all_models.py` | `python scripts/experiments/model_comparison/extract_all_models.py --model claude-sonnet-4-6` |
| ReAct | `croissantminer/react_agent/` | `python scripts/run_react_agent.py --split test --backbone sonnet-4-6 --prompt-variant v3` |
| Parallel Specialists | `scripts/multi_agents/` | `python scripts/multi_agents/run.py --config premium --prompt-variant v4 --test-only` |
| Triage + Critique | `scripts/agentic_v2.py` | `python scripts/agentic_v2.py --backbone sonnet-4-6 --prompt-variant v4` |
| Locator-Extractor | `scripts/agentic_lev.py` | `python scripts/agentic_lev.py --locator-backbone sonnet-4-6 --extractor-backbone sonnet-4-6 --prompt-variant v3` |

Single-pass extraction uses the prompt in `croissantminer/config.py` at temperature 0 and gives the model the
full paper text; each output records the prompt's hash (`1e1cfdd99246bbf5`) in its `_meta` block. The agentic
systems keep their own prompts next to their code. In the code, Triage + Critique is called `agentic_v2`,
Locator-Extractor `agentic_lev` (or LEV), and Parallel Specialists `specialist`.

## How scoring works

- **Core fields (rule-based):** normalized exact match for 7 fields (name, license, language, live dataset,
  date published, publisher, URL) and token F1 for 3 (creator, citation, description). See
  `evaluation/field_metrics.py`.
- **RAI fields (LLM judge):** GLM-5 compares each answer with the gold value on a 3-point scale: correct (1),
  partially correct (0.5), wrong (0). Prompt and calls: `scripts/judge_rerun_test88.py`.
- **Empty values:** when the paper does not report a field, the gold value is `[NULL - not found in paper]`.
  If the system also leaves the field empty, the cell is not scored; if it fills it in, the cell scores 0.
  A field the paper reports but the system leaves empty also scores 0.
- **Composite:** the mean of each field over the test papers, then the mean over the 30 fields.

`scripts/figures/build_test88_headline_table.py` applies these rules; `tests/test_scoring_rules.py` shows each
rule on a small example.

## Tests

```bash
pytest
```

About 100 tests, about 10 seconds, no API keys. They cover the scoring rules, the handling of model output,
and the check that Table 2 and Tables 5 and 6 are reproduced exactly. GitHub Actions runs them on every push.

## Repository layout

| Path | Contents |
|---|---|
| `croissantminer/` | Package: extraction prompt and configuration, PDF reading, ReAct agent, CLI |
| `scripts/` | The other systems, judge, figures and tables (`figures/`, `camera_ready/`), open-weight runs on a Slurm cluster (`euler/`) |
| `evaluation/` | Field metrics and system registry used by the scorer |
| `tests/` | Tests and the published numbers they check against |
| `hf_space/` | The Hugging Face Space demo |

The scripts that read the named annotation sheets are not included, to protect the annotators'
privacy; `data/annotations/gold.parquet` and `data/annotations/iaa.parquet` are their output.
The repository also contains early experiments that are not part of the paper (`experiments/`, `finetuning/`,
`validation/test_experiments.py`). Comments that cite `decisions.md` or task numbers (`T-###`) refer to our
internal project log, which is not included.

## Citation

```bibtex
@inproceedings{arda2026croissantminer,
  title     = {CroissantMiner: Automated Extraction and Validation of Croissant Metadata for ML Datasets},
  author    = {Arda, Berke and Akhtar, Mubashara and Yavuz, Ahmetcan and Gerry, Paul and
               Lobentanzer, Sebastian and Sarwar, Nobin and Giner-Miguelez, Joan and
               Chen, Kongtao and Zhang, Luyao and Sachan, Mrinmaya},
  booktitle = {Advances in Neural Information Processing Systems (Evaluations and Datasets Track)},
  year      = {2026}
}
```

## License

Code: MIT (see `LICENSE`). Annotations: CC BY 4.0 (see the dataset card). The papers remain under their
authors' licenses.
