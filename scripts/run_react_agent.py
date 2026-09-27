#!/usr/bin/env python3
"""CLI entry for the ReAct agent extraction pipeline.

Usage:
    python scripts/run_react_agent.py --split dev
    python scripts/run_react_agent.py --split test
    python scripts/run_react_agent.py --dataset AI4Math_MathVista
    python scripts/run_react_agent.py --split all --overwrite

Reads data/agentic/dev_test_split.json, runs the agent per paper, writes
results to data/extractions/react_agent/{ds_id}.json + _cost_log.json.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

import anthropic  # noqa: E402

from croissantminer.react_agent.runner import extract_paper, EXTRACTIONS_DIR  # noqa: E402

SPLIT_PATH = ROOT / "data" / "agentic" / "dev_test_split.json"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--split", choices=["dev", "test", "all"], help="Run the dev, test, or combined split.")
    g.add_argument("--dataset", help="Run a single dataset id.")
    p.add_argument("--max-turns", type=int, default=20)
    p.add_argument("--overwrite", action="store_true", help="Re-run papers whose extraction already exists.")
    p.add_argument("--save-trace", action="store_true", help="Save a reasoning trace for every paper (not just a sample).")
    p.add_argument("--trace-sample", type=int, default=5, help="When --save-trace is not set, still save N sampled traces (first N papers).")
    p.add_argument("--limit", type=int, help="Run only the first N papers (for testing).")
    p.add_argument("--backbone", default="sonnet-4-6",
                   choices=["sonnet-4-5", "sonnet-4-6", "gpt-5.4", "gpt-5.4-mini", "gemini-3.1-pro"],
                   help="Agent backbone (default: sonnet-4-6, non-seed Anthropic).")
    p.add_argument("--prompt-variant", default="v1",
                   choices=["v1", "v2", "v3", "v4", "v5"],
                   help="v1=baseline; v2=+anti-null prefix (Fix A); v3=+verify-correct (Fix C); v4=v2+v3 compound; v5=+multi-aspect.")
    args = p.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    if args.dataset:
        ids = [args.dataset]
    else:
        split = json.loads(SPLIT_PATH.read_text())
        ids = split["dev"] + split["test"] if args.split == "all" else split[args.split]

    if args.limit:
        ids = ids[: args.limit]

    client = anthropic.Anthropic()
    EXTRACTIONS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Running ReAct agent on {len(ids)} papers → {EXTRACTIONS_DIR}")

    t_start = time.time()
    ok = 0
    failed = 0
    for i, ds_id in enumerate(ids, 1):
        save_trace = args.save_trace or (i <= args.trace_sample)
        print(f"[{i}/{len(ids)}] {ds_id} ... ", end="", flush=True)
        t0 = time.time()
        try:
            res = extract_paper(
                ds_id,
                client=client,
                max_turns=args.max_turns,
                save_trace=save_trace,
                overwrite=args.overwrite,
                backbone_key=args.backbone,
                prompt_variant=args.prompt_variant,
            )
        except Exception as e:
            print(f"EXCEPTION {type(e).__name__}: {e}")
            failed += 1
            continue
        elapsed = time.time() - t0
        if res is None:
            print(f"FAIL ({elapsed:.1f}s) — see _failures.json")
            failed += 1
        else:
            meta = res.get("_meta", {})
            print(
                f"ok turns={meta.get('num_turns')} "
                f"tools={meta.get('num_tool_calls')} "
                f"cost=${meta.get('cost_usd')} "
                f"({elapsed:.1f}s)"
            )
            ok += 1

    print(f"\nTotals: ok={ok} failed={failed} total_elapsed={time.time()-t_start:.1f}s")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
