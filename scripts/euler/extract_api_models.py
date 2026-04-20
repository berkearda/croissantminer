#!/usr/bin/env python3
"""
CroissantMiner — API-based Open-Source Model Extraction

Runs extraction via OpenRouter, Together AI, Groq, or DeepSeek APIs.
These are all OpenAI-compatible, so one script handles all providers.

Usage:
  # Free: OpenRouter Llama 3.3 70B
  python scripts/euler/extract_api_models.py \
      --provider openrouter \
      --model meta-llama/llama-3.3-70b-instruct:free \
      --model-name llama3_70b_openrouter

  # Free with signup credits: Together AI Qwen3 32B
  python scripts/euler/extract_api_models.py \
      --provider together \
      --model Qwen/Qwen3-32B \
      --model-name qwen3_32b_together

  # Cheap: DeepSeek V3.2
  python scripts/euler/extract_api_models.py \
      --provider deepseek \
      --model deepseek-chat \
      --model-name deepseek_v3

  # Free: Groq Llama 4 Scout
  python scripts/euler/extract_api_models.py \
      --provider groq \
      --model meta-llama/llama-4-scout-17b-16e-instruct \
      --model-name llama4_scout_groq

Environment variables needed:
  OPENROUTER_API_KEY   — get free at openrouter.ai
  TOGETHER_API_KEY     — get $25 free at together.ai
  DEEPSEEK_API_KEY     — get at deepseek.com
  GROQ_API_KEY         — get free at groq.com
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

from croissantminer.pdf.reader import extract_text_from_pdf as _canonical_extract_text
from croissantminer.pdf.processor import clean_text as _canonical_clean_text
from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).parent.parent.parent
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

from config import SYSTEM_PROMPT, METADATA_SCHEMA

ALL_FIELDS = list(METADATA_SCHEMA.keys())

PROVIDERS = {
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "key_env": "OPENROUTER_API_KEY",
        "rpm_limit": 20,   # free tier
        "rpd_limit": 200,  # free tier
    },
    "together": {
        "base_url": "https://api.together.xyz/v1",
        "key_env": "TOGETHER_API_KEY",
        "rpm_limit": 60,
        "rpd_limit": None,
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "key_env": "DEEPSEEK_API_KEY",
        "rpm_limit": 60,
        "rpd_limit": None,
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "key_env": "GROQ_API_KEY",
        "rpm_limit": 30,   # free tier
        "rpd_limit": 1000, # free tier
    },
}

USER_PROMPT_TEMPLATE = """Extract metadata from the following academic paper by matching text to the field descriptions above. Your output must conform exactly to the following schema:

SCHEMA:
{schema}

PAPER TEXT:
{paper_text}

