"""Score the paraphrased-gold check with the paper's scorer.

    python scripts/paraphrase_check/score.py

Scores the 10 single-pass systems on the 30 parser-ablation papers three times: against the gold of 30 April 2026
(the gold the reworded files were made from) and against each reworded gold. The original gold is read from git
history (commit aea3b7a), so the comparison does not mix in the audit corrections made to gold.parquet later. The
Responsible AI fields use the stored GLM-5 verdicts: data/judged/judge_scores_glm_5.parquet for the original gold and
data/judged/paraphrase_check_glm5_*.parquet for the reworded golds. The scorer is
scripts/figures/build_test88_headline_table.py, used unchanged: only its paper set, gold and verdicts are set here.
Writes results/paraphrase_check/scores.csv.
"""
from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "data" / "extractions" / "parser_ablation" / "sample30.json"
OUT = ROOT / "results" / "paraphrase_check"
ORIGINAL_GOLD_COMMIT = "aea3b7a"                           # gold.parquet as of 30 April 2026
SYSTEMS = ["claude_sonnet_4_6", "gpt5_4_full", "qwen3_6_35b_a3b", "claude_opus_4_7", "mistral_small_4", "glm_5_1",
           "gpt5_4_mini", "gemini_3_1_pro", "deepseek_v3_2", "llama4_scout"]


def load_scorer():
    sys.argv = sys.argv[:1]
    spec = importlib.util.spec_from_file_location("scorer", ROOT / "scripts/figures/build_test88_headline_table.py")
    scorer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scorer)
    return scorer


def original_gold() -> pd.DataFrame:
    blob = subprocess.run(["git", "show", f"{ORIGINAL_GOLD_COMMIT}:data/annotations/gold.parquet"],
                          cwd=ROOT, capture_output=True, check=True).stdout
    return pd.read_parquet(io.BytesIO(blob))


def main() -> int:
    scorer = load_scorer()
    from evaluation.score_against_gold import DEFAULT_GOLD_METHODS
    papers = frozenset(json.loads(SAMPLE.read_text())["papers"])
    conditions = {
        "original": (original_gold(), ROOT / "data/judged/judge_scores_glm_5.parquet"),
        "sonnet_4_6": (pd.read_parquet(ROOT / "data/annotations/gold_paraphrased_sonnet_4_6.parquet"),
                       ROOT / "data/judged/paraphrase_check_glm5_sonnet_4_6.parquet"),
        "gpt_5_4": (pd.read_parquet(ROOT / "data/annotations/gold_paraphrased_gpt_5_4.parquet"),
                    ROOT / "data/judged/paraphrase_check_glm5_gpt_5_4.parquet"),
    }

    scores = {}
    for name, (gold, verdicts) in conditions.items():
        gold = gold[gold["gold_method"].isin(DEFAULT_GOLD_METHODS) & gold["gold_value"].notna()]
        scorer.test = papers                               # the scorer reads these globals when it scores
        scorer.GOLD_TEST = gold[gold["paper_id"].isin(papers)]
        scorer.judges = pd.read_parquet(verdicts)[["paper_id", "field_id", "system_id", "score"]]
        scores[name] = {sid: scorer.per_cell_scores_test88(sid).groupby("field_id")["score"].mean().mean()
                        for sid in SYSTEMS}

    table = pd.DataFrame(scores).round(4)
    table.index.name = "system"
    OUT.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUT / "scores.csv")
    print(table.sort_values("original", ascending=False).to_string())
    for name in ("sonnet_4_6", "gpt_5_4"):
        shift = (table[name] - table["original"]).abs()
        rho = spearmanr(table["original"], table[name]).statistic
        print(f"{name}: Spearman {rho:.3f} vs original, max |shift| {shift.max():.3f}, mean {shift.mean():.3f}")
    print(f"\nwrote {(OUT / 'scores.csv').relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
