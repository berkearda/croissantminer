#!/usr/bin/env python3
"""
CroissantMiner — Open-Source Model Extraction via vLLM

Runs offline batch inference with guided JSON decoding on Euler HPC.
Supports Qwen3-32B, Gemma, Llama, and any HuggingFace model via vLLM.

Usage:
  python scripts/euler/extract_openmodels.py \
      --model Qwen/Qwen3-32B-FP8 \
      --model-name qwen3_32b \
      --batch-size 4

Output: data/extractions/{model_name}/{dataset_id}.json
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import fitz  # PyMuPDF

# Add project root to path
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from config import SYSTEM_PROMPT, METADATA_SCHEMA

# All 30 fields
ALL_FIELDS = list(METADATA_SCHEMA.keys())

# JSON schema for guided decoding
EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        field: {"type": ["string", "null"]}
        for field in ALL_FIELDS
    },
    "required": ALL_FIELDS,
}

# User prompt (same as single-pass config.py USER_PROMPT_TEMPLATE)
USER_PROMPT = """Extract metadata from the following academic paper by matching text to the field descriptions above. Your output must conform exactly to the following schema:

SCHEMA:
{schema}

PAPER TEXT:
{paper_text}

Return ONLY valid JSON matching the schema above. Do not include any markdown formatting or explanations."""


def smart_truncate(text, max_chars):
    """Keep 60% from start + 20% from end. Matches models/claude_model.py."""
    if len(text) <= max_chars:
        return text
    keep_start = int(max_chars * 0.6)
    keep_end = int(max_chars * 0.2)
    return text[:keep_start] + "\n\n[... MIDDLE CONTENT TRUNCATED ...]\n\n" + text[-keep_end:]


def extract_paper_text(pdf_path, max_chars=240000):
    """Extract and clean text from PDF. Matches Claude baseline strategy."""
    doc = fitz.open(str(pdf_path))
    text = "\n".join(page.get_text() for page in doc)
    doc.close()

    # Strip references
    for pattern in [r'\n\s*References\s*\n', r'\n\s*REFERENCES\s*\n', r'\n\s*Bibliography\s*\n']:
        match = re.search(pattern, text)
        if match and match.start() > len(text) * 0.5:
            text = text[:match.start()]
            break

    text = smart_truncate(text, max_chars)
    return text.strip()


def build_prompts(papers, tokenizer, is_qwen3=False):
    """Build formatted prompts for all papers."""
    schema_str = json.dumps({f: "string or null" for f in ALL_FIELDS}, indent=2)

    prompts = []
    for paper in papers:
        user_content = USER_PROMPT.format(
            schema=schema_str,
            paper_text=paper["text"]
        )
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        # Apply chat template
        kwargs = {"tokenize": False, "add_generation_prompt": True}
        if is_qwen3:
            kwargs["enable_thinking"] = False  # Disable CoT for JSON extraction

        formatted = tokenizer.apply_chat_template(messages, **kwargs)
        prompts.append(formatted)

    return prompts


def main():
    parser = argparse.ArgumentParser(description="CroissantMiner open-source extraction")
    parser.add_argument("--model", type=str, required=True,
                        help="HuggingFace model ID (e.g., Qwen/Qwen3-32B-FP8)")
    parser.add_argument("--model-name", type=str, required=True,
                        help="Short name for output dir (e.g., qwen3_32b)")
    parser.add_argument("--quantization", type=str, default=None,
                        help="Quantization: fp8, awq, gptq, or None for full precision")
    parser.add_argument("--max-model-len", type=int, default=32768)
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.90)
    parser.add_argument("--tensor-parallel-size", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=4,
                        help="Papers per GPU batch")
    parser.add_argument("--temperature", type=float, default=0.7,
                        help="Sampling temperature (Qwen3 needs >0 for non-thinking mode)")
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--dev-only", action="store_true", help="Only process 15 dev papers")
    parser.add_argument("--paper", type=str, help="Process single paper by ID")
    args = parser.parse_args()

    # ── Load paper list ──
    with open(ROOT / "data" / "agentic" / "dev_test_split.json") as f:
        split = json.load(f)

    if args.paper:
        paper_ids = [args.paper]
    elif args.dev_only:
        paper_ids = sorted(split["dev"])
    else:
        paper_ids = sorted(split["dev"] + split["test"])

    # ── Output dir ──
    output_dir = ROOT / "data" / "extractions" / args.model_name
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Skip already done ──
    todo = []
    for pid in paper_ids:
        if (output_dir / f"{pid}.json").exists():
            continue
        pdf_path = ROOT / "data" / "raw" / f"{pid}.pdf"
        if not pdf_path.exists():
            # Try arxiv ID patterns
            with open(ROOT / "data" / "paper_links.json") as f:
                links = json.load(f)
            url = links.get(pid, "")
            m = re.search(r'(\d{4}\.\d{4,5})', url)
            if m:
                for sfx in ["", "v1", "v2", "v3", "v4", "v5"]:
                    p = ROOT / "data" / "raw" / f"{m.group(1)}{sfx}.pdf"
                    if p.exists():
                        pdf_path = p
                        break
        if pdf_path.exists():
            todo.append((pid, pdf_path))
        else:
            print(f"SKIP: no PDF for {pid}")

    print(f"=" * 60)
    print(f"CroissantMiner Open-Source Extraction")
    print(f"=" * 60)
    print(f"Model: {args.model}")
    print(f"Papers: {len(todo)} to process ({len(paper_ids) - len(todo)} skipped)")
    print(f"Output: {output_dir}")
    print(f"Batch size: {args.batch_size}")
    print(f"Max model len: {args.max_model_len}")
    print(f"=" * 60)

    if not todo:
        print("Nothing to process.")
        return

    # ── Load model ──
    print(f"\nLoading {args.model}...")
    t0 = time.time()

    from vllm import LLM, SamplingParams
    from transformers import AutoTokenizer

    # Check for structured output params (API varies by vllm version)
    try:
        from vllm.sampling_params import StructuredOutputsParams
        has_structured = True
    except ImportError:
        has_structured = False
        print("WARNING: StructuredOutputsParams not available. Using prompt-only JSON enforcement.")

    llm = LLM(
        model=args.model,
        quantization=args.quantization,
        max_model_len=args.max_model_len,
        gpu_memory_utilization=args.gpu_memory_utilization,
        tensor_parallel_size=args.tensor_parallel_size,
        dtype="bfloat16",
        trust_remote_code=True,
        enforce_eager=False,
    )
    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)

    load_time = time.time() - t0
    print(f"Model loaded in {load_time:.0f}s")

    # ── Detect model family ──
    is_qwen3 = "qwen3" in args.model.lower() or "qwen/qwen3" in args.model.lower()
    if is_qwen3:
        print("Detected Qwen3 — disabling thinking mode for JSON extraction")

    # ── Sampling params ──
    sampling_kwargs = {
        "temperature": args.temperature,
        "top_p": 0.8,
        "top_k": 20,
        "max_tokens": args.max_tokens,
    }

    if has_structured:
        sampling_kwargs["structured_outputs"] = StructuredOutputsParams(json=EXTRACTION_SCHEMA)
        print("Using guided JSON decoding (xgrammar)")

    sampling_params = SamplingParams(**sampling_kwargs)

    # ── Process in batches ──
    total_ok = 0
    total_fail = 0
    total_tokens = 0

    for batch_start in range(0, len(todo), args.batch_size):
        batch = todo[batch_start:batch_start + args.batch_size]
        batch_num = batch_start // args.batch_size + 1
        total_batches = (len(todo) + args.batch_size - 1) // args.batch_size

        print(f"\nBatch {batch_num}/{total_batches} ({len(batch)} papers)")

        # Extract text
        papers = []
        for pid, pdf_path in batch:
            text = extract_paper_text(pdf_path)
            papers.append({"paper_id": pid, "text": text})

        # Build prompts
        prompts = build_prompts(papers, tokenizer, is_qwen3=is_qwen3)

        # Run inference
        t1 = time.time()
        outputs = llm.generate(prompts, sampling_params)
        inference_time = time.time() - t1

        # Parse and save results
        for paper, output in zip(papers, outputs):
            pid = paper["paper_id"]
            raw_text = output.outputs[0].text
            prompt_tokens = len(output.prompt_token_ids)
            output_tokens = len(output.outputs[0].token_ids)
            total_tokens += prompt_tokens + output_tokens

            try:
                # Parse JSON
                raw = raw_text.strip()
                if raw.startswith("```json"):
                    raw = raw[7:]
                if raw.startswith("```"):
                    raw = raw[3:]
                if raw.endswith("```"):
                    raw = raw[:-3]

                first = raw.find("{")
                last = raw.rfind("}")
                if first != -1 and last != -1:
                    raw = raw[first:last + 1]

                metadata = json.loads(raw)

                # Normalize null variants
                for field in ALL_FIELDS:
                    val = metadata.get(field)
                    if val is not None and isinstance(val, str):
                        if val.strip().lower() in ("", "null", "none", "n/a", "not mentioned", "unknown"):
                            metadata[field] = None
                    metadata.setdefault(field, None)

                result = {
                    "paper_id": pid,
                    "metadata": metadata,
                    "status": "ok",
                    "_meta": {
                        "model": args.model,
                        "model_name": args.model_name,
                        "prompt_tokens": prompt_tokens,
                        "output_tokens": output_tokens,
                        "inference_time": round(inference_time / len(batch), 2),
                    }
                }
                total_ok += 1
                non_null = sum(1 for v in metadata.values() if v is not None)
                print(f"  {pid}: {non_null}/30 fields, {prompt_tokens}+{output_tokens} tokens")

            except (json.JSONDecodeError, Exception) as e:
                result = {
                    "paper_id": pid,
                    "metadata": None,
                    "status": f"error: {str(e)[:100]}",
                    "raw_output": raw_text[:500],
                    "_meta": {
                        "model": args.model,
                        "model_name": args.model_name,
                        "prompt_tokens": prompt_tokens,
                        "output_tokens": output_tokens,
                    }
                }
                total_fail += 1
                print(f"  {pid}: FAILED ({str(e)[:50]})")

            # Save
            with open(output_dir / f"{pid}.json", "w") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)

            # Also save flat extraction for evaluation compatibility
            if result["status"] == "ok":
                with open(output_dir / f"{pid}_flat.json", "w") as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False)

    # ── Summary ──
    elapsed = time.time() - t0
    print(f"\n{'=' * 60}")
    print(f"COMPLETE")
    print(f"{'=' * 60}")
    print(f"Papers: {total_ok} OK, {total_fail} failed")
    print(f"Total tokens: {total_tokens:,}")
    print(f"Total time: {elapsed:.0f}s ({elapsed/60:.1f} min)")
    print(f"Avg time/paper: {elapsed/max(total_ok+total_fail, 1):.1f}s")
    print(f"Output: {output_dir}")

    # Save summary
    summary = {
        "model": args.model,
        "model_name": args.model_name,
        "papers_ok": total_ok,
        "papers_failed": total_fail,
        "total_tokens": total_tokens,
        "elapsed_seconds": round(elapsed, 1),
        "cost_usd": 0.0,  # self-hosted = free
    }
    with open(output_dir / "_summary.json", "w") as f:
        json.dump(summary, f, indent=2)


if __name__ == "__main__":
    main()
