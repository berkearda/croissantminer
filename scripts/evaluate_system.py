"""Score your own extraction system on the CroissantMiner benchmark, with the paper's scorer and judge.

    python scripts/evaluate_system.py OUTPUTS --name my-system [--split test|dev] [--dry-run]
    make evaluate OUTPUTS=path/to/outputs NAME=my-system

OUTPUTS holds one JSON file per benchmark paper, named <paper_id>.json (the ids are the PDF names in data/raw/;
`--list-papers` prints them). A file holds the 30 fields at the top level, under "extraction" (the format of
data/extractions/) or under "fields" (the file `croissantminer extract --fields` writes).

The 10 core fields are scored by rules. Each filled Responsible AI answer is scored by the paper's GLM-5 judge
(scripts/judge_rerun_test88.py, needs DEEPINFRA_API_KEY; about $0.0006 per answer, under $1 per system). Verdicts are
cached, so a re-run judges only answers that changed. The paper's scoring files are used unchanged: the system is
added to them only while this script runs. Results go to leaderboard/<name>/ (see leaderboard/README.md).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PRICE_IN, PRICE_OUT = 0.40, 1.30          # US$ per million tokens, as in scripts/judge_rerun_test88.py
TOKENS_IN, TOKENS_OUT = 532, 269          # mean tokens per answer in the judge run of 26 September 2026
VERDICT_COLUMNS = ["paper_id", "field_id", "system_id", "gold_value", "candidate", "score", "reason",
                   "input_tokens", "output_tokens"]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fields(payload) -> dict:
    if isinstance(payload, dict):
        for key in ("extraction", "fields"):
            if isinstance(payload.get(key), dict):
                return payload[key]
        return payload
    return {}


def copy_outputs(src: Path, dst: Path, papers: frozenset, canonical: set) -> tuple[list[str], list[str]]:
    """Copy the outputs of the split's papers into the format the scorer reads ({"extraction": {...}})."""
    dst.mkdir(parents=True, exist_ok=True)
    found, bad = [], []
    for path in sorted(src.glob("*.json")):
        if path.stem not in papers:
            continue
        try:
            fields = _fields(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            bad.append(path.name)
            continue
        if not any(k in canonical or k.split(":")[-1] in canonical for k in fields):
            bad.append(path.name)
            continue
        (dst / path.name).write_text(json.dumps({"extraction": fields}, ensure_ascii=False, indent=1))
        found.append(path.stem)
    return found, bad


def answers_to_judge(scorer, sid: str, outdir: Path) -> list[dict]:
    """Filled Responsible AI answers whose gold value is not empty: the cells the judge scores."""
    cells = []
    for _, g in scorer.GOLD_TEST.iterrows():
        fid = g["field_id"]
        if fid not in scorer.LONG_TEXT_RAI_FIELDS or scorer.is_null_gold(g["gold_value"]):
            continue
        path = outdir / f"{g['paper_id']}.json"
        if not path.exists():
            continue
        ext = json.loads(path.read_text())["extraction"]
        cand = ext.get(fid, ext.get(fid.split(":")[-1]))
        if cand is None or not str(cand).strip():
            continue
        cells.append({"paper_id": g["paper_id"], "field_id": fid, "system_id": sid,
                      "gold_value": str(g["gold_value"]), "candidate": str(cand)})
    return cells


def judge_answers(todo: list[dict], cache: Path, workers: int) -> pd.DataFrame:
    try:
        from dotenv import find_dotenv, load_dotenv
        load_dotenv(find_dotenv(usecwd=True)) or load_dotenv(ROOT / ".env")
    except ImportError:
        pass
    if not os.environ.get("DEEPINFRA_API_KEY"):
        sys.exit("error: judging needs DEEPINFRA_API_KEY (the paper's GLM-5 judge runs on DeepInfra)")
    judge = _load("judge_rerun_test88", "scripts/judge_rerun_test88.py")
    rows = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(judge.process_cell_v2min, cell) for cell in todo]
        for i, fut in enumerate(as_completed(futures), 1):
            rows.append(fut.result())
            if i % 100 == 0 or i == len(todo):
                print(f"  judged {i} of {len(todo)}", flush=True)
                _save(cache, pd.DataFrame(rows))
    return pd.DataFrame(rows)