Return ONLY valid JSON matching the schema above. Do not include any markdown formatting or explanations."""


def extract_paper_text(ds_id, max_chars=200000):
    pdf_path = ROOT / "data" / "raw" / f"{ds_id}.pdf"
    if not pdf_path.exists():
        with open(ROOT / "data" / "paper_links.json") as f:
            links = json.load(f)
        url = links.get(ds_id, "")
        m = re.search(r'(\d{4}\.\d{4,5})', url)
        if m:
            for sfx in ["", "v1", "v2", "v3", "v4", "v5"]:
                p = ROOT / "data" / "raw" / f"{m.group(1)}{sfx}.pdf"
                if p.exists():
                    pdf_path = p; break
    if not pdf_path.exists():
        return None

    text = _canonical_clean_text(_canonical_extract_text(str(pdf_path)))
    for pattern in [r'\n\s*References\s*\n', r'\n\s*REFERENCES\s*\n']:
        match = re.search(pattern, text)
        if match and match.start() > len(text) * 0.5:
            text = text[:match.start()]; break

    return text[:max_chars].strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", required=True, choices=PROVIDERS.keys())
    parser.add_argument("--model", required=True)
    parser.add_argument("--model-name", required=True, help="Short name for output dir")
    parser.add_argument("--dev-only", action="store_true")
    parser.add_argument("--paper", type=str)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=4096)
    args = parser.parse_args()

    provider = PROVIDERS[args.provider]
    api_key = os.environ.get(provider["key_env"])
    if not api_key:
        print(f"ERROR: Set {provider['key_env']} environment variable")
        sys.exit(1)

    client = OpenAI(base_url=provider["base_url"], api_key=api_key)

    # Papers
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

    # Skip done
    todo = [p for p in papers if not (output_dir / f"{p}.json").exists()]

    print(f"{'=' * 60}")
    print(f"API Extraction: {args.provider} / {args.model}")
    print(f"{'=' * 60}")
    print(f"Papers: {len(todo)} to process ({len(papers) - len(todo)} skipped)")
    print(f"Output: {output_dir}")
    print(f"{'=' * 60}")

    schema_str = json.dumps({f: "string or null" for f in ALL_FIELDS}, indent=2)
    ok = fail = 0
    total_in = total_out = 0
    rpm_delay = 60.0 / provider["rpm_limit"] if provider["rpm_limit"] else 0.5

    for i, ds_id in enumerate(todo):
        paper_text = extract_paper_text(ds_id)
        if not paper_text:
            print(f"  [{i+1}/{len(todo)}] {ds_id}: SKIP (no PDF)")
            continue

        user_prompt = USER_PROMPT_TEMPLATE.format(schema=schema_str, paper_text=paper_text)

        # Retry logic
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

                raw = response.choices[0].message.content.strip()
                if raw.startswith("```json"): raw = raw[7:]
                if raw.startswith("```"): raw = raw[3:]
                if raw.endswith("```"): raw = raw[:-3]
                first = raw.find("{"); last = raw.rfind("}")
                if first != -1 and last != -1: raw = raw[first:last+1]

                metadata = json.loads(raw)

                # Normalize nulls
                for field in ALL_FIELDS:
                    val = metadata.get(field)
                    if val is not None and isinstance(val, str) and val.strip().lower() in ("", "null", "none", "n/a"):
                        metadata[field] = None
                    metadata.setdefault(field, None)

                in_tok = response.usage.prompt_tokens if response.usage else 0
                out_tok = response.usage.completion_tokens if response.usage else 0
                total_in += in_tok; total_out += out_tok

                result = {"paper_id": ds_id, "metadata": metadata, "status": "ok",
                          "_meta": {"model": args.model, "provider": args.provider,
                                    "input_tokens": in_tok, "output_tokens": out_tok}}

                non_null = sum(1 for v in metadata.values() if v is not None)
                print(f"  [{i+1}/{len(todo)}] {ds_id}: {non_null}/30 fields")
                ok += 1
                break

            except Exception as e:
                if attempt < 2:
                    wait = [5, 15, 45][attempt]
                    print(f"  [{i+1}/{len(todo)}] {ds_id}: retry {attempt+1} ({str(e)[:40]})")
                    time.sleep(wait)
                else:
                    result = {"paper_id": ds_id, "metadata": None, "status": f"error: {str(e)[:100]}",
                              "_meta": {"model": args.model, "provider": args.provider}}
                    print(f"  [{i+1}/{len(todo)}] {ds_id}: FAILED")
                    fail += 1

        with open(output_dir / f"{ds_id}.json", "w") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        # Also save flat for evaluation
        if result.get("status") == "ok":
            with open(output_dir / f"{ds_id}_flat.json", "w") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)

        time.sleep(rpm_delay)  # rate limit

    print(f"\n{'=' * 60}")
    print(f"DONE: {ok} OK, {fail} failed")
    print(f"Tokens: {total_in:,} in, {total_out:,} out")
    print(f"{'=' * 60}")

    summary = {"model": args.model, "provider": args.provider, "model_name": args.model_name,
               "papers_ok": ok, "papers_failed": fail,
               "total_input_tokens": total_in, "total_output_tokens": total_out}
    with open(output_dir / "_summary.json", "w") as f:
        json.dump(summary, f, indent=2)


if __name__ == "__main__":
    main()
