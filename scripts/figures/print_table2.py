#!/usr/bin/env python3
"""Print Table 2 of the paper: Core, RAI and Composite scores with 95% CIs on the 88 test papers
for the 24 ranked systems, grouped by architecture as in the paper, plus the unranked
Claude Sonnet 4.5 reference row.

Uses the Table 2 scorer (scripts/figures/build_test88_headline_table.py) through
scripts/camera_ready/build_camera_ready_tables.py, both unchanged. No API calls.

    python scripts/figures/print_table2.py
"""
import importlib.util
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", category=RuntimeWarning)  # empty-slice means in the bootstrap

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("tables", ROOT / "scripts/camera_ready/build_camera_ready_tables.py")
tables = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tables)

ARCHITECTURES = ["Single-pass", "ReAct", "Parallel Specialists", "Triage + Critique", "Locator-Extractor"]


def architecture(label):
    for a in ARCHITECTURES[1:]:
        if label.startswith(a):
            return a
    return "Single-pass"


def row(label, core, rai, comp, lo, hi):
    return f"{label:52s} {core:6.3f} {rai:6.3f}  {comp:.3f} [{lo:.3f}, {hi:.3f}]"


def main():
    t2 = tables.table2_numbers()
    t2["architecture"] = t2["label"].map(architecture)
    print(f"{'System':52s} {'Core':>6s} {'RAI':>6s}  Composite [95% CI]")
    for a in ARCHITECTURES:
        print(f"-- {a}")
        for r in t2[t2.architecture == a].sort_values("composite", ascending=False).itertuples():
            print(row(r.label, r.core, r.rai, r.composite, r.ci_lo, r.ci_hi))

    cells = tables.cells("claude_sonnet_4_5")
    comp, lo, hi = tables.h.bootstrap_ci(cells)
    per_field = cells.groupby("field_id")["score"].mean()
    core = per_field[per_field.index.isin(tables.h.TIER1)].mean()
    rai = per_field[per_field.index.isin(tables.h.LONG_TEXT_RAI_FIELDS)].mean()
    print("-- Reference (seeded the gold pre-fills, not ranked)")
    print(row("Claude Sonnet 4.5", core, rai, comp, lo, hi))


if __name__ == "__main__":
    main()
