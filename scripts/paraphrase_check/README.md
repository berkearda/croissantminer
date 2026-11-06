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
```

## Result

Scored against the original-gold verdicts in `data/judged/judge_scores_glm_5.parquet`, the composite of the 10 systems
moves by at most 0.046 (mean about 0.02), and the ranking is nearly unchanged: Spearman correlation with the
original-gold ranking is 0.964 for the Sonnet 4.6 gold and 0.976 for the GPT-5.4 gold.
