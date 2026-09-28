"""Shared fixtures.

The Table 2 scorer (scripts/figures/build_test88_headline_table.py) loads its
data when it is imported and resolves every path from its own location. To test
its rules without the real benchmark, `toy_scores` copies the scorer and the
evaluation package into a temporary folder, writes a small hand-made benchmark
next to them, and runs the unmodified scorer there in a fresh Python process.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]
SYSTEM = "claude_sonnet_4_6"
NULL = "[NULL - not found in paper]"

# (paper, field, gold value, gold method)
TOY_GOLD = [
    ("P1", "sc:license", "MIT", "unanimous_3of3"),
    ("P1", "sc:name", "Natural Questions", "unanimous_3of3"),
    ("P1", "rai:dataBiases", "Skewed toward English sources.", "majority_2of3"),
    ("P1", "rai:dataCollection", NULL, "unanimous_3of3"),
    ("P2", "sc:license", NULL, "unanimous_3of3"),
    ("P2", "sc:name", "National University of Singapore Dataset", "unanimous_3of3"),
    ("P2", "rai:dataBiases", "Crowdworkers were mostly US-based.", "unanimous_3of3"),
    ("P2", "rai:dataCollection", "Scraped from public forums.", "adjudicated"),
    ("P3", "sc:license", "Unknown", "unanimous_3of3"),
    ("P3", "sc:name", "Draft value", "not_settled"),
    ("P3", "rai:dataBiases", "No known biases are reported.", "unanimous_3of3"),
    ("P3", "rai:dataCollection", "Recorded in a lab study.", "unanimous_3of3"),
    ("P4", "sc:license", "CC BY 4.0", "unanimous_3of3"),
    ("D1", "sc:license", "MIT", "unanimous_3of3"),
]
SPLIT = {"dev": ["D1"], "test": ["P1", "P2", "P3", "P4"]}

# System outputs; P1 uses short keys, P2 the prefixed ones. P4 has no file.
TOY_OUTPUTS = {
    "P1": {"license": "MIT", "name": "", "rai:dataBiases": "Mostly English text."},
    "P2": {"sc:license": "Apache-2.0", "sc:name": "National University of Singapore Dataset",
           "rai:dataBiases": "Annotators were from the US.", "rai:dataCollection": None},
    "P3": {"license": None, "name": "Anything", "rai:dataBiases": "Biased toward images.",
           "rai:dataCollection": "Lab study."},
    "D1": {"license": "GPL-3.0"},
}

# Judge verdicts on the 3-point scale (1 = correct, 2 = partial, 3 = wrong).
TOY_JUDGE = [
    (SYSTEM, "P1", "rai:dataBiases", 1),
    (SYSTEM, "P2", "rai:dataBiases", 2),
    (SYSTEM, "P3", "rai:dataBiases", 3),
    ("gpt5_4_full", "P1", "rai:dataBiases", 3),  # another system: must be ignored
    # no verdict for P3 rai:dataCollection
]

NULL_CASES = [
    None, "", "   ", "null", "None", "N/A", "n/a.", "NA", "unknown", "Unknown.",
    "not disclosed", "Not specified", NULL, "[NULL]", "[N/A - not stated]",
    "Not found in paper", "The license is not mentioned in paper.",
    "Natural Questions", "National University of Singapore", "Nonetheless, data were cleaned.",
    "Unknown-source web pages", "NA-12 corpus", "MIT", "English",
]

DRIVER = r'''
import importlib.util, json, sys
root, system = sys.argv[1], sys.argv[2]
cases = json.load(open(f"{root}/null_cases.json"))
spec = importlib.util.spec_from_file_location("scorer", f"{root}/scripts/figures/build_test88_headline_table.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
df = m.per_cell_scores_test88(system)
out = {
    "cells": df.to_dict("records"),
    "ci": list(m.bootstrap_ci(df, n_boot=500)),
    "ci_again": list(m.bootstrap_ci(df, n_boot=500)),
    "null": [m.is_null_gold(c) for c in cases],
    "tier1": sorted(m.TIER1),
    "rai": sorted(m.LONG_TEXT_RAI_FIELDS),
}
print(json.dumps(out))
'''


def build_toy_repo(root: Path) -> None:
    shutil.copytree(REPO / "evaluation", root / "evaluation",
                    ignore=shutil.ignore_patterns("__pycache__"))
    (root / "scripts" / "figures").mkdir(parents=True)
    shutil.copy(REPO / "scripts/figures/build_test88_headline_table.py", root / "scripts/figures/")

    (root / "data/annotations").mkdir(parents=True)
    pd.DataFrame(TOY_GOLD, columns=["paper_id", "field_id", "gold_value", "gold_method"]) \
        .to_parquet(root / "data/annotations/gold.parquet")
    (root / "data/agentic").mkdir(parents=True)
    (root / "data/agentic/dev_test_split.json").write_text(json.dumps(SPLIT))
    (root / "data/judged").mkdir(parents=True)
    pd.DataFrame(TOY_JUDGE, columns=["system_id", "paper_id", "field_id", "v2min_score"]) \
        .to_parquet(root / "data/judged/judge_scores_v2min_glm5.parquet")
    out_dir = root / "data/extractions" / SYSTEM
    out_dir.mkdir(parents=True)
    for paper, fields in TOY_OUTPUTS.items():
        (out_dir / f"{paper}.json").write_text(json.dumps({"extraction": fields}))
    (root / "null_cases.json").write_text(json.dumps(NULL_CASES))


@pytest.fixture(scope="session")
def toy_scores(tmp_path_factory):
    root = tmp_path_factory.mktemp("toy_repo")
    build_toy_repo(root)
    proc = subprocess.run([sys.executable, "-c", DRIVER, str(root), SYSTEM],
                          capture_output=True, text=True, cwd=root, timeout=300)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout.strip().splitlines()[-1])
    out["by_cell"] = {(c["paper_id"], c["field_id"]): c["score"] for c in out["cells"]}
    return out
