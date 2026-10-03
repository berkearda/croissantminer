#!/usr/bin/env python3
"""
Batch-API extraction on the 102-paper dev+test split for 5 proprietary models.

All three providers (Anthropic, OpenAI, Google) offer a batch API at
50% of synchronous pricing with a 24h SLA. Most batches finish in <1h.

Output matches the real-time path in extract_all_models.py:
  data/extractions/<output_dir>/<ds_id>.json  (with _meta provenance block)

Per-model batch handle lives in:
  data/extractions/<output_dir>/_batch/batch_info.json

Subcommands:
  submit  — build JSONL, upload/create batch job, save batch handle
  status  — poll all submitted batches, print state + counts
  fetch   — download results for finished batches, write per-paper JSON
  all     — submit, then poll until done, then fetch (blocks)

Usage:
  python extract_all_models_batch.py submit --model all
  python extract_all_models_batch.py status
  python extract_all_models_batch.py fetch --model all

Note: Skip-if-exists semantics match the real-time script. If a paper
already has an output JSON, it is excluded from the batch payload.
"""

import argparse
import hashlib
import io
import json
import logging
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent.parent.parent
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

from config import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from validation.validate_extraction import CANONICAL_FIELDS, validate_extraction

_PROMPT_HASH = hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()[:16]
try:
    _GIT_COMMIT = subprocess.check_output(
        ["git", "rev-parse", "--short", "HEAD"],
        stderr=subprocess.DEVNULL,
    ).decode().strip()
except Exception:
    _GIT_COMMIT = "unknown"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("batch")

PROCESSED = ROOT / "data" / "processed"
EXTRACTIONS = ROOT / "data" / "extractions"

MODELS = {
    "claude-opus-4-7": {
        "name": "Claude Opus 4.7",
        "model_id": "claude-opus-4-7",
        "provider": "anthropic",
        "output_dir": "claude_opus_4_7",
        "skip_temperature": True,  # Opus 4.7 rejects temperature (extended-thinking model)
    },
    "claude-sonnet-4-6": {
        "name": "Claude Sonnet 4.6",
        "model_id": "claude-sonnet-4-6",
        "provider": "anthropic",
        "output_dir": "claude_sonnet_4_6",
    },
    "claude-sonnet-4-5-repro": {
        "name": "Claude Sonnet 4.5 (reproducibility re-run)",
        "model_id": "claude-sonnet-4-5-20250929",
        "provider": "anthropic",
        "output_dir": "claude_sonnet_4_5_repro",
    },
    "gpt-5.4": {
        "name": "GPT-5.4 full",
        "model_id": "gpt-5.4-2026-03-05",
        "provider": "openai",
        "output_dir": "gpt5.4_full",
        "max_tokens_param": "max_completion_tokens",
    },
    "gpt-5.4-mini": {
        "name": "GPT-5.4 Mini",
        "model_id": "gpt-5.4-mini-2026-03-17",
        "provider": "openai",
        "output_dir": "gpt5.4_mini",
        "max_tokens_param": "max_completion_tokens",
    },
    "gemini-flash": {
        "name": "Gemini 2.5 Flash",
        "model_id": "gemini-2.5-flash",
        "provider": "google",
        "output_dir": "gemini_2.5_flash",
    },
    "gemini-pro": {
        "name": "Gemini 3.1 Pro Preview",
        "model_id": "gemini-3.1-pro-preview",
        "provider": "google",
        "output_dir": "gemini_3.1_pro",
    },
}
PAPER_MODELS = list(MODELS)  # `--model all` runs these, the paper's models, and nothing added below

# Newer Gemini models for the leaderboard (2026-10-02): the paper's prompt and temperature 0, with room for the
# thinking tokens these models spend before answering. The "-t1" entries use temperature 1.0, the value Google
# recommends for all Gemini 3 models (ai.google.dev/gemini-api/docs/gemini-3), to test that setting.
for _key, _name, _model_id in [("gemini-3-flash", "Gemini 3 Flash Preview", "gemini-3-flash-preview"),
                               ("gemini-3.5-flash", "Gemini 3.5 Flash", "gemini-3.5-flash"),
                               ("gemini-3.6-flash", "Gemini 3.6 Flash", "gemini-3.6-flash"),
                               ("gemini-3.7-flash", "Gemini 3.7 Flash", "gemini-3.7-flash"),
                               ("gemini-3.8-flash", "Gemini 3.8 Flash", "gemini-3.8-flash")]:
    MODELS[_key] = {"name": _name, "model_id": _model_id, "provider": "google",
                    "output_dir": _model_id.replace("-", "_").replace(".", "_"), "max_output_tokens": 16384}
