import asyncio
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from agents import ALL_FIELDS, COORDINATOR, MODEL, SPECIALISTS, null_dict
from pdf import extract_text_from_pdf, clean_text

DATA_DIR = Path("data")
RAW_DIR = DATA_DIR / "raw"
SPLIT_FILE = DATA_DIR / "agentic" / "dev_test_split.json"
OUTPUT_DIR = DATA_DIR / "extractions" / "multi_agent_paul"
COST_LOG_PATH = OUTPUT_DIR / "_cost_log.json"


def _load_usage_log() -> dict:
    if COST_LOG_PATH.exists():
        return json.loads(COST_LOG_PATH.read_text())
    return {"papers": {}, "totals": {"input_tokens": 0, "output_tokens": 0}}


def _save_cost_log(log: dict) -> None:
    COST_LOG_PATH.write_text(json.dumps(log, indent=2))


def _build_meta(
        agent_usage: dict[str, dict],
        coordinator_usage: dict,
        coordinator_modifications: int,
) -> dict:
    """Build the _meta block attached to each output JSON."""
    agent_tokens = {
        name: {
            "input_tokens": usage["input_tokens"],
            "output_tokens": usage["output_tokens"],
        }
        for name, usage in agent_usage.items()
    }
    total_in = sum(u["input_tokens"] for u in agent_usage.values()) + coordinator_usage["input_tokens"]
    total_out = sum(u["output_tokens"] for u in agent_usage.values()) + coordinator_usage["output_tokens"]

    return {
        "model": MODEL,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "provider": "anthropic",
        "agent_tokens": agent_tokens,
        "coordinator_tokens": {
            "input_tokens": coordinator_usage["input_tokens"],
            "output_tokens": coordinator_usage["output_tokens"],
        },
        "coordinator_modifications": coordinator_modifications,
        "input_tokens": total_in,
        "output_tokens": total_out,
    }


async def _run_specialists_parallel(paper_text: str) -> tuple[dict[str, dict], dict[str, dict]]:
    """
    Run all five specialist agents in parallel using threads
    """
    loop = asyncio.get_event_loop()

    tasks = [
        loop.run_in_executor(None, agent.run, paper_text)
        for agent in SPECIALISTS
    ]
    results = await asyncio.gather(*tasks)

    specialist_outputs = {}
    specialist_usage = {}
    for agent, (fields, usage) in zip(SPECIALISTS, results):
        specialist_outputs[agent.name] = fields
        specialist_usage[agent.name] = usage

    return specialist_outputs, specialist_usage


class MultiAgentPipeline:
    """
    Runs the full multi-agent extraction pipeline for one or many papers.
    """

    def __init__(self, parallel: bool = True, skip_existing: bool = True):
        self.parallel = parallel
        self.skip_existing = skip_existing

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    def run_individual_paper(self, dataset_id: str) -> Optional[dict]:
        output_path = OUTPUT_DIR / f"{dataset_id}.json"

        if self.skip_existing and output_path.exists():
            print(f"  Skipping {dataset_id}: output already exists")
            return None

        pdf_path = RAW_DIR / f"{dataset_id}.pdf"
        if not pdf_path.exists():
            print(f"  PDF not found: {pdf_path}. Saving null output.")
            self._save_null_output(dataset_id, output_path)
            return None

        print(f"\n  -- {dataset_id} --")
        start_time = time.time()

        paper_text = extract_text_from_pdf(pdf_path)
        paper_text = clean_text(paper_text)

        if self.parallel:
            specialist_outputs, specialist_usage = asyncio.run(
                _run_specialists_parallel(paper_text)
            )
        else:
            specialist_outputs, specialist_usage = self._run_specialists_sequential(paper_text)

        merged, coord_usage, modifications = COORDINATOR.run(specialist_outputs)

        # Ensure all fields are present, and fill missing with None
        final_fields = {field: merged.get(field, None) for field in ALL_FIELDS}

        agents_meta = _build_meta(specialist_usage, coord_usage, modifications)

        output = {
            "paper_id": dataset_id,
            "metadata": final_fields,
            "status": "ok",
            "_meta": agents_meta,
        }
        output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))

        print(f"  Done {dataset_id} ({time.time() - start_time:.1f}s)")

        self._update_usage_log(dataset_id, agents_meta)

        return output

    def _run_specialists_sequential(
            self, paper_text: str
    ) -> tuple[dict[str, dict], dict[str, dict]]:
        specialist_outputs = {}
        specialist_usage = {}

        for agent in SPECIALISTS:
            fields, usage = agent.run(paper_text)
            specialist_outputs[agent.name] = fields
            specialist_usage[agent.name] = usage

        return specialist_outputs, specialist_usage

    def _save_null_output(self, dataset_id: str, output_path: Path) -> None:
        """Save a fully-null extraction when the PDF is missing."""
        meta = _build_meta(
            {a.name: {"input_tokens": 0, "output_tokens": 0} for a in SPECIALISTS},
            {"input_tokens": 0, "output_tokens": 0},
            0,
        )
        output = {
            "paper_id": dataset_id,
            "metadata": null_dict(ALL_FIELDS),
            "status": "ok",
            "_meta": meta,
        }
        output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))

    def run_all_split_papers(self, split: str = "test") -> dict[str, int]:
        """
        Run extraction for all papers in a dev/test split.

        Returns:
            Summary counts: {processed, skipped, errors}
        """
        split_data = json.loads(SPLIT_FILE.read_text())
        if split not in split_data:
            raise ValueError(f"Split '{split}' not found in {SPLIT_FILE}. Available: {list(split_data)}")

        ids = split_data[split]
        print(f"Running Multi-Agent Pipeline for split={split} (total={len(ids)})")

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

        print(
            f"Done processing {counts['processed']} papers ({counts['skipped']} skipped & {counts['errors']} errors)"
        )

        self._print_usage_summary()
        return counts

    def _update_usage_log(self, dataset_id: str, meta: dict) -> None:
        log = _load_usage_log()
        log["papers"][dataset_id] = {
            "timestamp": meta["timestamp"],
            "input_tokens": meta["input_tokens"],
            "output_tokens": meta["output_tokens"],
            "coordinator_modifications": meta["coordinator_modifications"],
        }
        log["totals"]["input_tokens"] += meta["input_tokens"]
        log["totals"]["output_tokens"] += meta["output_tokens"]
        _save_cost_log(log)

    def _print_usage_summary(self) -> None:
        log = _load_usage_log()
        t = log["totals"]

        print(
            f"\nCost summary — "
            f"input: {t['input_tokens']:,} tokens | "
            f"output: {t['output_tokens']:,} tokens"
        )

    def _strip_references(self, text: str) -> str:
        """Remove everything after 'References' heading."""
        # Common patterns for references section
        patterns = [
            r'\n\s*References\s*\n',
            r'\n\s*REFERENCES\s*\n',
            r'\n\s*Bibliography\s*\n',
        ]
        for pattern in patterns:
            m = re.search(pattern, text)

            if m:
                # Only cut if it's in the last 40% of the paper (avoid false matches)
                if m.start() > len(text) * 0.6:
                    return text[:m.start()].strip()
        return text.strip()
