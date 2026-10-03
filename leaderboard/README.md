# Leaderboard

Extraction systems scored on the 88 test papers of the CroissantMiner benchmark with the paper's scorer. *Core*
averages the 10 core fields (scored by rules), *RAI* the 20 Responsible AI fields (scored by a judge model), and
*Composite* weights all 30 fields equally; 95% confidence intervals come from 2,000 bootstrap samples over papers (see
[how scoring works](../docs/reproducing.md#how-scoring-works)). The [leaderboard website](https://berkearda.github.io/croissantminer/) shows the same
table with each system's score on all 30 fields; it is built from `leaderboard.csv` whenever that file changes.

Claude Sonnet 4.5 drafted the gold annotations before annotators checked them, so its score is not comparable and it
is not listed (0.861 in the paper); systems built on Claude models are marked with \*. *US$ per paper* is the API cost at list prices: of
April and May 2026 for the paper's systems (the paper's Table 8), and of the day the outputs were made for systems
added later; self-hosted models ran on our own GPUs.

Systems added after the paper have no *Paper* score. They use the paper's prompt and scorer and were run with
`scripts/experiments/model_comparison/extract_all_models_batch.py` (`--model gemini-3.8-flash`, `gemini-3.8-flash-t1`,
`gpt-6.1-sol`). Gemini 3.8 Flash runs at temperature 0 as in the paper, and once at temperature 1, the value Google
recommends for Gemini 3 models; that row is listed because, on the 14 development papers, it beat temperature 0 by
more than 0.02, a rule set before the test run. GPT-6.1 Sol accepts only its default temperature (1).

<!-- table:start -->
| Rank | System | Design | Core | RAI | Composite [95% CI] | Paper | US$ per paper |
|---|---|---|---|---|---|---|---|
| 1 | Claude Sonnet 4.6\* | Single-pass | 0.752 | 0.661 | 0.692 [0.670, 0.712] | 0.709 | 0.13 |
| 2 | Claude Opus 4.7\* | Single-pass | 0.676 | 0.682 | 0.680 [0.647, 0.714] | 0.699 | 0.27 |
| 3 | GPT-5.4 | Single-pass | 0.653 | 0.653 | 0.653 [0.637, 0.680] | 0.665 | 0.09 |
| 4 | ReAct (Sonnet 4.6)\* | ReAct | 0.734 | 0.592 | 0.639 [0.613, 0.676] | 0.652 | 0.26 |
| 5 | Parallel Specialists (Sonnet 4.6)\* | Parallel Specialists | 0.699 | 0.605 | 0.636 [0.614, 0.659] | 0.647 | 0.73 |
| 6 | Gemini 3.8 Flash (temperature 1) | Single-pass | 0.597 | 0.634 | 0.622 [0.597, 0.649] |  | 0.03 |
| 7 | Qwen 3.6 35B-A3B | Single-pass | 0.698 | 0.584 | 0.622 [0.599, 0.648] | 0.634 | self-hosted |
| 8 | ReAct (GPT-5.4) | ReAct | 0.688 | 0.582 | 0.617 [0.587, 0.649] | 0.631 | 0.54 |
| 9 | Gemini 3.8 Flash | Single-pass | 0.612 | 0.616 | 0.614 [0.594, 0.635] |  | 0.03 |
| 10 | Triage + Critique (Sonnet 4.6)\* | Triage + Critique | 0.675 | 0.578 | 0.610 [0.590, 0.639] | 0.624 | 0.21 |
| 11 | GLM-5.1 | Single-pass | 0.675 | 0.573 | 0.607 [0.587, 0.628] | 0.625 | 0.06 |
| 12 | Gemini 2.5 Flash | Single-pass | 0.615 | 0.585 | 0.595 [0.573, 0.618] | 0.616 | 0.01 |
| 13 | GPT-5.4 Mini | Single-pass | 0.561 | 0.589 | 0.580 [0.555, 0.605] | 0.596 | 0.03 |
| 14 | Gemini 3.1 Pro Preview | Single-pass | 0.577 | 0.574 | 0.575 [0.556, 0.595] | 0.590 | 0.07 |
| 15 | Parallel Specialists (GPT-5.4) | Parallel Specialists | 0.627 | 0.548 | 0.574 [0.556, 0.596] | 0.589 | 0.53 |
| 16 | GPT-6.1 Sol | Single-pass | 0.465 | 0.628 | 0.574 [0.551, 0.597] |  | 0.07 |
| 17 | ReAct (Gemini 3.1 Pro) | ReAct | 0.723 | 0.498 | 0.573 [0.546, 0.598] | 0.582 | 0.30 |
| 18 | DeepSeek V3.2 | Single-pass | 0.617 | 0.525 | 0.555 [0.527, 0.583] | 0.575 | 0.01 |
| 19 | Locator-Extractor (Sonnet 4.6)\* | Locator-Extractor | 0.643 | 0.498 | 0.546 [0.521, 0.574] | 0.566 | 0.20 |
| 20 | Triage + Critique (GPT-5.4) | Triage + Critique | 0.592 | 0.522 | 0.545 [0.526, 0.572] | 0.557 | 0.16 |
| 21 | Parallel Specialists (Gemini 3.1 Pro) | Parallel Specialists | 0.607 | 0.477 | 0.520 [0.500, 0.540] | 0.539 | 0.57 |
| 22 | Mistral Small 4 | Single-pass | 0.616 | 0.460 | 0.512 [0.496, 0.528] | 0.527 | self-hosted |
| 23 | Locator-Extractor (GPT-5.4) | Locator-Extractor | 0.523 | 0.455 | 0.478 [0.456, 0.504] | 0.502 | 0.11 |
| 24 | Locator-Extractor (Gemini 3.1 Pro + GPT-5.4 Mini) | Locator-Extractor | 0.560 | 0.413 | 0.462 [0.440, 0.485] | 0.478 | 0.08 |
| 25 | Locator-Extractor (Gemini 3.1 Pro) | Locator-Extractor | 0.500 | 0.413 | 0.442 [0.414, 0.468] | 0.448 | 0.09 |
| 26 | Triage + Critique (Gemini 3.1 Pro) | Triage + Critique | 0.513 | 0.370 | 0.418 [0.397, 0.437] | 0.436 | 0.14 |
| 27 | Llama 4 Scout 17B | Single-pass | 0.506 | 0.310 | 0.375 [0.357, 0.392] | 0.391 | self-hosted |
<!-- table:end -->

## The judge

Every row was judged by GLM-5 (`z-ai/glm-5`) served by Z.AI through OpenRouter, with the paper's judge prompt,
reasoning switched off: the paper's systems on 1 October 2026, later systems when they were added (`judged_on` in
`leaderboard.csv`). *Paper* is the composite in the paper. The paper's
verdicts came from GLM-5 on DeepInfra in May 2026; DeepInfra retired that model on 10 September 2026 and now answers
requests for it with GLM-5.2, so the May verdicts cannot be repeated. The judge used here scores the systems 0.015
lower on average (0.006 to 0.025 by system), and the order is nearly the same: only Triage + Critique (Sonnet 4.6)
and GLM-5.1, 0.0007 apart in the paper, swap places. New systems are judged the same way, and the scoring script
refuses replies from any other model or provider.


