"""Run Paul's Multi-Agent Specialist pipeline.

Usage:
    python scripts/multi_agents/run.py --config mixed --prompt-variant v1 --paper CIFAR_30field
    python scripts/multi_agents/run.py --config mixed --prompt-variant v1 --dev-only
    python scripts/multi_agents/run.py --config mixed --prompt-variant v4

Configs (per-specialist backbone routing):
  econ    = all GPT-5.4-mini (cheap)
  mixed   = mini for {core, processing}, Sonnet 4.6 for {collection, annotation, impact}
  premium = all Sonnet 4.6

Prompt variants:
  v1 = Paul's prompts unchanged (baseline)
  v2 = Paul's + anti-null-bias prefix (Fix A)
  v3 = Paul's + verify+correct phase post-extraction (Fix C)
  v4 = v2 + v3 compound
  v5 = v4 + multi-aspect emphasis
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Project root + this dir on path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from pipeline import MultiAgentPipeline  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", default="mixed",
                   choices=["econ", "mixed", "premium", "gpt5_4_full", "gemini_3_1_pro"],
                   help="per-specialist backbone routing")
    p.add_argument("--prompt-variant", default="v1",
                   choices=["v1", "v2", "v3", "v4", "v5"],
                   help="v1=Paul's prompts; v2=+Fix A; v3=+Fix C; v4=A+C; v5=A+C+D")
    p.add_argument("--dev-only", action="store_true", help="Run on dev 14 only")
    p.add_argument("--test-only", action="store_true", help="Run on test 88 only")
    p.add_argument("--paper", type=str, help="Run a single paper by dataset_id")
    p.add_argument("--overwrite", action="store_true",
                   help="Re-extract papers that already have output JSON")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    pipeline = MultiAgentPipeline(
        config=args.config,
        prompt_variant=args.prompt_variant,
        skip_existing=not args.overwrite,
    )

    if args.paper:
        result = pipeline.run_individual_paper(args.paper)
        if result is None:
            print(f"  Skipped {args.paper} (already exists or PDF missing)")
            sys.exit(0)
        ext = result.get("extraction", {})
        non_null = sum(v is not None and str(v).strip() != "" for v in ext.values())
        print(f"\nExtracted {non_null}/{len(ext)} non-null fields.")
        return

    if args.dev_only:
        counts = pipeline.run_split("dev")
    elif args.test_only:
        counts = pipeline.run_split("test")
    else:
        counts = pipeline.run_all()
    if counts["errors"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