def _save(cache: Path, new: pd.DataFrame) -> None:
    old = pd.read_parquet(cache) if cache.exists() else pd.DataFrame(columns=VERDICT_COLUMNS)
    both = pd.concat([old, new[[c for c in VERDICT_COLUMNS if c in new.columns]]], ignore_index=True)
    both = both[both.score.notna()].drop_duplicates(subset=["paper_id", "field_id", "candidate"], keep="last")
    both.to_parquet(cache, index=False)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("outputs", nargs="?", type=Path, help="folder with one <paper_id>.json per paper")
    ap.add_argument("--name", help="short name of your system, for example qwen3-8b-single-pass")
    ap.add_argument("--split", choices=["test", "dev"], default="test",
                    help="test (88 papers, the paper's results) or dev (14 papers, for tuning)")
    ap.add_argument("--out", type=Path, help="result folder (default: leaderboard/<name>)")
    ap.add_argument("--dry-run", action="store_true", help="count the answers to judge and the cost, judge nothing")
    ap.add_argument("--workers", type=int, default=8, help="parallel judge calls")
    ap.add_argument("--list-papers", action="store_true", help="print the paper ids of the split and exit")
    args = ap.parse_args(argv)

    split = json.loads((ROOT / "data/agentic/dev_test_split.json").read_text())
    if args.list_papers:
        print("\n".join(sorted(split[args.split])))
        return 0
    if not args.outputs or not args.name:
        ap.error("give the outputs folder and --name")
    name = "".join(c if c.isalnum() or c in "-_." else "-" for c in args.name).strip("-")
    out = args.out or ROOT / "leaderboard" / name
    sid = f"leaderboard_{name}"

    scorer = _load("scorer", "scripts/figures/build_test88_headline_table.py")   # the paper's scorer, unchanged
    papers = frozenset(split[args.split])
    if args.split == "dev":                                   # the scorer reads these globals when it scores
        scorer.test = papers
        scorer.GOLD_TEST = scorer.GOLD[scorer.GOLD["paper_id"].isin(papers)]
    canonical = {f.split(":")[-1] for f in scorer.GOLD["field_id"].unique()}
    found, bad = copy_outputs(args.outputs, out / "outputs", papers, canonical)
    print(f"Scoring {name} on the {len(papers)} {args.split} papers with the paper's scorer")
    print(f"  outputs: {len(found)} of {len(papers)} papers" + (f"; unreadable or without fields: {', '.join(bad)}" if bad else ""))
    if not found:
        return 1
    scorer.STRATEGY_DIRS[sid] = out / "outputs"

    cache = out / "judge_verdicts.parquet"
    cells = answers_to_judge(scorer, sid, out / "outputs")
    cached = pd.read_parquet(cache) if cache.exists() else pd.DataFrame(columns=VERDICT_COLUMNS)
    done = set(zip(cached.paper_id, cached.field_id, cached.candidate))
    todo = [c for c in cells if (c["paper_id"], c["field_id"], c["candidate"]) not in done]
    cost = len(todo) * (TOKENS_IN * PRICE_IN + TOKENS_OUT * PRICE_OUT) / 1e6
    print(f"  judge:   {len(cells)} Responsible AI answers, {len(cells) - len(todo)} with a cached verdict, "
          f"{len(todo)} to judge (about ${cost:.2f})")
    if args.dry_run:
        return 0
    if todo:
        judge_answers(todo, cache, args.workers)
    verdicts = pd.read_parquet(cache) if cache.exists() else pd.DataFrame(columns=VERDICT_COLUMNS)
    keys = {(c["paper_id"], c["field_id"], c["candidate"]) for c in cells}
    verdicts = verdicts[[k in keys for k in zip(verdicts.paper_id, verdicts.field_id, verdicts.candidate)]]
    missing = len(cells) - len(verdicts)
    verdicts = verdicts.assign(system_id=sid)
    scorer.judges = pd.concat([scorer.judges, verdicts[["paper_id", "field_id", "system_id", "score"]]], ignore_index=True)

    scores = scorer.per_cell_scores_test88(sid)
    composite, lo, hi = scorer.bootstrap_ci(scores)
    per_field = scores.groupby("field_id")["score"].mean()
    core = per_field[per_field.index.isin(scorer.TIER1)].mean()
    rai = per_field[per_field.index.isin(scorer.LONG_TEXT_RAI_FIELDS)].mean()
    print(f"\n{name}   Core {core:.3f}   RAI {rai:.3f}   Composite {composite:.3f} [{lo:.3f}, {hi:.3f}]"
          f"   ({len(scores)} scored cells, {scores['paper_id'].nunique()} paper"
          f"{'' if scores['paper_id'].nunique() == 1 else 's'})")
    result = {"name": name, "split": args.split, "papers": len(found), "scored_cells": int(len(scores)),
              "core": float(core), "rai": float(rai), "composite": float(composite),
              "ci95": [float(lo), float(hi)], "unjudged_answers": int(missing),
              "judge": "GLM-5, v2-min prompt (scripts/judge_rerun_test88.py)", "scored_on": date.today().isoformat()}
    complete = len(found) == len(papers) and not missing
    if args.split == "test" and complete:
        table2 = pd.read_csv(ROOT / "tests/expected/table2_camera_ready.csv")
        rank = 1 + int((table2["composite"] > composite).sum())
        result["rank_in_table2"] = rank
        print(f"Rank {rank} of {len(table2) + 1} next to the {len(table2)} ranked systems of the paper's Table 2")
    if missing:
        print(f"warning: {missing} answers have no verdict (the judge failed); they are left out of the score. "
              "Run again to retry them; a leaderboard entry needs all answers judged.")
    if len(found) < len(papers):
        print(f"warning: outputs for {len(papers) - len(found)} papers are missing; a leaderboard entry needs all of them.")
    (out / "scores.json").write_text(json.dumps(result, indent=2) + "\n")
    per_field.rename("score").to_csv(out / "per_field.csv")
    shown = out.relative_to(ROOT) if str(out.resolve()).startswith(str(ROOT)) else out
    print(f"Wrote {shown}/scores.json and per_field.csv")
    return 0 if complete else 1


if __name__ == "__main__":
    sys.exit(main())