MODELS["gemini-3.8-flash-t1"] = {**MODELS["gemini-3.8-flash"], "name": "Gemini 3.8 Flash (temperature 1)",
                                 "output_dir": "gemini_3_8_flash_t1", "temperature": 1.0}
MODELS["gemini-pro-t1"] = {**MODELS["gemini-pro"], "name": "Gemini 3.1 Pro Preview (temperature 1)",
                           "output_dir": "gemini_3_1_pro_t1", "temperature": 1.0, "max_output_tokens": 16384}
# Newer OpenAI models (2026-10-02). They accept only their default temperature (1), so it is left out, as for Claude
# Opus 4.7 in the paper; their reasoning tokens count toward the output limit, hence 16,384.
for _key, _name, _model_id in [("gpt-6-luna", "GPT-6 Luna", "gpt-6-luna"), ("gpt-6.1-sol", "GPT-6.1 Sol", "gpt-6.1-sol"),
                               ("gpt-5.5", "GPT-5.5", "gpt-5.5-2026-04-23")]:
    MODELS[_key] = {"name": _name, "model_id": _model_id, "provider": "openai", "max_tokens_param": "max_completion_tokens",
                    "output_dir": _key.replace("-", "_").replace(".", "_"), "skip_temperature": True,
                    "max_output_tokens": 16384}

TEST_PAPERS = ["AI4Math_MathVista", "openai_gsm8k", "rajpurkar_squad"]
MAX_OUTPUT_TOKENS = 8192  # 4096 truncated Gemini 3.1 Pro (~42% of papers); 8192 gives headroom + handles Opus 4.7 extended-thinking budget
_CUSTOM_ID_RE = re.compile(r"[^a-zA-Z0-9_-]")


# ── shared helpers (mirror extract_all_models.py) ──

def _sanitize_custom_id(ds_id: str) -> str:
    return _CUSTOM_ID_RE.sub("_", ds_id.replace("/", "__"))[:64]


def parse_json_response(text: str):
    text = text.strip()
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0].strip()
    return json.loads(text)


def normalize_field_names(metadata: dict) -> dict:
    PREFIX_MAP = {
        "sc:name": "name", "sc:description": "description", "sc:url": "url",
        "sc:license": "license", "sc:creator": "creator", "sc:publisher": "publisher",
        "sc:datePublished": "datePublished", "sc:inLanguage": "inLanguage",
        "cr:citeAs": "citeAs", "cr:isLiveDataset": "isLiveDataset",
        "sc:citeAs": "citeAs", "sc:isLiveDataset": "isLiveDataset",
        "cr:name": "name", "cr:description": "description",
    }
    return {PREFIX_MAP.get(k, k): v for k, v in metadata.items()}


def _sanitize_utf8(text: str) -> str:
    """Drop lone UTF-16 surrogates that PyPDF2 occasionally emits.

    JSON encoding (via httpx) rejects them with 'surrogates not allowed'.
    """
    return text.encode("utf-8", errors="replace").decode("utf-8")


def get_paper_text(ds_id: str):
    from croissantminer.pdf.reader import extract_text_from_pdf as _extract
    from croissantminer.pdf.processor import clean_text as _clean
    raw_dir = ROOT / "data" / "raw"
    pdf_candidates = [
        raw_dir / f"{ds_id}.pdf",
        raw_dir / f"{ds_id.replace('_', '/')}.pdf",
    ]
    paper_links_path = ROOT / "data" / "paper_links.json"
    if paper_links_path.exists():
        with open(paper_links_path) as f:
            paper_links = json.load(f)
        m = re.search(r"(\d{4}\.\d{4,5})", paper_links.get(ds_id, ""))
        if m:
            arxiv_id = m.group(1)
            for suffix in ["", "v1", "v2", "v3", "v4", "v5"]:
                pdf_candidates.append(raw_dir / f"{arxiv_id}{suffix}.pdf")
    for pdf_path in pdf_candidates:
        if pdf_path.exists():
            return _sanitize_utf8(_clean(_extract(str(pdf_path))))
    return None


def _meta_block(cfg: dict) -> dict:
    return {
        "parser": "pypdf2",
        "parser_version": "3.0.1",
        "prompt_sha256_prefix": _PROMPT_HASH,
        "prompt_chars": len(SYSTEM_PROMPT),
        "model_id": cfg["model_id"],
        "provider": cfg["provider"],
        "temperature": None if cfg.get("skip_temperature") else cfg.get("temperature", 0.0),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "git_commit": _GIT_COMMIT,
        "paper_set": "102_dev_test_split",
        "script": "scripts/experiments/model_comparison/extract_all_models_batch.py",
        "mode": "batch",
    }


