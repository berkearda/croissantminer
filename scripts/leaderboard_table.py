"""Write the table in leaderboard/README.md from leaderboard/leaderboard.csv, the file the demo's leaderboard reads.

    python scripts/leaderboard_table.py           # rewrite the table
    python scripts/leaderboard_table.py --check   # exit 1 if the table in the README is out of date
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "leaderboard" / "leaderboard.csv"
README = ROOT / "leaderboard" / "README.md"
START, END = "<!-- table:start -->", "<!-- table:end -->"


def rows(path: Path = CSV) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        data = list(csv.DictReader(f))
    reference = [r for r in data if r["role"] == "reference"]
    ranked = sorted((r for r in data if r["role"] == "ranked"), key=lambda r: -float(r["composite"]))
    return reference + ranked


def table(path: Path = CSV) -> str:
    lines = ["| Rank | System | Design | Core | RAI | Composite [95% CI] | Paper | US$ per paper |",
             "|---|---|---|---|---|---|---|---|"]
    rank = 0
    for r in rows(path):
        name = r["system"] + ("\\*" if r["claude"] == "yes" else "")
        cost = r["cost_per_paper_usd"] if r["cost_per_paper_usd"] == "self-hosted" else f"{float(r['cost_per_paper_usd']):.2f}"
        cells = [name, r["design"], f"{float(r['core']):.3f}", f"{float(r['rai']):.3f}",
                 f"{float(r['composite']):.3f} [{float(r['ci_low']):.3f}, {float(r['ci_high']):.3f}]",
                 f"{float(r['paper_composite']):.3f}", cost]
        if r["role"] == "reference":
            lines.append("| | " + " | ".join(f"*{c} (reference)*" if i == 0 else f"*{c}*" for i, c in enumerate(cells)) + " |")
        else:
            rank += 1
            lines.append(f"| {rank} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def updated(text: str) -> str:
    head, rest = text.split(START, 1)
    _, tail = rest.split(END, 1)
    return f"{head}{START}\n{table()}\n{END}{tail}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="only check that the README table is up to date")
    args = ap.parse_args(argv)
    text = README.read_text(encoding="utf-8")
    new = updated(text)
    if args.check:
        if new != text:
            print("leaderboard/README.md is out of date: run python scripts/leaderboard_table.py")
            return 1
        return 0
    README.write_text(new, encoding="utf-8")
    print(f"wrote the table of {README.relative_to(ROOT)} ({len(rows())} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
