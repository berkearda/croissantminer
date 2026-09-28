#!/usr/bin/env python3
"""
CroissantMiner — Open-Source Model Extraction via vLLM (Euler HPC).

Runs offline batch inference with guided JSON decoding. Supports Qwen,
Gemma, Llama families via vLLM 0.11+.

Standardization (matches extract_all_models_batch.py):
- Prompt: imports SYSTEM_PROMPT + USER_PROMPT_TEMPLATE from config (single source of truth).
- Parser: PyPDF2 3.0.1 via croissantminer.pdf canonical path.
- Paper set: 102-paper dev+test split (SuperGPQA excluded per T-017).
- Output schema: {dataset_id, model, extraction, usage, valid, _meta}.
- _meta provenance block: parser, prompt_sha256_prefix, git_commit, paper_set, ...

Usage:
  python scripts/euler/extract_openmodels.py \\
      --model Qwen/Qwen3.5-27B \\
      --model-name qwen3_5_27b \\
      --max-model-len 131072 \\
      --tensor-parallel-size 2

Output: data/extractions/{model_name}/{dataset_id}.json
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from config import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE, METADATA_SCHEMA
from croissantminer.pdf.reader import extract_text_from_pdf as _canonical_extract_text
from croissantminer.pdf.processor import clean_text as _canonical_clean_text
from validation.validate_extraction import CANONICAL_FIELDS, validate_extraction

ALL_FIELDS = list(METADATA_SCHEMA.keys())
_PROMPT_HASH = hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()[:16]
try:
    _GIT_COMMIT = subprocess.check_output(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=str(ROOT),
        stderr=subprocess.DEVNULL,
    ).decode().strip()
except Exception:
    _GIT_COMMIT = "unknown"

# Guided JSON schema for vLLM structured outputs.
EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {f: {"type": ["string", "null"]} for f in ALL_FIELDS},
    "required": ALL_FIELDS,
}

PREFIX_MAP = {
    "sc:name": "name", "sc:description": "description", "sc:url": "url",
    "sc:license": "license", "sc:creator": "creator", "sc:publisher": "publisher",
    "sc:datePublished": "datePublished", "sc:inLanguage": "inLanguage",
    "cr:citeAs": "citeAs", "cr:isLiveDataset": "isLiveDataset",
    "sc:citeAs": "citeAs", "sc:isLiveDataset": "isLiveDataset",
    "cr:name": "name", "cr:description": "description",
}


def _sanitize_utf8(text: str) -> str:
    return text.encode("utf-8", errors="replace").decode("utf-8")


def extract_paper_text(ds_id: str):
    raw_dir = ROOT / "data" / "raw"
    candidates = [
        raw_dir / f"{ds_id}.pdf",
        raw_dir / f"{ds_id.replace('_', '/')}.pdf",
    ]
    paper_links_path = ROOT / "data" / "paper_links.json"
    if paper_links_path.exists():
        with open(paper_links_path) as f:
            links = json.load(f)
        m = re.search(r"(\d{4}\.\d{4,5})", links.get(ds_id, ""))
        if m:
            arxiv_id = m.group(1)
            for sfx in ["", "v1", "v2", "v3", "v4", "v5"]:
                candidates.append(raw_dir / f"{arxiv_id}{sfx}.pdf")
    for p in candidates:
        if p.exists():
            return _sanitize_utf8(_canonical_clean_text(_canonical_extract_text(str(p))))
    return None


def parse_json_response(text: str) -> dict:
    raw = text.strip()
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
    return json.loads(raw)


def normalize_field_names(metadata: dict) -> dict:
    out = {PREFIX_MAP.get(k, k): v for k, v in metadata.items()}
    for f in CANONICAL_FIELDS:
        out.setdefault(f, None)
    return out


def build_prompts(papers, tokenizer, is_qwen3: bool):
    prompts = []
    for paper in papers:
        user_content = USER_PROMPT_TEMPLATE % paper["text"]
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]
        kwargs = {"tokenize": False, "add_generation_prompt": True}
        if is_qwen3:
            kwargs["enable_thinking"] = False
        try:
            formatted = tokenizer.apply_chat_template(messages, **kwargs)
        except TypeError:
            # Older tokenizer may not accept enable_thinking
            kwargs.pop("enable_thinking", None)
            formatted = tokenizer.apply_chat_template(messages, **kwargs)
        prompts.append(formatted)
    return prompts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help="HuggingFace model ID")
    parser.add_argument("--model-name", required=True, help="Short name for output dir")
    parser.add_argument("--quantization", default=None, help="fp8, awq, gptq, or None")
    parser.add_argument("--max-model-len", type=int, default=131072)
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.90)
    parser.add_argument("--tensor-parallel-size", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--dev-only", action="store_true")
    parser.add_argument("--paper", type=str, help="Process a single paper by ID")
    parser.add_argument("--enable-expert-parallel", action="store_true",
                        help="For MoE (Llama 4, Qwen3-Next): distribute experts instead of sharding")
    parser.add_argument("--enforce-eager", action="store_true",
                        help="Disable CUDA graph capture. Needed for Gemma 4 (vLLM issue #39914).")
    parser.add_argument("--rope-scaling", type=str, default=None,
                        help='JSON rope scaling override, e.g. '
                             '\'{"rope_type":"yarn","factor":4.0,'
                             '"original_max_position_embeddings":32768}\' '
                             '(needed to serve 32K-native Qwen3 dense models '
                             'at 131K)')
    parser.add_argument("--max-num-batched-tokens", type=int, default=None,
                        help="Prefill chunk size cap. Set to 4096 for Gemma 4 to avoid prefill hang.")
    args = parser.parse_args()

    # ── Paper list (102-benchmark) ──
    with open(ROOT / "data" / "agentic" / "dev_test_split.json") as f:
        split = json.load(f)
    if args.paper:
        paper_ids = [args.paper]
    elif args.dev_only:
        paper_ids = sorted(split["dev"])
    else:
        paper_ids = sorted(split["dev"] + split["test"])

    output_dir = ROOT / "data" / "extractions" / args.model_name
    output_dir.mkdir(parents=True, exist_ok=True)
    fail_dir = output_dir / "failures"
    fail_dir.mkdir(exist_ok=True)

    # ── Skip done; resolve PDFs up-front ──
    todo = []
    for pid in paper_ids:
        if (output_dir / f"{pid}.json").exists():
            continue
        text = extract_paper_text(pid)
        if text is None:
            print(f"SKIP: no PDF for {pid}")
            continue
        todo.append((pid, text))

    print("=" * 60)
    print("CroissantMiner Open-Source Extraction")
    print("=" * 60)
    print(f"Model: {args.model}")
    print(f"Papers: {len(todo)} to process ({len(paper_ids) - len(todo)} already done or no PDF)")
    print(f"Output: {output_dir}")
    print(f"Prompt hash: {_PROMPT_HASH}")
    print(f"Git commit: {_GIT_COMMIT}")
    print("=" * 60)
    if not todo:
        print("Nothing to process.")
        return

    # ── Load vLLM ──
    print(f"\nLoading {args.model} on {args.tensor_parallel_size} GPU(s)...")
    t0 = time.time()
    from vllm import LLM, SamplingParams
    from transformers import AutoTokenizer

    try:
        from vllm.sampling_params import StructuredOutputsParams
        has_structured = True
    except ImportError:
        has_structured = False
        print("WARNING: StructuredOutputsParams not available; relying on prompt for JSON.")

    llm_kwargs = dict(
        model=args.model,
        quantization=args.quantization,
        max_model_len=args.max_model_len,
        gpu_memory_utilization=args.gpu_memory_utilization,
        tensor_parallel_size=args.tensor_parallel_size,
        dtype="bfloat16",
        trust_remote_code=True,
        enforce_eager=args.enforce_eager,
    )
    if args.enable_expert_parallel:
        llm_kwargs["enable_expert_parallel"] = True
    if args.max_num_batched_tokens is not None:
        llm_kwargs["max_num_batched_tokens"] = args.max_num_batched_tokens
    if args.rope_scaling:
        llm_kwargs["hf_overrides"] = {"rope_scaling": json.loads(args.rope_scaling)}
    llm = LLM(**llm_kwargs)
    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    load_time = time.time() - t0
    print(f"Model loaded in {load_time:.0f}s")

    is_qwen3 = "qwen3" in args.model.lower()
    if is_qwen3:
        print("Qwen3 family detected — disabling thinking mode for JSON extraction")

    # Guard: drop papers whose rendered prompt exceeds the context window
    # (prompt + generation budget). Prevents one oversized paper from
    # crashing a whole batch; skipped papers are logged and reported.
    max_input = args.max_model_len - args.max_tokens
    kept, dropped = [], []
    for pid, text in todo:
        rendered = build_prompts([{"text": text}], tokenizer, is_qwen3)[0]
        n_tok = len(tokenizer(rendered).input_ids)
        if n_tok > max_input:
            dropped.append((pid, n_tok))
            print(f"SKIP {pid}: prompt {n_tok:,} tokens > limit {max_input:,}")
        else:
            kept.append((pid, text))
    todo = kept
    if dropped:
        print(f"Context-window skips: {len(dropped)} paper(s): "
              + ", ".join(f"{p} ({n:,}t)" for p, n in dropped))

    sampling_kwargs = dict(
        temperature=args.temperature,
        top_p=0.8 if args.temperature > 0 else 1.0,
        top_k=20 if args.temperature > 0 else -1,
        max_tokens=args.max_tokens,
    )
    if has_structured:
        sampling_kwargs["structured_outputs"] = StructuredOutputsParams(json=EXTRACTION_SCHEMA)
        print("Using guided JSON decoding (xgrammar)")
    sampling_params = SamplingParams(**sampling_kwargs)

    def _meta_block() -> dict:
        return {
            "parser": "pypdf2",
            "parser_version": "3.0.1",
            "prompt_sha256_prefix": _PROMPT_HASH,
            "prompt_chars": len(SYSTEM_PROMPT),
            "model_id": args.model,
            "provider": "vllm",
            "temperature": args.temperature,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "git_commit": _GIT_COMMIT,
            "paper_set": "102_dev_test_split",
            "script": "scripts/euler/extract_openmodels.py",
            "mode": "vllm_offline",
            "max_model_len": args.max_model_len,
            "tensor_parallel_size": args.tensor_parallel_size,
            "quantization": args.quantization,
        }

    # ── Run in batches ──
    total_ok = 0
    total_fail = 0

    for batch_start in range(0, len(todo), args.batch_size):
        batch = todo[batch_start:batch_start + args.batch_size]
        batch_num = batch_start // args.batch_size + 1
        total_batches = (len(todo) + args.batch_size - 1) // args.batch_size
        print(f"\nBatch {batch_num}/{total_batches} ({len(batch)} papers)")

        papers = [{"paper_id": pid, "text": text} for pid, text in batch]
        prompts = build_prompts(papers, tokenizer, is_qwen3)

        t1 = time.time()
        outputs = llm.generate(prompts, sampling_params)
        inference_time = time.time() - t1

        for paper, output in zip(papers, outputs):
            pid = paper["paper_id"]
            raw_text = output.outputs[0].text
            prompt_tokens = len(output.prompt_token_ids)
            output_tokens = len(output.outputs[0].token_ids)
            usage = {"input_tokens": prompt_tokens, "output_tokens": output_tokens}

            try:
                metadata = parse_json_response(raw_text)
                metadata = normalize_field_names(metadata)
                is_valid, errors = validate_extraction(metadata, pid)
                result = {
                    "dataset_id": pid,
                    "model": args.model,
                    "extraction": metadata,
                    "usage": usage,
                    "valid": is_valid,
                    "_meta": _meta_block(),
                }
                if not is_valid:
                    result["validation_errors"] = errors
                non_null = sum(1 for v in metadata.values() if v is not None)
                status = "OK" if is_valid else f"WARN({len(errors)})"
                print(f"  {pid}: {status} {non_null}/30 fields "
                      f"({prompt_tokens}in/{output_tokens}out, {inference_time/len(batch):.1f}s/paper)")
                total_ok += 1
            except Exception as e:
                result = {
                    "dataset_id": pid,
                    "model": args.model,
                    "extraction": None,
                    "usage": usage,
                    "valid": False,
                    "error": f"{type(e).__name__}: {str(e)[:200]}",
                    "_meta": _meta_block(),
                }
                (fail_dir / f"{pid.replace('/', '__')}_raw.txt").write_text(raw_text or "")
                print(f"  {pid}: FAILED ({str(e)[:60]})")
                total_fail += 1

            with open(output_dir / f"{pid}.json", "w") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)

    elapsed = time.time() - t0
    print(f"\n{'=' * 60}")
    print("COMPLETE")
    print(f"{'=' * 60}")
    print(f"Papers: {total_ok} OK, {total_fail} failed")
    print(f"Total time: {elapsed:.0f}s ({elapsed/60:.1f} min)")
    print(f"Output: {output_dir}")

    with open(output_dir / "_summary.json", "w") as f:
        json.dump({
            "model": args.model,
            "model_name": args.model_name,
            "papers_ok": total_ok,
            "papers_failed": total_fail,
            "elapsed_seconds": round(elapsed, 1),
            "cost_usd": 0.0,
            "git_commit": _GIT_COMMIT,
            "prompt_sha256_prefix": _PROMPT_HASH,
        }, f, indent=2)


if __name__ == "__main__":
    main()
