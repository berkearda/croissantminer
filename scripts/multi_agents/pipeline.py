"""Multi-agent specialist extraction pipeline (refactored from Paul's design).

Output schema (Phase 0 fix 8): uses 'extraction' key for compatibility with
croissantminer.evaluation.score_against_gold (was 'metadata' in Paul's original).

Output dir: data/extractions/agentic_specialist_<config>_v<N>/
where config ∈ {econ, mixed, premium} and v<N> is the prompt variant.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Paul's pdf import path: was `from pdf import` — our shim resolves it
from scripts._agentic_helpers import get_paper_text  # noqa: E402

# Local imports
sys.path.insert(0, str(Path(__file__).resolve().parent))
from agents import (  # noqa: E402
    ALL_FIELDS, BACKBONE_CONFIGS, build_specialists, simple_merge, null_dict,
)


DATA_DIR = ROOT / "data"
SPLIT_FILE = DATA_DIR / "agentic" / "dev_test_split.json"


def output_dir_for(config: str, prompt_variant: str) -> Path:
    suffix = "" if prompt_variant == "v1" else f"_{prompt_variant}"
    return DATA_DIR / "extractions" / f"agentic_specialist_{config}{suffix}"


class MultiAgentPipeline:
    def __init__(
        self,
        config: str = "mixed",
        prompt_variant: str = "v1",
        skip_existing: bool = True,
    ):
        self.config = config
        self.prompt_variant = prompt_variant
        self.skip_existing = skip_existing
        self.specialists = build_specialists(config, prompt_variant)
        self.output_dir = output_dir_for(config, prompt_variant)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ── Single paper ──────────────────────────────────────────────
    def run_individual_paper(self, dataset_id: str) -> Optional[dict]:
        output_path = self.output_dir / f"{dataset_id}.json"
        if self.skip_existing and output_path.exists():
            return None

        print(f"\n  -- {dataset_id} --")
        t0 = time.time()
        paper_text = get_paper_text(dataset_id)
        if not paper_text:
            print(f"  PDF not found for {dataset_id}. Saving null output.")
            self._save_null_output(dataset_id, output_path)
            return None

        # Sequential specialist runs (parallel TBD; cleanest for token-tracking)
        specialist_outputs: dict[str, dict] = {}
        specialist_usage: dict[str, dict] = {}
        for agent in self.specialists:
            fields, usage = agent.run(paper_text)
            specialist_outputs[agent.name] = fields
            specialist_usage[agent.name] = usage
            print(f"   [{agent.name}@{agent.backbone_key}] "
                  f"{usage['input_tokens']}in / {usage['output_tokens']}out tokens")

        # Verify+correct phase (variants v3/v4/v5)
        vc_usage_total = {"input_tokens": 0, "output_tokens": 0}
        for agent in self.specialists:
            new_ext, vc_usage = agent.verify_correct(
                paper_text, specialist_outputs[agent.name]
            )
            specialist_outputs[agent.name] = new_ext
            specialist_usage[agent.name]["input_tokens"] += vc_usage["input_tokens"]
            specialist_usage[agent.name]["output_tokens"] += vc_usage["output_tokens"]
            vc_usage_total["input_tokens"] += vc_usage["input_tokens"]
            vc_usage_total["output_tokens"] += vc_usage["output_tokens"]

        merged = simple_merge(specialist_outputs)
        final_fields = {field: merged.get(field, None) for field in ALL_FIELDS}

        total_in = sum(u["input_tokens"] for u in specialist_usage.values())
        total_out = sum(u["output_tokens"] for u in specialist_usage.values())

        meta = {
            "config": self.config,
            "prompt_variant": self.prompt_variant,
            "specialist_backbones": {a.name: a.backbone_key for a in self.specialists},
            "agent_tokens": {
                name: {"input_tokens": u["input_tokens"], "output_tokens": u["output_tokens"]}
                for name, u in specialist_usage.items()
            },
            "verify_correct_tokens": vc_usage_total,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "elapsed_seconds": round(time.time() - t0, 1),
        }

        output = {
            "dataset_id": dataset_id,
            "model": f"specialist_{self.config}",
            "extraction": final_fields,           # ← fix 8: was 'metadata'
            "usage": {"input_tokens": total_in, "output_tokens": total_out},
            "valid": True,
            "_meta": meta,
        }
        output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
        print(f"  Done {dataset_id} ({meta['elapsed_seconds']}s, "
              f"{total_in}in / {total_out}out tokens)")
        return output

    def _save_null_output(self, dataset_id: str, output_path: Path) -> None:
        output = {
            "dataset_id": dataset_id,
            "model": f"specialist_{self.config}",
            "extraction": null_dict(ALL_FIELDS),
            "usage": {"input_tokens": 0, "output_tokens": 0},
            "valid": False,
            "_meta": {
                "config": self.config,
                "prompt_variant": self.prompt_variant,
                "specialist_backbones": {a.name: a.backbone_key for a in self.specialists},
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": "PDF not found",
            },
        }
        output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))

    # ── Split runner ──────────────────────────────────────────────
    def run_split(self, split: str = "dev") -> dict[str, int]:
        split_data = json.loads(SPLIT_FILE.read_text())
        if split not in split_data:
            raise ValueError(f"Split '{split}' not in {SPLIT_FILE}. Available: {list(split_data)}")
        ids = split_data[split]
        print(f"Running specialist-{self.config}-{self.prompt_variant} for split={split} (n={len(ids)})")
        counts = {"processed": 0, "skipped": 0, "errors": 0}
        for i, dataset_id in enumerate(ids, 1):
            print(f"\n[{i}/{len(ids)}]", end="")
            try:
                result = self.run_individual_paper(dataset_id)
                if result is None:
                    counts["skipped"] += 1
                else:
                    counts["processed"] += 1
            except Exception as e:
                print(f" [ERROR] {dataset_id}: {e}")
                counts["errors"] += 1
        print(f"\nDone: {counts['processed']} ok, {counts['skipped']} skipped, "
              f"{counts['errors']} errors")
        return counts

    def run_all(self) -> dict[str, int]:
        """Run on dev + test (all 102 papers, with skip-existing)."""
        split_data = json.loads(SPLIT_FILE.read_text())
        ids = sorted(split_data["dev"] + split_data["test"])
        print(f"Running specialist-{self.config}-{self.prompt_variant} on all {len(ids)} papers")
        counts = {"processed": 0, "skipped": 0, "errors": 0}
        for i, dataset_id in enumerate(ids, 1):
            print(f"\n[{i}/{len(ids)}]", end="")
            try:
                result = self.run_individual_paper(dataset_id)
                if result is None:
                    counts["skipped"] += 1
                else:
                    counts["processed"] += 1
            except Exception as e:
                print(f" [ERROR] {dataset_id}: {e}")
                counts["errors"] += 1
        print(f"\nDone: {counts['processed']} ok, {counts['skipped']} skipped, "
              f"{counts['errors']} errors")
        return counts
