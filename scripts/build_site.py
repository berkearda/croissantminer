"""Write the data of the leaderboard website (site/) from leaderboard/leaderboard.csv.

    python scripts/build_site.py      # writes site/data/leaderboard.json
    python -m http.server -d site     # preview at http://localhost:8000

The ranking is the one in leaderboard/README.md (scripts/leaderboard_table.py), so the site, the README table
and the demo's leaderboard tab all read the same file.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from leaderboard_table import CSV, rows  # noqa: E402

OUT = ROOT / "site" / "data" / "leaderboard.json"

# model -> developer, shown next to the model name
PROVIDERS = [("Claude", "Anthropic"), ("GPT", "OpenAI"), ("Gemini", "Google"), ("Qwen", "Qwen"),
             ("GLM", "Z.ai"), ("DeepSeek", "DeepSeek"), ("Mistral", "Mistral AI"), ("Llama", "Meta")]


def provider(model: str) -> str:
    found = [name for prefix, name in PROVIDERS if prefix in model]
    return " + ".join(dict.fromkeys(found)) or "—"


def number(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


def main() -> int:
    systems, rank = [], 0
    for r in rows():
        ranked = r["role"] == "ranked"
        if ranked:
            rank += 1
        systems.append({
            "rank": rank if ranked else None,
            "system": r["system"],
            "design": r["design"],
            "model": r["model"],
            "provider": provider(r["model"]),
            "open_weights": r["open_weights"] == "yes",
            "claude": r["claude"] == "yes",
            "reference": not ranked,
            "core": float(r["core"]),
            "rai": float(r["rai"]),
            "composite": float(r["composite"]),
            "ci": [float(r["ci_low"]), float(r["ci_high"])],
            "paper_composite": number(r["paper_composite"]),
            "cost": number(r["cost_per_paper_usd"]),
            "judge": r["judge"],
            "judged_on": r["judged_on"],
            "source": r["source"],
            "link": r["link"],
        })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"built": date.today().isoformat(), "systems": systems}, indent=1) + "\n",
                   encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(systems)} systems from {CSV.relative_to(ROOT)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