## Add your system

1. **Get the papers.** `python scripts/download_papers.py` downloads the PDFs into `data/raw/`, and
   `python scripts/evaluate_system.py --list-papers` lists the 88 test papers (`--split dev` lists the 14
   development papers).
2. **Run your system** on each test paper and save one JSON file per paper, named `<paper_id>.json`, with the 30
   fields at the top level or under `"extraction"`. With CroissantMiner's own command, for example:
   `croissantminer extract data/raw/<paper_id>.pdf --method single-pass --fields outputs/<paper_id>.json`.
3. **Score it** with `make evaluate OUTPUTS=outputs NAME=my-system`. The Responsible AI answers go to the judge
   above (`OPENROUTER_API_KEY`), at most 1,152 answers or about US$0.75 per system; verdicts are cached, so a re-run
   only judges changed answers. Tune your system on the development papers (`--split dev`) and score the test papers
   once.
4. **Open a pull request** with the folder `leaderboard/<name>/` the script wrote (your outputs, the judge's verdicts
   and the scores) and a row in `leaderboard/leaderboard.csv`: the scores from `scores.json`, your team, the date
   your outputs were made (`date`, YYYY-MM-DD), a link to your code or paper (`link`), `results` set to the folder
   name, `role` set to `ranked`, and `judge` and `judged_on` from `judge` and `scored_on` in `scores.json`. Then run
   `python scripts/leaderboard_table.py` to update the table above. We check an entry by scoring its outputs again;
   once it is merged, the website updates itself.

**Rules.** Do not train or tune on the gold annotations of the test papers (they are public). Name the model and
whether its weights are open, give the cost per paper, and mark a system built on a Claude model with \*.