def _finalize_metadata(raw_text: str) -> tuple:
    metadata = parse_json_response(raw_text)
    metadata = normalize_field_names(metadata)
    for field in CANONICAL_FIELDS:
        metadata.setdefault(field, None)
    return metadata


def _write_output(cfg: dict, ds_id: str, raw_text: str, usage: dict, out_dir: Path, fail_dir: Path) -> bool:
    try:
        metadata = _finalize_metadata(raw_text)
    except Exception as e:
        log.error(f"  {ds_id}: JSON parse failed ({e})")
        (fail_dir / f"{ds_id.replace('/', '__')}_raw.txt").write_text(raw_text or "")
        return False
    is_valid, errors = validate_extraction(metadata, ds_id)
    output = {
        "dataset_id": ds_id,
        "model": cfg["model_id"],
        "extraction": metadata,
        "usage": usage,
        "valid": is_valid,
        "_meta": _meta_block(cfg),
    }
    if not is_valid:
        output["validation_errors"] = errors
    out_path = out_dir / f"{ds_id.replace('/', '__')}.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    status = "OK" if is_valid else f"WARN({len(errors)})"
    log.info(f"  {ds_id}: {status} ({usage.get('input_tokens',0)}in/{usage.get('output_tokens',0)}out)")
    return True


# ── paper-set helpers ──

def load_paper_ids(test: bool, split_name: str = "both") -> list:
    if test:
        return TEST_PAPERS
    split_path = ROOT / "data" / "agentic" / "dev_test_split.json"
    with open(split_path) as f:
        split = json.load(f)
    return sorted(split["dev"] + split["test"] if split_name == "both" else split[split_name])


def pending_papers(cfg: dict, ds_ids: list) -> list:
    out_dir = EXTRACTIONS / cfg["output_dir"]
    return [d for d in ds_ids if not (out_dir / f"{d.replace('/', '__')}.json").exists()]


def batch_info_path(cfg: dict) -> Path:
    return EXTRACTIONS / cfg["output_dir"] / "_batch" / "batch_info.json"


def save_batch_info(cfg: dict, info: dict):
    p = batch_info_path(cfg)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w") as f:
        json.dump(info, f, indent=2)


def load_batch_info(cfg: dict):
    p = batch_info_path(cfg)
    if not p.exists():
        return None
    with open(p) as f:
        return json.load(f)


# ── Anthropic batch ──

def anthropic_submit(cfg: dict, ds_ids: list) -> dict:
    import anthropic
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request

    client = anthropic.Anthropic()
    requests = []
    id_map = {}
    for ds_id in ds_ids:
        text = get_paper_text(ds_id)
        if text is None:
            log.warning(f"  skip (no PDF): {ds_id}")
            continue
        cid = _sanitize_custom_id(ds_id)
        id_map[cid] = ds_id
        params_kwargs = {
            "model": cfg["model_id"],
            "max_tokens": MAX_OUTPUT_TOKENS,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": USER_PROMPT_TEMPLATE % text}],
        }
        if not cfg.get("skip_temperature"):
            params_kwargs["temperature"] = 0.0
        requests.append(
            Request(
                custom_id=cid,
                params=MessageCreateParamsNonStreaming(**params_kwargs),
            )
        )
    if not requests:
        return {}
    batch = client.messages.batches.create(requests=requests)
    log.info(f"  submitted: {batch.id} ({len(requests)} requests)")
    return {
        "provider": "anthropic",
        "batch_id": batch.id,
        "submitted_at": datetime.utcnow().isoformat() + "Z",
        "id_map": id_map,
        "model_id": cfg["model_id"],
    }


def anthropic_status(info: dict) -> dict:
    import anthropic
    client = anthropic.Anthropic()
    batch = client.messages.batches.retrieve(info["batch_id"])
    return {
        "state": batch.processing_status,
        "counts": dict(batch.request_counts) if hasattr(batch, "request_counts") else {},
        "done": batch.processing_status == "ended",
    }


