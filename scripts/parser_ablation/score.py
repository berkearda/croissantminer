"""Score the PDF parser ablation (Appendix C.3, Table 8) with the paper's scorer.

    python scripts/parser_ablation/score.py

Scores the eight runs in data/extractions/parser_ablation/ (Sonnet 4.6 and GPT-5.4, each with PyPDF2, PyMuPDF,
Docling with its default body-only export, and Docling with the full export) on the 30 sampled test papers. The
core fields are scored by rules; the Responsible AI fields use the stored verdicts in
data/judged/parser_ablation_glm5_2026-09-26.parquet (GLM-5 on DeepInfra, all eight runs judged in one session on
26 September 2026). The scorer is scripts/figures/build_test88_headline_table.py, used unchanged: only its paper
set, output folders and verdicts are set here. Writes results/parser_ablation/scores.csv and per_field.csv.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "data" / "extractions" / "parser_ablation"
VERDICTS = ROOT / "data" / "judged" / "parser_ablation_glm5_2026-09-26.parquet"
OUT = ROOT / "results" / "parser_ablation"
MODELS = {"sonnet_4_6": "Sonnet 4.6", "gpt_5_4": "GPT-5.4"}
PARSERS = {"pypdf2": "PyPDF2", "pymupdf": "PyMuPDF", "docling_full": "Docling, full export",
           "docling": "Docling, body only"}


def load_scorer():
    sys.argv = sys.argv[:1]
    spec = importlib.util.spec_from_file_location("scorer", ROOT / "scripts/figures/build_test88_headline_table.py")
    scorer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scorer)
    return scorer


def main() -> int:
    scorer = load_scorer()
    papers = frozenset(json.loads((RUNS / "sample30.json").read_text())["papers"])
    scorer.test = papers                                   # the scorer reads these globals when it scores
    scorer.GOLD_TEST = scorer.GOLD[scorer.GOLD["paper_id"].isin(papers)]
    scorer.judges = pd.read_parquet(VERDICTS)[["paper_id", "field_id", "system_id", "score"]]

    rows, fields = [], []
    for m, model in MODELS.items():
        for p, parser in PARSERS.items():
            sid = f"pa_{m}_{p}"                            # the system ids in the verdict file
            scorer.STRATEGY_DIRS[sid] = RUNS / f"{m}__{p}"
            cells = scorer.per_cell_scores_test88(sid)
            per_field = cells.groupby("field_id")["score"].mean()
            core = per_field[per_field.index.isin(scorer.TIER1)].mean()
            rai = per_field[per_field.index.isin(scorer.LONG_TEXT_RAI_FIELDS)].mean()
            rows.append({"model": model, "parser": parser, "papers": cells["paper_id"].nunique(),
                         "core": round(core, 4), "rai": round(rai, 4), "composite": round(per_field.mean(), 4)})
            fields += [{"model": model, "parser": parser, "field_id": f, "score": round(s, 4)}
                       for f, s in per_field.items()]
    OUT.mkdir(parents=True, exist_ok=True)
    table = pd.DataFrame(rows)
    table.to_csv(OUT / "scores.csv", index=False)
    pd.DataFrame(fields).to_csv(OUT / "per_field.csv", index=False)
    print(table.to_string(index=False))
    print(f"\nwrote {(OUT / 'scores.csv').relative_to(ROOT)} and per_field.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
