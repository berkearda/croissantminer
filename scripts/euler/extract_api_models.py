#!/usr/bin/env python3
"""
CroissantMiner — API-based model extraction via OpenAI-compatible endpoints.

Used for models we can't (or won't) self-host: GLM-5.1 (744B), DeepSeek V3,
OpenRouter-only models, Together, Groq, etc.

Standardization (matches extract_all_models_batch.py + extract_openmodels.py):
- Prompt: SYSTEM_PROMPT + USER_PROMPT_TEMPLATE from config.
- Parser: PyPDF2 3.0.1 via croissantminer.pdf canonical path.
- Paper set: 102-paper dev+test split.
- Output schema: {dataset_id, model, extraction, usage, valid, _meta}.

Usage:
  # GLM-5.1 via Z.ai API (current SOTA open-source, Apr 2026)
  export ZAI_API_KEY=...
  python scripts/euler/extract_api_models.py \\
      --provider zai --model glm-5.1 --model-name glm_5_1

  # DeepSeek V3
  export DEEPSEEK_API_KEY=...
  python scripts/euler/extract_api_models.py \\
      --provider deepseek --model deepseek-chat --model-name deepseek_v3

  # OpenRouter (free Qwen 3.6 Plus preview)
  export OPENROUTER_API_KEY=...
  python scripts/euler/extract_api_models.py \\
      --provider openrouter --model qwen/qwen3.6-plus-preview --model-name qwen3_6_plus
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

from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).parent.parent.parent
load_dotenv(ROOT / ".env")
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

PROVIDERS = {
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "key_env": "OPENROUTER_API_KEY",
        "rpm_limit": 20,
    },
    "together": {
        "base_url": "https://api.together.xyz/v1",
        "key_env": "TOGETHER_API_KEY",
        "rpm_limit": 60,
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "key_env": "DEEPSEEK_API_KEY",
        "rpm_limit": 60,
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "key_env": "GROQ_API_KEY",
        "rpm_limit": 30,
    },
    "zai": {
        "base_url": "https://api.z.ai/api/paas/v4",
        "key_env": "ZAI_API_KEY",
        "rpm_limit": 60,
    },
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", required=True, choices=list(PROVIDERS.keys()))
    parser.add_argument("--model", required=True, help="Model ID as used by the provider")
    parser.add_argument("--model-name", required=True, help="Short name for output dir")
    parser.add_argument("--dev-only", action="store_true")
    parser.add_argument("--paper", type=str)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=8192,
                        help="Max output tokens. 4096 was too tight for GLM-5.1 (verbose); 8192 gives headroom.")
    args = parser.parse_args()

    prov = PROVIDERS[args.provider]
    api_key = os.environ.get(prov["key_env"])
    if not api_key:
        print(f"ERROR: set {prov['key_env']} in env or .env")
        sys.exit(1)
    client = OpenAI(base_url=prov["base_url"], api_key=api_key)

    with open(ROOT / "data" / "agentic" / "dev_test_split.json") as f:
        split = json.load(f)
    if args.paper:
        papers = [args.paper]
    elif args.dev_only:
        papers = sorted(split["dev"])
    else:
        papers = sorted(split["dev"] + split["test"])

    output_dir = ROOT / "data" / "extractions" / args.model_name
    output_dir.mkdir(parents=True, exist_ok=True)
    fail_dir = output_dir / "failures"
    fail_dir.mkdir(exist_ok=True)

    todo = [p for p in papers if not (output_dir / f"{p}.json").exists()]

    print("=" * 60)
    print(f"API Extraction: {args.provider} / {args.model}")
    print("=" * 60)
    print(f"Papers: {len(todo)} to process ({len(papers) - len(todo)} skipped)")
    print(f"Output: {output_dir}")
    print(f"Prompt hash: {_PROMPT_HASH}")
    print(f"Git commit: {_GIT_COMMIT}")
    print("=" * 60)

    def _meta_block(usage: dict) -> dict:
        return {
            "parser": "pypdf2",
            "parser_version": "3.0.1",
            "prompt_sha256_prefix": _PROMPT_HASH,
            "prompt_chars": len(SYSTEM_PROMPT),
            "model_id": args.model,
            "provider": args.provider,
            "temperature": args.temperature,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "git_commit": _GIT_COMMIT,
            "paper_set": "102_dev_test_split",
            "script": "scripts/euler/extract_api_models.py",
            "mode": "api_realtime",
        }

    ok = fail = 0
    total_in = total_out = 0
    rpm_delay = 60.0 / prov["rpm_limit"] if prov["rpm_limit"] else 0.5

    for i, ds_id in enumerate(todo, 1):
        paper_text = extract_paper_text(ds_id)
        if not paper_text:
            print(f"  [{i}/{len(todo)}] {ds_id}: SKIP (no PDF)")
            continue

        user_prompt = USER_PROMPT_TEMPLATE % paper_text
        raw_text = None
        result = None

        for attempt in range(3):
            try:
                response = client.chat.completions.create(
                    model=args.model,
                    temperature=args.temperature,
                    max_tokens=args.max_tokens,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                )
                raw_text = response.choices[0].message.content or ""
                usage = {
                    "input_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "output_tokens": response.usage.completion_tokens if response.usage else 0,
                }
                total_in += usage["input_tokens"]
                total_out += usage["output_tokens"]

                metadata = parse_json_response(raw_text)
                metadata = normalize_field_names(metadata)
                is_valid, errors = validate_extraction(metadata, ds_id)
                result = {
                    "dataset_id": ds_id,
                    "model": args.model,
                    "extraction": metadata,
                    "usage": usage,
                    "valid": is_valid,
                    "_meta": _meta_block(usage),
                }
                if not is_valid:
                    result["validation_errors"] = errors
                non_null = sum(1 for v in metadata.values() if v is not None)
                status = "OK" if is_valid else f"WARN({len(errors)})"
                print(f"  [{i}/{len(todo)}] {ds_id}: {status} {non_null}/30 "
                      f"({usage['input_tokens']}in/{usage['output_tokens']}out)")
                ok += 1
                break
            except Exception as e:
                if attempt < 2:
                    wait = [5, 15, 45][attempt]
                    print(f"  [{i}/{len(todo)}] {ds_id}: retry {attempt+1} ({str(e)[:60]})")
                    time.sleep(wait)
                else:
                    result = {
                        "dataset_id": ds_id,
                        "model": args.model,
                        "extraction": None,
                        "usage": {"input_tokens": 0, "output_tokens": 0},
                        "valid": False,
                        "error": f"{type(e).__name__}: {str(e)[:200]}",
                        "_meta": _meta_block({}),
                    }
                    if raw_text:
                        (fail_dir / f"{ds_id.replace('/', '__')}_raw.txt").write_text(raw_text)
                    print(f"  [{i}/{len(todo)}] {ds_id}: FAILED")
                    fail += 1

        with open(output_dir / f"{ds_id}.json", "w") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        time.sleep(rpm_delay)

    print(f"\n{'=' * 60}")
    print(f"DONE: {ok} OK, {fail} failed")
    print(f"Tokens: {total_in:,} in, {total_out:,} out")
    print(f"{'=' * 60}")

    with open(output_dir / "_summary.json", "w") as f:
        json.dump({
            "model": args.model,
            "provider": args.provider,
            "model_name": args.model_name,
            "papers_ok": ok,
            "papers_failed": fail,
            "total_input_tokens": total_in,
            "total_output_tokens": total_out,
            "git_commit": _GIT_COMMIT,
            "prompt_sha256_prefix": _PROMPT_HASH,
        }, f, indent=2)


if __name__ == "__main__":
    main()