def anthropic_fetch(cfg: dict, info: dict) -> int:
    import anthropic
    client = anthropic.Anthropic()
    out_dir = EXTRACTIONS / cfg["output_dir"]
    fail_dir = out_dir / "failures"
    fail_dir.mkdir(parents=True, exist_ok=True)
    id_map = info["id_map"]
    written = 0
    for result in client.messages.batches.results(info["batch_id"]):
        ds_id = id_map.get(result.custom_id, result.custom_id)
        if result.result.type == "succeeded":
            msg = result.result.message
            # Content can be multi-block (text + thinking) or empty on edge cases;
            # concatenate all text blocks, skip non-text.
            raw_text = ""
            for block in msg.content:
                if getattr(block, "type", None) == "text":
                    raw_text += block.text
                elif hasattr(block, "text"):
                    raw_text += block.text
            usage = {
                "input_tokens": msg.usage.input_tokens,
                "output_tokens": msg.usage.output_tokens,
            }
            if not raw_text.strip():
                log.error(f"  {ds_id}: empty content from model (blocks={[getattr(b,'type',type(b).__name__) for b in msg.content]})")
                (fail_dir / f"{ds_id.replace('/', '__')}_empty.json").write_text(
                    json.dumps({"ds_id": ds_id, "usage": usage}, indent=2)
                )
                continue
            if _write_output(cfg, ds_id, raw_text, usage, out_dir, fail_dir):
                written += 1
        else:
            log.error(f"  {ds_id}: {result.result.type}")
            (fail_dir / f"{ds_id.replace('/', '__')}_error.json").write_text(
                json.dumps(result.result.model_dump() if hasattr(result.result, "model_dump") else str(result.result), indent=2)
            )
    return written


# ── OpenAI batch ──
#
# OpenAI enforces a per-model "enqueued token" limit across all in-flight
# batches for an organization (gpt-5.4: 900K, gpt-5.4-mini: 2M, ...). A
# 100-paper run at ~30K tokens/paper exceeds this, so we chunk the
# requests and submit each chunk only after the previous has dequeued
# (status != validating/in_progress). Chunk handles live under
# info["chunks"] so status/fetch/resubmit can iterate them uniformly.

OPENAI_ENQUEUED_LIMITS = {
    # Model-specific daily enqueued-token caps (conservative ~80% of published).
    "gpt-5.4-2026-03-05": 700_000,
    "gpt-5.4-mini-2026-03-17": 1_600_000,
}
OPENAI_DEFAULT_LIMIT = 700_000


def _estimate_request_tokens(body: dict) -> int:
    # Char-based heuristic; we only need an upper bound for chunk packing.
    total_chars = sum(len(m.get("content", "")) for m in body.get("messages", []))
    return max(1, total_chars // 4)


def _build_openai_request_lines(cfg: dict, ds_ids: list):
    id_map = {}
    lines = []
    token_costs = []
    for ds_id in ds_ids:
        text = get_paper_text(ds_id)
        if text is None:
            log.warning(f"  skip (no PDF): {ds_id}")
            continue
        cid = _sanitize_custom_id(ds_id)
        id_map[cid] = ds_id
        body = {"model": cfg["model_id"]}
        if not cfg.get("skip_temperature"):  # newer reasoning models accept only their default temperature
            body["temperature"] = cfg.get("temperature", 0.0)
        body["messages"] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPT_TEMPLATE % text},
        ]
        body[cfg.get("max_tokens_param", "max_completion_tokens")] = cfg.get("max_output_tokens", MAX_OUTPUT_TOKENS)
        line = json.dumps({
            "custom_id": cid,
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": body,
        })
        lines.append(line)
        token_costs.append(_estimate_request_tokens(body) + cfg.get("max_output_tokens", MAX_OUTPUT_TOKENS))
    return lines, token_costs, id_map


def _chunk_by_tokens(lines: list, costs: list, limit: int) -> list:
    chunks = []
    cur_lines, cur_cost = [], 0
    for ln, c in zip(lines, costs):
        if cur_lines and cur_cost + c > limit:
            chunks.append(cur_lines)
            cur_lines, cur_cost = [], 0
        cur_lines.append(ln)
        cur_cost += c
    if cur_lines:
        chunks.append(cur_lines)
    return chunks


def _submit_openai_chunk(client, cfg: dict, chunk_lines: list, chunk_idx: int) -> dict:
    out_dir = EXTRACTIONS / cfg["output_dir"] / "_batch"
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_dir / f"batch_input_chunk{chunk_idx}.jsonl"
    jsonl_path.write_text("\n".join(chunk_lines) + "\n")
    with open(jsonl_path, "rb") as fh:
        batch_file = client.files.create(file=fh, purpose="batch")
    batch = client.batches.create(
        input_file_id=batch_file.id,
        endpoint="/v1/chat/completions",
        completion_window="24h",
    )
    log.info(f"    chunk {chunk_idx}: submitted {batch.id} ({len(chunk_lines)} requests)")
    return {
        "batch_id": batch.id,
        "input_file_id": batch_file.id,
        "n_requests": len(chunk_lines),
        "submitted_at": datetime.utcnow().isoformat() + "Z",
        "status": "submitted",
    }


