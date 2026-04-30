#!/usr/bin/env python3
"""T-067 audit-set sampler: produce a 200-cell judge-vs-human audit set.

Stratified sampling: 20 prose RAI fields x 10 cells per field = 200 cells.
Within each field the 10 cells are spread across the available
extraction strategies so the judges (and humans) see the full quality
range that production will produce, not just outputs from one strong
system.

Output: data/annotations/audit_set_200.parquet (canonical, used by the
audit reporter) plus three rater-facing CSVs ready to drop into Google
Sheets:
  data/annotations/audit_sheet_R1.csv
  data/annotations/audit_sheet_R3.csv
  data/annotations/audit_sheet_R2.csv

Each sheet contains the same 200 rows in the same order, with the
candidate values shown but the rater's column blank to fill in.
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from evaluation.field_metrics import LONG_TEXT_RAI_FIELDS  # noqa: E402

GOLD_PARQUET = ROOT / "data" / "annotations" / "gold.parquet"
EXTRACTION_BASE = ROOT / "data" / "extractions"
OUT_PARQUET = ROOT / "data" / "annotations" / "audit_set_200.parquet"
SHEETS_DIR = ROOT / "data" / "annotations"

# Strategies that are on disk and have a full or near-full set of
# extractions. Open-weight Llama 4 Scout agentic + ReAct + specialist
# pipelines are excluded because their JSONs are not yet here; the
# audit doesn't gain quality information from systems that aren't
# ready to be scored at production time.
ELIGIBLE_STRATEGIES = [
    "claude_sonnet_4_5", "claude_sonnet_4_6", "claude_opus_4_7",
    "gpt5.4_full", "gpt5.4_mini",
    "gemini_3.1_pro", "gemini_2.5_flash",
    "deepseek_v3_2", "glm_5_1", "llama4_scout",
    "mistral_small_4", "qwen3_6_35b_a3b",
    "agentic_v2_sonnet_4_5", "agentic_v2_gpt5_4_full",
    "agentic_v2_gemini_3_1_pro",
    "agentic_lev_sonnet_4_5", "agentic_lev_gpt5_4_full",
    "agentic_lev_gemini_3_1_pro",
]

CELLS_PER_FIELD = 10
SEED = 20260427  # frozen audit-sample seed; lock it in decisions.md

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                   datefmt="%H:%M:%S")
log = logging.getLogger("sample_audit")


def load_strategy(strategy: str) -> dict[str, dict]:
    """Return {paper_id: extraction_payload} for a strategy."""
    out: dict[str, dict] = {}
    sdir = EXTRACTION_BASE / strategy
    if not sdir.exists():
        return out
    for path in sdir.glob("*.json"):
        if path.name.startswith("_"):
            continue
        try:
            with open(path) as f:
                out[path.stem] = json.load(f)
        except json.JSONDecodeError:
            log.warning("  skip malformed json: %s", path)
    return out


def get_pred_value(payload: dict, field_id: str) -> str | None:
    p = payload.get("extraction", payload)
    if field_id in p and p[field_id] is not None:
        return p[field_id]
    short = field_id.split(":")[-1] if ":" in field_id else field_id
    return p.get(short)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--n-cells", type=int, default=200)
    p.add_argument("--cells-per-field", type=int, default=CELLS_PER_FIELD)
    args = p.parse_args()

    rng = random.Random(SEED)

    log.info("loading gold.parquet...")
    gold = pd.read_parquet(GOLD_PARQUET)
    gold = gold[gold["gold_value"].notna()].copy()
    log.info("  %d cells with non-null gold (across %d papers, %d fields)",
            len(gold), gold["paper_id"].nunique(), gold["field_id"].nunique())

    # Restrict to the 20 prose RAI fields the LLM judge will score.
    gold_prose = gold[gold["field_id"].isin(LONG_TEXT_RAI_FIELDS)].copy()
    log.info("  %d settled prose-field cells", len(gold_prose))

    log.info("loading extractions for %d strategies...", len(ELIGIBLE_STRATEGIES))
    strat_extractions = {s: load_strategy(s) for s in ELIGIBLE_STRATEGIES}
    for s in ELIGIBLE_STRATEGIES:
        log.info("  %-30s  %4d papers", s, len(strat_extractions[s]))

    # Build the candidate pool: every (paper, field, strategy) triple
    # for which (a) gold exists, (b) the strategy has an extraction,
    # (c) the strategy's predicted value is non-null.
    #
    # Degenerate-cell filter (added 2026-04-27 evening per N9 audit):
    # if BOTH gold and candidate are placeholder strings like
    # "[NULL - not found in paper]", the cell contributes zero
    # variance to the judge-vs-human agreement signal (every rater
    # and every judge will score it 3) and wastes rater time. We
    # exclude these from the pool before sampling.
    # Match both "[NULL - not found in paper]" and bare "[NULL]" /
    # "null" / "n/a" / "unknown" / "not found" / etc.
    placeholder_patterns = [
        re.compile(r"^\s*\[?\s*null\s*\]?\s*$", re.IGNORECASE),
        re.compile(r"\bnot\s+found\b", re.IGNORECASE),
        re.compile(r"^\s*n/?a\s*$", re.IGNORECASE),
        re.compile(r"^\s*unknown\s*$", re.IGNORECASE),
        re.compile(r"^\s*none\s*$", re.IGNORECASE),
    ]

    def is_placeholder(s: str) -> bool:
        s = s.strip()
        return any(p.search(s) for p in placeholder_patterns)

    candidates: list[dict] = []
    n_dropped_degenerate = 0
    for _, row in gold_prose.iterrows():
        paper, field, gv = row["paper_id"], row["field_id"], row["gold_value"]
        for strat in ELIGIBLE_STRATEGIES:
            payload = strat_extractions[strat].get(paper)
            if payload is None:
                continue
            pred = get_pred_value(payload, field)
            if pred is None:
                continue
            pred_str = str(pred).strip()
            if not pred_str:
                continue
            gv_str = str(gv)
            if is_placeholder(gv_str) and is_placeholder(pred_str):
                n_dropped_degenerate += 1
                continue
            candidates.append({
                "paper_id": paper,
                "field_id": field,
                "system_id": strat,
                "gold_value": gv_str,
                "candidate_value": pred_str,
            })

    log.info("candidate pool: %d (paper, field, system) triples "
            "(%d degenerate both-placeholder cells filtered)",
            len(candidates), n_dropped_degenerate)

    # Stratified sample: per field, sample cells_per_field triples,
    # while spreading systems as evenly as we can.
    per_field: dict[str, list[dict]] = {f: [] for f in LONG_TEXT_RAI_FIELDS}
    for c in candidates:
        per_field[c["field_id"]].append(c)

    # System round-robin within each field, shuffled to avoid bias.
    sampled: list[dict] = []
    for field in LONG_TEXT_RAI_FIELDS:
        pool = per_field[field]
        if len(pool) < args.cells_per_field:
            log.warning("  %s: only %d candidates, taking all", field, len(pool))
            sampled.extend(pool)
            continue

        # Group by system so we can balance.
        by_system: dict[str, list[dict]] = {}
        for c in pool:
            by_system.setdefault(c["system_id"], []).append(c)

        systems = list(by_system.keys())
        rng.shuffle(systems)
        chosen: list[dict] = []
        # Round-robin: take one from each system in turn until we have enough.
        while len(chosen) < args.cells_per_field:
            progressed = False
            for s in systems:
                if not by_system[s]:
                    continue
                # pick a random cell from this system's queue
                idx = rng.randrange(len(by_system[s]))
                chosen.append(by_system[s].pop(idx))
                progressed = True
                if len(chosen) >= args.cells_per_field:
                    break
            if not progressed:
                break  # all queues drained
        sampled.extend(chosen)

    log.info("sampled %d cells (target %d)", len(sampled), args.n_cells)

    # Final shuffle so raters don't see all cells of one field consecutively
    rng.shuffle(sampled)

    audit = pd.DataFrame(sampled)
    audit.insert(0, "row_id", range(1, len(audit) + 1))
    audit.to_parquet(OUT_PARQUET, index=False)
    log.info("wrote %s (%d rows)", OUT_PARQUET, len(audit))

    # Field and system distribution sanity check
    log.info("field distribution:")
    for f, n in audit["field_id"].value_counts().sort_index().items():
        log.info("  %-40s  %d", f, n)
    log.info("system distribution:")
    for s, n in audit["system_id"].value_counts().items():
        log.info("  %-30s  %3d", s, n)

    # Three identical rater sheets. Each has a "rating" column for the
    # rater to fill (1, 2, or 3) and a "notes" column for free text.
    for rater in ("R1", "R2", "R3"):
        sheet = audit.copy()
        sheet["rating"] = ""
        sheet["notes"] = ""
        sheet_path = SHEETS_DIR / f"audit_sheet_{rater}.csv"
        sheet.to_csv(sheet_path, index=False)
        log.info("wrote %s", sheet_path)


if __name__ == "__main__":
    main()
