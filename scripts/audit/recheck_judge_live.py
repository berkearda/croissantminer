#!/usr/bin/env python3
"""Re-judge a small sample of saved v2min cells against the live GLM-5
endpoint and compare with data/judged/judge_scores_v2min_glm5.parquet.

Used 2026-07-26 to verify the DeepInfra endpoint's envelope drift (JSON now
arrives in reasoning_content with empty content) does not change verdicts:
6/6 scores matched the saved parquet at both 2000 and 4000 token caps.

Usage:
    python scripts/audit/recheck_judge_live.py [--n 6] [--system SYSTEM_ID]

Requires DEEPINFRA_API_KEY in the environment (source .env first).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "jr", ROOT / "scripts" / "judge_rerun_test88.py")
jr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jr)


def call_raw(field, ref, cand, max_toks):
    body = {
        "model": jr.MODEL,
        "messages": [
            {"role": "system", "content": jr.SYSTEM},
            {"role": "user", "content": jr.v2min_user(field, ref, cand)},
        ],
        "temperature": 0.0,
        "max_completion_tokens": max_toks,
        "response_format": {"type": "json_object"},
    }
    req = urllib.request.Request(
        jr.URL, data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {jr.API_KEY}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        resp = json.load(r)
    m = resp["choices"][0]["message"]
    content = m.get("content") or ""
    rc = m.get("reasoning_content") or ""
    src = "content" if content.strip() else (
        "reasoning_content" if rc.strip() else "EMPTY")
    msg = content if content.strip() else rc
    if "</think>" in msg:
        msg = msg.split("</think>", 1)[-1]
    matches = re.findall(r'\{[^{}]*"score"[^{}]*\}', msg, re.S)
    score = json.loads(matches[-1])["score"] if matches else None
    return score, src, resp.get("usage", {}).get("completion_tokens")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=6, help="cells per token cap")
    ap.add_argument("--system", default="agentic_react_sonnet_4_6_v3")
    args = ap.parse_args()

    j = pd.read_parquet(ROOT / "data/judged/judge_scores_v2min_glm5.parquet")
    sub = j[j.system_id == args.system]
    per = max(1, args.n // 3)
    cells = pd.concat([sub[sub.score == s].head(per) for s in (1, 2, 3)])

    for cap in (2000, 4000):
        print(f"--- max_completion_tokens = {cap} ---")
        agree = n = 0
        for _, c in cells.iterrows():
            s, src, toks = call_raw(
                c["field_id"], str(c["gold_value"])[:8000],
                str(c["candidate"])[:8000], cap)
            ok = s == c["score"]
            agree += ok
            n += 1
            print(f"{c['paper_id'][:24]:24s} {c['field_id'][:28]:28s} "
                  f"saved={c['score']} rerun={s} src={src} "
                  f"out_toks={toks} {'OK' if ok else 'DIFF'}")
        print(f"agreement: {agree}/{n}\n")


if __name__ == "__main__":
    main()