def openai_submit(cfg: dict, ds_ids: list) -> dict:
    from openai import OpenAI
    client = OpenAI()
    lines, costs, id_map = _build_openai_request_lines(cfg, ds_ids)
    if not lines:
        return {}
    limit = OPENAI_ENQUEUED_LIMITS.get(cfg["model_id"], OPENAI_DEFAULT_LIMIT)
    chunks = _chunk_by_tokens(lines, costs, limit)
    log.info(f"  chunking {len(lines)} requests into {len(chunks)} chunks "
             f"(limit {limit} tokens/chunk): sizes {[len(c) for c in chunks]}")

    # Submit only the first chunk now. Subsequent chunks deferred to
    # cmd_status, which submits the next chunk when the previous completes.
    first = _submit_openai_chunk(client, cfg, chunks[0], chunk_idx=0)
    first["chunk_idx"] = 0
    pending = []
    for i, cl in enumerate(chunks[1:], start=1):
        chunk_path = EXTRACTIONS / cfg["output_dir"] / "_batch" / f"batch_input_chunk{i}.jsonl"
        chunk_path.write_text("\n".join(cl) + "\n")
        pending.append({"chunk_idx": i, "n_requests": len(cl), "jsonl": str(chunk_path), "status": "pending"})

    return {
        "provider": "openai",
        "model_id": cfg["model_id"],
        "output_dir": cfg["output_dir"],
        "id_map": id_map,
        "chunks": [first] + pending,
        "submitted_at": datetime.utcnow().isoformat() + "Z",
    }


def _openai_submit_next_pending(info: dict):
    """If any pending chunks exist and the prior chunk is terminal, submit the next.

    Gracefully handles OpenAI's enqueued-token counter lag after a prior
    chunk hits "completed": on `token_limit_exceeded` we keep the chunk
    pending so the next status call retries.
    """
    from openai import OpenAI
    client = OpenAI()
    chunks = info["chunks"]
    for i, chunk in enumerate(chunks):
        if chunk.get("status") == "pending":
            prior = chunks[i - 1]
            prior_status = prior.get("last_state")
            if prior_status not in {"completed", "failed", "expired", "cancelled"}:
                return False
            lines = Path(chunk["jsonl"]).read_text().strip().splitlines()
            try:
                new_chunk = _submit_openai_chunk(client, {
                    "model_id": info["model_id"],
                    "output_dir": info.get("output_dir", ""),
                }, lines, chunk_idx=chunk["chunk_idx"])
            except Exception as e:
                msg = str(e)
                if "token_limit_exceeded" in msg or "Enqueued token limit" in msg:
                    log.warning(f"    chunk {chunk['chunk_idx']}: token_limit_exceeded on submit; "
                                f"keeping pending, retry on next status poll")
                    # Leave status=pending so the next status call retries.
                    return False
                raise
            chunk.update(new_chunk)
            chunk["status"] = "submitted"
            return True
    return False


def openai_status(info: dict) -> dict:
    from openai import OpenAI
    client = OpenAI()
    chunks = info["chunks"]

    states, counts_agg = [], {"completed": 0, "failed": 0, "total": 0}
    any_pending = False
    all_done = True
    for chunk in chunks:
        if chunk.get("status") == "pending":
            states.append("pending")
            any_pending = True
            all_done = False
            continue
        bid = chunk.get("batch_id")
        if not bid:
            continue
        b = client.batches.retrieve(bid)
        st = b.status
        chunk["last_state"] = st
        states.append(st)
        c = b.request_counts.model_dump() if hasattr(b.request_counts, "model_dump") else dict(b.request_counts or {})
        for k in ("completed", "failed", "total"):
            counts_agg[k] += c.get(k, 0) or 0
        chunk["output_file_id"] = b.output_file_id
        chunk["error_file_id"] = b.error_file_id
        if st not in {"completed", "failed", "expired", "cancelled"}:
            all_done = False

    # If a chunk is terminal and pending chunks remain, submit the next one.
    submitted = _openai_submit_next_pending(info)
    if submitted:
        all_done = False  # new chunk in flight

    return {
        "state": "all-done" if all_done else (states[0] if states else "unknown"),
        "counts": counts_agg,
        "chunk_states": states,
        "done": all_done,
    }


