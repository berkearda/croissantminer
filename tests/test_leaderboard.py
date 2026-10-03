"""The leaderboard script scores a new system exactly as the paper scored its own systems. No API calls."""
import importlib.util
import json
import shutil
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, REPO / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_copy_of_a_paper_system_gets_its_table2_row(tmp_path):
    evaluate = _load("evaluate_system", "scripts/evaluate_system.py")
    scorer = _load("scorer_for_leaderboard_test", "scripts/figures/build_test88_headline_table.py")
    source = scorer.STRATEGY_DIRS["claude_sonnet_4_6"]
    inputs, out = tmp_path / "inputs", tmp_path / "result"
    inputs.mkdir()
    out.mkdir()
    for paper in scorer.test:
        if (source / f"{paper}.json").exists():
            shutil.copy(source / f"{paper}.json", inputs)
    # The paper's verdicts for this system fill the cache, so nothing is sent to the judge.
    verdicts = scorer.judges[(scorer.judges.system_id == "claude_sonnet_4_6") & scorer.judges.score.notna()]
    verdicts.reindex(columns=evaluate.VERDICT_COLUMNS).to_parquet(out / "judge_verdicts.parquet", index=False)

    assert evaluate.main([str(inputs), "--name", "copy-of-sonnet-4-6", "--out", str(out)]) == 0
    result = json.loads((out / "scores.json").read_text())
    expected = pd.read_csv(REPO / "tests/expected/table2_camera_ready.csv").set_index("sid").loc["claude_sonnet_4_6"]
    for key, col in [("composite", "composite"), ("core", "core"), ("rai", "rai")]:
        assert abs(result[key] - expected[col]) < 1e-12, key
    assert abs(result["ci95"][0] - expected["ci_lo"]) < 1e-12 and abs(result["ci95"][1] - expected["ci_hi"]) < 1e-12
    assert result["scored_cells"] == expected["n_cells"] and result["unjudged_answers"] == 0
    assert result["rank"] >= 1 and len(list((out / "outputs").glob("*.json"))) == 88


def test_the_readme_table_is_the_csv():
    table = _load("leaderboard_table", "scripts/leaderboard_table.py")
    assert table.main(["--check"]) == 0, "run python scripts/leaderboard_table.py"


def test_the_paper_column_is_table2():
    board = pd.read_csv(REPO / "leaderboard/leaderboard.csv")
    expected = pd.read_csv(REPO / "tests/expected/table2_camera_ready.csv").set_index("label")
    paper = board[(board.role == "ranked") & (board.source == "paper")].set_index("system")
    assert sorted(paper.index) == sorted(expected.index)
    for name, row in paper.iterrows():
        assert abs(row.paper_composite - expected.loc[name, "composite"]) < 1e-9, name


def test_rows_added_after_the_paper_match_their_scores():
    board = pd.read_csv(REPO / "leaderboard/leaderboard.csv")
    for _, row in board[(board.role == "ranked") & (board.source != "paper")].iterrows():
        assert pd.isna(row.paper_composite), row.system
        scores = json.loads((REPO / "leaderboard" / row.results / "scores.json").read_text())
        assert scores["split"] == "test" and scores["papers"] == 88 and scores["unjudged_answers"] == 0, row.system
        for key in ("core", "rai", "composite"):
            assert abs(row[key] - scores[key]) < 1e-12, (row.system, key)
        assert abs(row.ci_low - scores["ci95"][0]) < 1e-12 and abs(row.ci_high - scores["ci95"][1]) < 1e-12, row.system
        assert row.judge == scores["judge"] and row.judged_on == scores["scored_on"], row.system
