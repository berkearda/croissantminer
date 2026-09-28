"""Recompute Table 2 and the per-field Tables 5/6 of the paper from the stored
system outputs and judge verdicts, and compare with the published numbers
(tests/expected/, written by scripts/camera_ready/build_camera_ready_tables.py).

Needs the released data in data/ (see README, "Reproducing the paper"); skipped
when it is not there. No API calls.
"""
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]
EXPECTED = Path(__file__).resolve().parent / "expected"
RERUN = "_rerun2609"

DATA_FILES = [
    "data/annotations/gold.parquet",
    "data/agentic/dev_test_split.json",
    "data/judged/judge_scores_v2min_glm5.parquet",
    "data/judged/judge_scores_v2min_glm5_gapfill_2026-09.parquet",
    "data/judged/judge_scores_v2min_glm5_lev_rerun_2026-09.parquet",
]


def missing_inputs():
    sys.path.insert(0, str(REPO))
    from evaluation.score_against_gold import STRATEGY_DIRS

    missing = [f for f in DATA_FILES if not (REPO / f).exists()]
    for sid in pd.read_csv(EXPECTED / "table2_camera_ready.csv")["sid"]:
        base = sid[: -len(RERUN)] if sid.endswith(RERUN) else sid
        d = STRATEGY_DIRS[base]
        d = d.parent / sid if sid.endswith(RERUN) else d
        if not d.is_dir():
            missing.append(str(d.relative_to(REPO)))
    return missing


@pytest.fixture(scope="module")
def tables():
    missing = missing_inputs()
    if missing:
        pytest.skip(f"released data not found ({len(missing)} inputs missing, e.g. {missing[0]})")
    spec = importlib.util.spec_from_file_location(
        "build_camera_ready_tables", REPO / "scripts/camera_ready/build_camera_ready_tables.py")
    t = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(t)
    return t.table2_numbers(), t.per_field_numbers()


def test_table2(tables):
    got = tables[0].set_index("sid")
    exp = pd.read_csv(EXPECTED / "table2_camera_ready.csv").set_index("sid")
    assert list(got.index) == list(exp.index)
    for col in ["core", "rai", "composite", "ci_lo", "ci_hi"]:
        np.testing.assert_allclose(got[col], exp[col], rtol=0, atol=1e-12, err_msg=col)
    for col in ["n_papers", "n_cells"]:
        assert got[col].tolist() == exp[col].tolist(), col


def test_headline_number(tables):
    best = tables[0].sort_values("composite", ascending=False).iloc[0]
    assert best["sid"] == "claude_sonnet_4_6"
    assert round(best["composite"], 3) == 0.709


def test_per_field_tables(tables):
    exp = pd.read_csv(EXPECTED / "per_field_camera_ready.csv", index_col=0)
    got = tables[1].loc[exp.index, exp.columns]
    np.testing.assert_allclose(got.to_numpy(float), exp.to_numpy(float), rtol=0, atol=1e-12)