def openai_fetch(cfg: dict, info: dict) -> int:
    from openai import OpenAI
    client = OpenAI()
    out_dir = EXTRACTIONS / cfg["output_dir"]
    fail_dir = out_dir / "failures"
    fail_dir.mkdir(parents=True, exist_ok=True)
    id_map = info["id_map"]
    written = 0

    for chunk in info["chunks"]:
        bid = chunk.get("batch_id")
        if not bid:
            continue
        # Refresh to get output_file_id
        b = client.batches.retrieve(bid)
        if b.output_file_id:
            content = client.files.content(b.output_file_id).content
            for line in content.decode("utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                ds_id = id_map.get(row["custom_id"], row["custom_id"])
                err = row.get("error")
                if err:
                    log.error(f"  {ds_id}: {err}")
                    (fail_dir / f"{ds_id.replace('/', '__')}_error.json").write_text(json.dumps(row, indent=2))
                    continue
                resp_body = row["response"]["body"]
                raw_text = resp_body["choices"][0]["message"]["content"]
                u = resp_body.get("usage", {})
                usage = {
                    "input_tokens": u.get("prompt_tokens", 0),
                    "output_tokens": u.get("completion_tokens", 0),
                    "reasoning_tokens": (u.get("completion_tokens_details") or {}).get("reasoning_tokens", 0),
                }
                if _write_output(cfg, ds_id, raw_text, usage, out_dir, fail_dir):
                    written += 1
        if b.error_file_id:
            err_content = client.files.content(b.error_file_id).content
            (fail_dir / f"chunk{chunk.get('chunk_idx','?')}_errors.jsonl").write_bytes(err_content)

    return written


# ── Google Gemini batch (REST) ──

def _gemini_api_key() -> str:
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set")
    return key


def gemini_submit(cfg: dict, ds_ids: list) -> dict:
    import requests
    api_key = _gemini_api_key()

    id_map = {}
    lines = []
    for ds_id in ds_ids:
        text = get_paper_text(ds_id)
        if text is None:
            log.warning(f"  skip (no PDF): {ds_id}")
            continue
        cid = _sanitize_custom_id(ds_id)
        id_map[cid] = ds_id
        request_body = {
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": USER_PROMPT_TEMPLATE % text}]}],
            "generationConfig": {
                "temperature": cfg.get("temperature", 0.0),
                "maxOutputTokens": cfg.get("max_output_tokens", MAX_OUTPUT_TOKENS),
            },
        }
        lines.append(json.dumps({"key": cid, "request": request_body}))
    if not lines:
        return {}

    out_dir = EXTRACTIONS / cfg["output_dir"] / "_batch"
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_dir / "batch_input.jsonl"
    body_bytes = ("\n".join(lines) + "\n").encode("utf-8")
    jsonl_path.write_bytes(body_bytes)

    display_name = f"croissantminer-{cfg['output_dir']}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

    # Step 1: initiate resumable upload.
    init_resp = requests.post(
        "https://generativelanguage.googleapis.com/upload/v1beta/files",
        headers={
            "x-goog-api-key": api_key,
            "X-Goog-Upload-Protocol": "resumable",
            "X-Goog-Upload-Command": "start",
            "X-Goog-Upload-Header-Content-Length": str(len(body_bytes)),
            "X-Goog-Upload-Header-Content-Type": "application/jsonl",
            "Content-Type": "application/json",
        },
        json={"file": {"display_name": display_name}},
        timeout=60,
    )
    if init_resp.status_code != 200:
        raise RuntimeError(f"Gemini upload init failed {init_resp.status_code}: {init_resp.text[:400]}")
    upload_url = init_resp.headers.get("X-Goog-Upload-URL") or init_resp.headers.get("x-goog-upload-url")
    if not upload_url:
        raise RuntimeError(f"Gemini upload init missing upload URL. Headers: {dict(init_resp.headers)}")

    # Step 2: upload bytes.
    up_resp = requests.post(
        upload_url,
        headers={
            "Content-Length": str(len(body_bytes)),
            "X-Goog-Upload-Offset": "0",
            "X-Goog-Upload-Command": "upload, finalize",
        },
        data=body_bytes,
        timeout=300,
    )
    if up_resp.status_code != 200:
        raise RuntimeError(f"Gemini upload finalize failed {up_resp.status_code}: {up_resp.text[:400]}")
    file_meta = up_resp.json().get("file", {})
    file_name = file_meta.get("name")
    if not file_name:
        raise RuntimeError(f"Gemini upload returned no file name: {up_resp.text[:400]}")

    # Step 3: create batch job.
    create_url = f"https://generativelanguage.googleapis.com/v1beta/models/{cfg['model_id']}:batchGenerateContent"
    create_resp = requests.post(
        create_url,
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
        json={"batch": {"display_name": display_name, "input_config": {"file_name": file_name}}},
        timeout=60,
    )
    if create_resp.status_code != 200:
        raise RuntimeError(f"Gemini batch create failed {create_resp.status_code}: {create_resp.text[:400]}")
    batch_data = create_resp.json()
    batch_name = batch_data.get("name")
    log.info(f"  submitted: {batch_name} ({len(lines)} requests, file={file_name})")
    return {
        "provider": "google",
        "batch_name": batch_name,
        "input_file": file_name,
        "submitted_at": datetime.utcnow().isoformat() + "Z",
        "id_map": id_map,
        "model_id": cfg["model_id"],
    }


def gemini_status(info: dict) -> dict:
    import requests
    api_key = _gemini_api_key()
    resp = requests.get(
        f"https://generativelanguage.googleapis.com/v1beta/{info['batch_name']}",
        headers={"x-goog-api-key": api_key},
        timeout=60,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Gemini status failed {resp.status_code}: {resp.text[:400]}")
    data = resp.json()
    meta = data.get("metadata", {})
    state = data.get("state") or meta.get("state") or "UNKNOWN"
    return {
        "state": state,
        "counts": meta.get("requestCounts") or data.get("requestCounts") or {},
        "done": state in {
            "JOB_STATE_SUCCEEDED", "JOB_STATE_FAILED", "JOB_STATE_CANCELLED", "JOB_STATE_EXPIRED",
            "BATCH_STATE_SUCCEEDED", "BATCH_STATE_FAILED", "BATCH_STATE_CANCELLED", "BATCH_STATE_EXPIRED",
        },
        "output_file": (data.get("response", {}) or {}).get("responsesFile") or (data.get("output", {}) or {}).get("responsesFile"),
        "raw": data,
    }


def _gemini_text(resp_body: dict) -> str:
    """The answer text of a Gemini response: its text parts, without thought summaries (raises if there is none)."""
    parts = resp_body["candidates"][0]["content"]["parts"]
    texts = [p["text"] for p in parts if "text" in p and not p.get("thought")]
    if not texts:
        raise KeyError("no text part")
    return "".join(texts)


def gemini_fetch(cfg: dict, info: dict) -> int:
    import requests
    api_key = _gemini_api_key()
    st = gemini_status(info)
    out_dir = EXTRACTIONS / cfg["output_dir"]
    fail_dir = out_dir / "failures"
    fail_dir.mkdir(parents=True, exist_ok=True)
    id_map = info["id_map"]

    # The batch response nests differently across API versions; try common paths.
    raw = st["raw"]
    responses_file = (
        raw.get("response", {}).get("responsesFile")
        or raw.get("output", {}).get("responsesFile")
        or (raw.get("metadata", {}).get("output") or {}).get("responsesFile")
    )
    inlined = (
        raw.get("response", {}).get("inlinedResponses")
        or raw.get("output", {}).get("inlinedResponses")
    )

    written = 0
    if responses_file:
        dl = requests.get(
            f"https://generativelanguage.googleapis.com/download/v1beta/{responses_file}:download",
            params={"alt": "media"},
            headers={"x-goog-api-key": api_key},
            timeout=300,
        )
        if dl.status_code != 200:
            raise RuntimeError(f"Gemini download failed {dl.status_code}: {dl.text[:400]}")
        for line in dl.content.decode("utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            key = row.get("key") or row.get("custom_id")
            ds_id = id_map.get(key, key or "unknown")
            resp_body = row.get("response")
            if not resp_body or "error" in row:
                log.error(f"  {ds_id}: {row.get('error') or 'no response'}")
                (fail_dir / f"{ds_id.replace('/', '__')}_error.json").write_text(json.dumps(row, indent=2))
                continue
            try:
                raw_text = _gemini_text(resp_body)
            except (KeyError, IndexError) as e:
                log.error(f"  {ds_id}: malformed response ({e})")
                (fail_dir / f"{ds_id.replace('/', '__')}_error.json").write_text(json.dumps(row, indent=2))
                continue
            u = resp_body.get("usageMetadata", {})
            usage = {
                "input_tokens": u.get("promptTokenCount", 0),
                "output_tokens": u.get("candidatesTokenCount", 0),
                "thinking_tokens": u.get("thoughtsTokenCount", 0),
            }
            if _write_output(cfg, ds_id, raw_text, usage, out_dir, fail_dir):
                written += 1
    elif inlined:
        for item in inlined:
            key = item.get("key") or item.get("custom_id")
            ds_id = id_map.get(key, key or "unknown")
            resp_body = item.get("response")
            if not resp_body or "error" in item:
                log.error(f"  {ds_id}: {item.get('error') or 'no response'}")
                continue
            try:
                raw_text = _gemini_text(resp_body)
            except (KeyError, IndexError):
                continue
            u = resp_body.get("usageMetadata", {})
            usage = {
                "input_tokens": u.get("promptTokenCount", 0),
                "output_tokens": u.get("candidatesTokenCount", 0),
                "thinking_tokens": u.get("thoughtsTokenCount", 0),
            }
            if _write_output(cfg, ds_id, raw_text, usage, out_dir, fail_dir):
                written += 1
    else:
        log.warning(f"  no output file found; full state: {json.dumps(raw)[:500]}")

    return written


# ── provider dispatch ──

SUBMIT = {"anthropic": anthropic_submit, "openai": openai_submit, "google": gemini_submit}
STATUS = {"anthropic": anthropic_status, "openai": openai_status, "google": gemini_status}
FETCH = {"anthropic": anthropic_fetch, "openai": openai_fetch, "google": gemini_fetch}


def cmd_submit(model_keys: list, ds_ids: list, force: bool):
    for mk in model_keys:
        cfg = MODELS[mk]
        log.info(f"\n── submit: {cfg['name']} ──")
        existing = load_batch_info(cfg)
        if existing and not force:
            log.info(f"  batch already submitted: {existing.get('batch_id') or existing.get('batch_name')} "
                     f"(use --force to resubmit)")
            continue
        pending = pending_papers(cfg, ds_ids)
        log.info(f"  pending papers: {len(pending)} / {len(ds_ids)}")
        if not pending:
            log.info("  nothing to submit")
            continue
        info = SUBMIT[cfg["provider"]](cfg, pending)
        if info:
            save_batch_info(cfg, info)


def cmd_status(model_keys: list) -> dict:
    summary = {}
    for mk in model_keys:
        cfg = MODELS[mk]
        info = load_batch_info(cfg)
        if not info:
            log.info(f"  {cfg['name']}: no batch submitted")
            summary[mk] = {"done": True, "state": "none"}
            continue
        try:
            st = STATUS[cfg["provider"]](info)
        except Exception as e:
            log.error(f"  {cfg['name']}: status error {e}")
            summary[mk] = {"done": False, "state": "error", "error": str(e)}
            continue
        # Persist any state updates (chunk last_state, newly-submitted chunks).
        save_batch_info(cfg, info)
        extra = f" chunks={st.get('chunk_states')}" if st.get("chunk_states") else ""
        log.info(f"  {cfg['name']}: state={st['state']} counts={st.get('counts')}{extra}")
        summary[mk] = st
    return summary


def cmd_fetch(model_keys: list):
    for mk in model_keys:
        cfg = MODELS[mk]
        info = load_batch_info(cfg)
        if not info:
            log.info(f"  {cfg['name']}: no batch submitted")
            continue
        try:
            st = STATUS[cfg["provider"]](info)
        except Exception as e:
            log.error(f"  {cfg['name']}: status error {e}")
            continue
        if not st["done"]:
            log.info(f"  {cfg['name']}: not done yet (state={st['state']})")
            continue
        log.info(f"\n── fetch: {cfg['name']} ──")
        n = FETCH[cfg["provider"]](cfg, info)
        log.info(f"  wrote {n} extraction files")


def cmd_all(model_keys: list, ds_ids: list, poll_interval: int, force: bool):
    cmd_submit(model_keys, ds_ids, force=force)
    while True:
        summary = cmd_status(model_keys)
        if all(v.get("done") for v in summary.values()):
            break
        log.info(f"  (sleeping {poll_interval}s)")
        time.sleep(poll_interval)
    cmd_fetch(model_keys)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", choices=["submit", "status", "fetch", "all"])
    parser.add_argument("--model", choices=list(MODELS.keys()) + ["all"], default="all")
    parser.add_argument("--test", action="store_true", help="3-paper dry-run")
    parser.add_argument("--force", action="store_true", help="Re-submit even if batch handle exists")
    parser.add_argument("--split", choices=["both", "dev", "test"], default="both",
                        help="papers: dev + test (default), or only the 14 dev or the 88 test papers")
    parser.add_argument("--poll-interval", type=int, default=120, help="Seconds between status polls in `all` mode")
    args = parser.parse_args()

    model_keys = PAPER_MODELS if args.model == "all" else [args.model]
    ds_ids = load_paper_ids(args.test, args.split)
    log.info(f"Paper set: {len(ds_ids)} papers, models: {model_keys}")

    if args.cmd == "submit":
        cmd_submit(model_keys, ds_ids, force=args.force)
    elif args.cmd == "status":
        cmd_status(model_keys)
    elif args.cmd == "fetch":
        cmd_fetch(model_keys)
    elif args.cmd == "all":
        cmd_all(model_keys, ds_ids, args.poll_interval, force=args.force)


if __name__ == "__main__":
    main()
