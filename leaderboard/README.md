# Leaderboard

Extraction systems scored on the 88 test papers of the CroissantMiner benchmark, with the paper's scorer and judge.
*Core* averages the 10 core fields, *RAI* the 20 Responsible AI fields, and *Composite* weights all 30 fields
equally; 95% confidence intervals come from 2,000 bootstrap samples over papers (see
[how scoring works](../docs/reproducing.md#how-scoring-works)). Claude Sonnet 4.5 drafted the gold annotations
before annotators checked them, so it is shown for reference and not ranked, and systems built on Claude models are
marked with \*.

| Rank | System | Architecture | Core | RAI | Composite [95% CI] | Source |
|---|---|---|---|---|---|---|
| | *Claude Sonnet 4.5\* (reference)* | *Single-pass* | *0.903* | *0.840* | *0.861 [0.830, 0.893]* | *paper* |
| 1 | Claude Sonnet 4.6\* | Single-pass | 0.752 | 0.687 | 0.709 [0.688, 0.729] | paper |
| 2 | Claude Opus 4.7\* | Single-pass | 0.676 | 0.711 | 0.699 [0.665, 0.732] | paper |
| 3 | GPT-5.4 | Single-pass | 0.653 | 0.671 | 0.665 [0.648, 0.692] | paper |
| 4 | ReAct (Sonnet 4.6)\* | ReAct | 0.734 | 0.610 | 0.652 [0.626, 0.687] | paper |
| 5 | Parallel Specialists (Sonnet 4.6)\* | Parallel Specialists | 0.699 | 0.621 | 0.647 [0.626, 0.667] | paper |
| 6 | Qwen 3.6 35B-A3B | Single-pass | 0.698 | 0.601 | 0.634 [0.615, 0.654] | paper |
| 7 | ReAct (GPT-5.4) | ReAct | 0.688 | 0.603 | 0.631 [0.601, 0.663] | paper |
| 8 | GLM-5.1 | Single-pass | 0.675 | 0.599 | 0.625 [0.604, 0.645] | paper |
| 9 | Triage + Critique (Sonnet 4.6)\* | Triage + Critique | 0.675 | 0.599 | 0.624 [0.606, 0.653] | paper |
| 10 | Gemini 2.5 Flash | Single-pass | 0.615 | 0.616 | 0.616 [0.592, 0.639] | paper |
| 11 | GPT-5.4 Mini | Single-pass | 0.561 | 0.614 | 0.596 [0.573, 0.620] | paper |
| 12 | Gemini 3.1 Pro Preview | Single-pass | 0.577 | 0.596 | 0.590 [0.571, 0.609] | paper |
| 13 | Parallel Specialists (GPT-5.4) | Parallel Specialists | 0.627 | 0.570 | 0.589 [0.572, 0.611] | paper |
| 14 | ReAct (Gemini 3.1 Pro) | ReAct | 0.723 | 0.511 | 0.582 [0.556, 0.605] | paper |
| 15 | DeepSeek V3.2 | Single-pass | 0.617 | 0.555 | 0.575 [0.547, 0.604] | paper |
| 16 | Locator-Extractor (Sonnet 4.6)\* | Locator-Extractor | 0.643 | 0.528 | 0.566 [0.543, 0.592] | paper |
| 17 | Triage + Critique (GPT-5.4) | Triage + Critique | 0.592 | 0.540 | 0.557 [0.537, 0.585] | paper |
| 18 | Parallel Specialists (Gemini 3.1 Pro) | Parallel Specialists | 0.607 | 0.505 | 0.539 [0.518, 0.559] | paper |
| 19 | Mistral Small 4 | Single-pass | 0.616 | 0.482 | 0.527 [0.510, 0.544] | paper |
| 20 | Locator-Extractor (GPT-5.4) | Locator-Extractor | 0.523 | 0.492 | 0.502 [0.481, 0.528] | paper |
| 21 | Locator-Extractor (Gemini 3.1 Pro + GPT-5.4 Mini) | Locator-Extractor | 0.560 | 0.436 | 0.478 [0.456, 0.502] | paper |
| 22 | Locator-Extractor (Gemini 3.1 Pro) | Locator-Extractor | 0.500 | 0.422 | 0.448 [0.423, 0.471] | paper |
| 23 | Triage + Critique (Gemini 3.1 Pro) | Triage + Critique | 0.513 | 0.397 | 0.436 [0.415, 0.457] | paper |
| 24 | Llama 4 Scout 17B | Single-pass | 0.506 | 0.334 | 0.391 [0.374, 0.409] | paper |

## Add your system

1. **Get the papers.** `python scripts/download_papers.py` downloads the PDFs into `data/raw/`, and
   `python scripts/evaluate_system.py --list-papers` lists the 88 test papers (`--split dev` lists the 14
   development papers).
2. **Run your system** on each test paper and save one JSON file per paper, named `<paper_id>.json`, with the 30
   fields at the top level or under `"extraction"`. With CroissantMiner's own command, for example:
   `croissantminer extract data/raw/<paper_id>.pdf --method single-pass --fields outputs/<paper_id>.json`.
3. **Score it** with `make evaluate OUTPUTS=outputs NAME=my-system`. The Responsible AI answers go to the paper's
   GLM-5 judge on DeepInfra (`DEEPINFRA_API_KEY`), at most 1,152 answers or about $0.65 per system; verdicts are
   cached, so a re-run only judges changed answers. Tune your system on the development papers (`--split dev`) and
   score the test papers once.
4. **Open a pull request** with the folder `leaderboard/<name>/` the script wrote (your outputs, the judge's verdicts
   and the scores) and a row in the table above, with a link to your code or paper. We check an entry by scoring
   its outputs again.

**Rules.** Do not train or tune on the gold annotations of the test papers (they are public). Name the model and
whether its weights are open, give the cost per paper, and mark a system built on a Claude model with \*.
