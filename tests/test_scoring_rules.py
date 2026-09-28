"""Cell-level rules of the Table 2 scorer, checked on a hand-made benchmark
(see conftest.py for the toy gold, outputs and judge verdicts)."""
import math

import numpy as np
import pytest

from conftest import NULL_CASES

EXPECTED_CELLS = {
    ("P1", "sc:license"): 1.0,         # exact match
    ("P1", "sc:name"): 0.0,            # gold documented, output empty
    ("P1", "rai:dataBiases"): 1.0,     # judge verdict 1
    ("P2", "sc:license"): 0.0,         # gold is NULL, output filled in
    ("P2", "sc:name"): 1.0,            # exact match
    ("P2", "rai:dataBiases"): 0.5,     # judge verdict 2
    ("P2", "rai:dataCollection"): 0.0, # gold documented, output empty
    ("P3", "rai:dataBiases"): 0.0,     # judge verdict 3
}


def test_every_cell_scored_as_expected(toy_scores):
    assert toy_scores["by_cell"] == EXPECTED_CELLS


def test_null_gold_with_empty_output_is_not_scored(toy_scores):
    assert ("P1", "rai:dataCollection") not in toy_scores["by_cell"]
    assert ("P3", "sc:license") not in toy_scores["by_cell"]  # gold "Unknown", output None


def test_unsettled_gold_is_excluded(toy_scores):
    assert ("P3", "sc:name") not in toy_scores["by_cell"]


def test_dev_papers_are_excluded(toy_scores):
    assert all(paper != "D1" for paper, _ in toy_scores["by_cell"])


def test_paper_without_output_file_is_left_out(toy_scores):
    assert all(paper != "P4" for paper, _ in toy_scores["by_cell"])


def test_rai_cell_without_verdict_is_not_scored(toy_scores):
    # The released verdict files cover every cell Table 2 needs; a new system
    # has to be judged first (scripts/judge_rerun_test88.py).
    assert ("P3", "rai:dataCollection") not in toy_scores["by_cell"]


def test_field_split(toy_scores):
    assert set(toy_scores["tier1"]) >= {"sc:license", "sc:name"}
    assert toy_scores["rai"] == ["rai:dataBiases", "rai:dataCollection"]


def test_composite_weights_fields_equally(toy_scores):
    # Field means: license 0.5, name 0.5, dataBiases 0.5, dataCollection 0.0.
    point = toy_scores["ci"][0]
    assert point == pytest.approx(0.375)
    cell_mean = np.mean(list(EXPECTED_CELLS.values()))
    assert not math.isclose(point, cell_mean)  # 0.4375 would mean cell weighting


def test_bootstrap_is_deterministic_and_brackets_point(toy_scores):
    point, lo, hi = toy_scores["ci"]
    assert toy_scores["ci_again"] == toy_scores["ci"]
    assert lo <= point <= hi


NULL_EXPECTED = {
    None: True, "": True, "   ": True, "null": True, "None": True, "N/A": True,
    "n/a.": True, "NA": True, "unknown": True, "Unknown.": True, "not disclosed": True,
    "Not specified": True, "[NULL - not found in paper]": True, "[NULL]": True,
    "[N/A - not stated]": True, "Not found in paper": True,
    "The license is not mentioned in paper.": True,
    # Real values that merely start like a missing marker (fixed 2026-09-26).
    "Natural Questions": False, "National University of Singapore": False,
    "Nonetheless, data were cleaned.": False, "Unknown-source web pages": False,
    "NA-12 corpus": False, "MIT": False, "English": False,
}


@pytest.mark.parametrize("i", range(len(NULL_CASES)))
def test_is_null_gold(toy_scores, i):
    value = NULL_CASES[i]
    assert toy_scores["null"][i] is NULL_EXPECTED[value], repr(value)
