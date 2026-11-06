# Paraphrased-gold check

Data for the paraphrased-gold check in the paper (paragraph "Human-Rewritten Cells and Paraphrased Gold"): does the
score depend on the exact wording of the gold? Every free-text gold value on the 30 parser-ablation papers
(`data/extractions/parser_ablation/sample30.json`) is reworded by two models from different families, Claude Sonnet 4.6
and GPT-5.4, keeping the meaning. The 10 single-pass systems are then re-judged against each reworded gold.

Scope: the 23 free-text fields (the 20 Responsible AI fields plus `sc:creator`, `cr:citeAs` and `sc:description`),
settled non-null cells only. Constrained fields and `[NULL]` cells are copied unchanged. Sonnet 4.6 rewords 460 cells
and GPT-5.4 rewords 457.

## Files

| File | Contents |
|---|---|
| `data/annotations/gold_paraphrased_sonnet_4_6.parquet` | `gold.parquet` with the target cells reworded by Sonnet 4.6 (same schema) |
| `data/annotations/gold_paraphrased_gpt_5_4.parquet` | the same, reworded by GPT-5.4 |
| `data/judged/paraphrase_check_glm5_sonnet_4_6.parquet` | per-cell GLM-5 verdicts of the 10 systems' Responsible AI fields against the Sonnet 4.6 gold |
| `data/judged/paraphrase_check_glm5_gpt_5_4.parquet` | the same against the GPT-5.4 gold |

The verdict files have one row per paper, field and system (`paper_id`, `field_id`, `system_id`, `judge`, `score`,
`reason`, token counts, `scored_at`). All were judged in one session (GLM-5, 26 July 2026). The three short-text core
fields are scored by token-F1 against the reworded gold, as in the main results.

## Run

```bash
python scripts/paraphrase_check/paraphrase_gt.py --model sonnet-4-6   # needs ANTHROPIC_API_KEY
python scripts/paraphrase_check/paraphrase_gt.py --model gpt-5.4      # needs OPENAI_API_KEY
python scripts/paraphrase_check/score.py                              # writes results/paraphrase_check/scores.csv
```

The reworded golds are on hand, so `score.py` works without re-running the paraphraser. It uses the paper's scorer
(`scripts/figures/build_test88_headline_table.py`) unchanged. The reworded files were made from the gold of 30 April
2026, so `score.py` compares them with that same gold, read from git history (commit `aea3b7a`); comparing with
today's `gold.parquet` would mix in the audit corrections made since. Responsible AI fields use the stored GLM-5
verdicts: `data/judged/judge_scores_glm_5.parquet` for the original gold and the files above for the reworded golds.

## Result

| System | Original gold | Sonnet 4.6 reworded | GPT-5.4 reworded |
|---|---|---|---|
| Claude Sonnet 4.6 | 0.609 | 0.610 | 0.610 |
| GPT-5.4 | 0.603 | 0.591 | 0.601 |
| Claude Opus 4.7 | 0.592 | 0.573 | 0.590 |
| Qwen3.6 35B-A3B | 0.553 | 0.544 | 0.548 |
| GLM-5.1 | 0.547 | 0.540 | 0.539 |
| GPT-5.4 Mini | 0.519 | 0.516 | 0.518 |
| Gemini 3.1 Pro | 0.509 | 0.507 | 0.512 |
| DeepSeek V3.2 | 0.497 | 0.498 | 0.498 |
| Mistral Small 4 | 0.458 | 0.458 | 0.466 |
| Llama 4 Scout 17B | 0.342 | 0.340 | 0.343 |

The ranking is unchanged under both reworded golds (Spearman 1.00). Composites move by at most 0.019 (mean 0.006)
with the Sonnet 4.6 gold and at most 0.008 (mean 0.003) with the GPT-5.4 gold.
