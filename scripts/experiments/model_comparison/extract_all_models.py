#!/usr/bin/env python3
"""
Multi-model extraction on 103 gold papers.
Uses the SAME prompt as the gold Claude Sonnet 4.5 pipeline.

Models: GPT-5.4 Mini, Gemini 2.5 Flash, Gemini 3.1 Pro Preview
Usage:
  python scripts/experiments/model_comparison/extract_all_models.py --test        # 3 papers
  python scripts/experiments/model_comparison/extract_all_models.py --model gpt   # GPT only, all 103
  python scripts/experiments/model_comparison/extract_all_models.py --model gemini-flash
  python scripts/experiments/model_comparison/extract_all_models.py --model gemini-pro
  python scripts/experiments/model_comparison/extract_all_models.py               # all 3 models, all 103
"""

import argparse
import json
import logging
import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent.parent.parent
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

from config import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from validation.validate_extraction import validate_extraction

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("model_comparison")

PROCESSED = ROOT / "data" / "processed"
EXTRACTIONS = ROOT / "data" / "extractions"

# ── Model configurations ──
MODELS = {
    "gpt": {
        "name": "GPT-5.4 Mini",
        "model_id": "gpt-5.4-mini",
        "provider": "openai",
        "output_dir": "gpt5.4_mini",
        "max_tokens_param": "max_completion_tokens",  # GPT-5.x uses this
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

# 3 test papers (diverse domains)
TEST_PAPERS = ["AI4Math_MathVista", "openai_gsm8k", "rajpurkar_squad"]


def parse_json_response(text):
    """Parse JSON from LLM response, handling markdown fences."""
    text = text.strip()
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0].strip()
    return json.loads(text)


def normalize_field_names(metadata):
    """Strip sc:/cr: prefixes to match canonical field names."""
    PREFIX_MAP = {
        "sc:name": "name", "sc:description": "description", "sc:url": "url",
        "sc:license": "license", "sc:creator": "creator", "sc:publisher": "publisher",
        "sc:datePublished": "datePublished", "sc:inLanguage": "inLanguage",
        "cr:citeAs": "citeAs", "cr:isLiveDataset": "isLiveDataset",
        "sc:citeAs": "citeAs", "sc:isLiveDataset": "isLiveDataset",
        "cr:name": "name", "cr:description": "description",
    }
    return {PREFIX_MAP.get(k, k): v for k, v in metadata.items()}


def get_paper_text(ds_id):
    """Load paper text from processed data."""
    ext_path = PROCESSED / ds_id / "full_pdf_metadata_result.json"
    # We need the paper TEXT, not the extraction. Check if we stored it.
    # The gold pipeline read PDFs from data/raw/ via PyMuPDF.
    # For model comparison, let's reconstruct from the PDF.
    from croissantminer.pdf.reader import extract_text_from_pdf as _canonical_extract_text
    from croissantminer.pdf.processor import clean_text as _canonical_clean_text
    # Try multiple PDF naming patterns
    raw_dir = ROOT / "data" / "raw"
    pdf_candidates = [
        raw_dir / f"{ds_id}.pdf",
        raw_dir / f"{ds_id.replace('_', '/')}.pdf",
    ]
    # Also check paper_links for arxiv ID
    paper_links_path = ROOT / "data" / "paper_links.json"
    if paper_links_path.exists():
        with open(paper_links_path) as f:
            paper_links = json.load(f)
        url = paper_links.get(ds_id, "")
        m = re.search(r'(\d{4}\.\d{4,5})', url)
        if m:
            arxiv_id = m.group(1)
            for suffix in ["", "v1", "v2", "v3", "v4", "v5"]:
                pdf_candidates.append(raw_dir / f"{arxiv_id}{suffix}.pdf")

    for pdf_path in pdf_candidates:
        if pdf_path.exists():
            text = _canonical_clean_text(_canonical_extract_text(str(pdf_path)))
            return "\n".join(pages)

    return None


def call_openai(model_id, system_prompt, user_prompt, max_tokens_param="max_completion_tokens"):
    """Call OpenAI API."""
    from openai import OpenAI
    client = OpenAI()

    params = {
        "model": model_id,
        "temperature": 0.0,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    params[max_tokens_param] = 4096

    response = client.chat.completions.create(**params)
    text = response.choices[0].message.content
    usage = {
        "input_tokens": response.usage.prompt_tokens,
        "output_tokens": response.usage.completion_tokens,
    }
    return text, usage


def call_google(model_id, system_prompt, user_prompt):
    """Call Google Gemini API via REST (compatible with all Python versions)."""
    import requests

    api_key = os.getenv("GEMINI_API_KEY")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent"

    payload = {
        "contents": [{"parts": [{"text": user_prompt}]}],
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "generationConfig": {
            "temperature": 0.0,
            "maxOutputTokens": 8192,
        },
    }

    resp = requests.post(
        url, params={"key": api_key},
        json=payload, timeout=120,
    )

    if resp.status_code != 200:
        raise Exception(f"Gemini API error {resp.status_code}: {resp.text[:300]}")

    data = resp.json()

    # Extract text
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raise Exception(f"Unexpected Gemini response structure: {json.dumps(data)[:300]}")

    # Extract usage
    usage_meta = data.get("usageMetadata", {})
    usage = {
        "input_tokens": usage_meta.get("promptTokenCount", 0),
        "output_tokens": usage_meta.get("candidatesTokenCount", 0),
    }
    return text, usage


def extract_one(model_key, ds_id, paper_text):
    """Extract metadata for one paper with one model."""
    cfg = MODELS[model_key]
    user_prompt = USER_PROMPT_TEMPLATE % paper_text

    if cfg["provider"] == "openai":
        raw, usage = call_openai(
            cfg["model_id"], SYSTEM_PROMPT, user_prompt,
            cfg.get("max_tokens_param", "max_completion_tokens"),
        )
    elif cfg["provider"] == "google":
        raw, usage = call_google(cfg["model_id"], SYSTEM_PROMPT, user_prompt)
    else:
        raise ValueError(f"Unknown provider: {cfg['provider']}")

    metadata = parse_json_response(raw)
    metadata = normalize_field_names(metadata)

    # Ensure all 30 fields present
    from validation.validate_extraction import CANONICAL_FIELDS
    for field in CANONICAL_FIELDS:
        metadata.setdefault(field, None)

    return metadata, usage, raw


def run_model(model_key, ds_ids, test_mode=False):
    """Run extraction for a single model across all papers."""
    cfg = MODELS[model_key]
    out_dir = EXTRACTIONS / cfg["output_dir"]
    fail_dir = out_dir / "failures"
    out_dir.mkdir(parents=True, exist_ok=True)
    fail_dir.mkdir(parents=True, exist_ok=True)

    log.info(f"\n{'='*70}")
    log.info(f"Running {cfg['name']} ({cfg['model_id']}) on {len(ds_ids)} papers")
    log.info(f"Output: {out_dir}")
    log.info(f"{'='*70}")

    results = []
    total_input = 0
    total_output = 0
    successes = 0
    failures = 0

    for i, ds_id in enumerate(ds_ids):
        safe_id = ds_id.replace("/", "__")
        out_path = out_dir / f"{safe_id}.json"

        # Skip if already extracted
        if out_path.exists() and not test_mode:
            log.info(f"  [{i+1}/{len(ds_ids)}] {ds_id} — SKIP (exists)")
            with open(out_path) as f:
                d = json.load(f)
            results.append({"ds_id": ds_id, "status": "skip", "usage": d.get("usage", {})})
            successes += 1
            continue

        paper_text = get_paper_text(ds_id)
        if paper_text is None:
            log.warning(f"  [{i+1}/{len(ds_ids)}] {ds_id} — SKIP (no PDF)")
            results.append({"ds_id": ds_id, "status": "no_pdf"})
            failures += 1
            continue

        t0 = time.time()
        for attempt in range(2):
            try:
                metadata, usage, raw = extract_one(model_key, ds_id, paper_text)

                is_valid, errors = validate_extraction(metadata, ds_id)
                elapsed = time.time() - t0

                total_input += usage.get("input_tokens", 0)
                total_output += usage.get("output_tokens", 0)

                # Save
                output = {
                    "dataset_id": ds_id,
                    "model": cfg["model_id"],
                    "extraction": metadata,
                    "usage": usage,
                    "time_seconds": round(elapsed, 1),
                    "valid": is_valid,
                }
                if not is_valid:
                    output["validation_errors"] = errors

                with open(out_path, "w") as f:
                    json.dump(output, f, indent=2, ensure_ascii=False)

                status = "OK" if is_valid else f"WARN({len(errors)} issues)"
                log.info(f"  [{i+1}/{len(ds_ids)}] {ds_id} — {status} ({elapsed:.1f}s, {usage.get('input_tokens',0)}in/{usage.get('output_tokens',0)}out)")
                results.append({"ds_id": ds_id, "status": "ok", "usage": usage, "time": elapsed, "valid": is_valid})
                successes += 1
                break

            except Exception as e:
                if attempt == 0:
                    wait = 15 if "503" in str(e) or "429" in str(e) else 5
                    log.warning(f"  [{i+1}/{len(ds_ids)}] {ds_id} — RETRY in {wait}s ({str(e)[:80]})")
                    time.sleep(wait)
                else:
                    elapsed = time.time() - t0
                    log.error(f"  [{i+1}/{len(ds_ids)}] {ds_id} — FAIL ({e})")
                    # Save raw response if available
                    try:
                        fail_path = fail_dir / f"{safe_id}_raw.txt"
                        fail_path.write_text(str(e))
                    except:
                        pass
                    results.append({"ds_id": ds_id, "status": "fail", "error": str(e)[:200]})
                    failures += 1

        # Small delay to avoid rate limits
        time.sleep(0.5)

    # Summary
    log.info(f"\n{'─'*70}")
    log.info(f"{cfg['name']} SUMMARY")
    log.info(f"{'─'*70}")
    log.info(f"  Papers:   {len(ds_ids)}")
    log.info(f"  Success:  {successes}")
    log.info(f"  Failures: {failures}")
    log.info(f"  Tokens:   {total_input:,} in, {total_output:,} out")

    # Save log
    extraction_log = {
        "model": cfg["model_id"],
        "model_name": cfg["name"],
        "total_papers": len(ds_ids),
        "successes": successes,
        "failures": failures,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "results": results,
    }
    log_path = out_dir / "extraction_log.json"
    with open(log_path, "w") as f:
        json.dump(extraction_log, f, indent=2)
    log.info(f"  Log saved: {log_path}")

    return extraction_log


def print_comparison(ds_ids, model_keys):
    """Print side-by-side comparison for test papers."""
    print(f"\n{'='*120}")
    print("SIDE-BY-SIDE COMPARISON")
    print(f"{'='*120}")

    for ds_id in ds_ids:
        print(f"\n--- {ds_id} ---")

        # Load Claude baseline
        claude_path = PROCESSED / ds_id / "full_pdf_metadata_result.json"
        if claude_path.exists():
            with open(claude_path) as f:
                claude = json.load(f)
        else:
            claude = {}

        # Load other models
        model_data = {"Claude": claude}
        for mk in model_keys:
            cfg = MODELS[mk]
            p = EXTRACTIONS / cfg["output_dir"] / f"{ds_id}.json"
            if p.exists():
                with open(p) as f:
                    d = json.load(f)
                model_data[cfg["name"]] = d.get("extraction", {})
            else:
                model_data[cfg["name"]] = {}

        # Print table
        headers = list(model_data.keys())
        print(f"  {'Field':<30} " + " ".join(f"{h:<25}" for h in headers))
        print("  " + "-" * (30 + 26 * len(headers)))

        from validation.validate_extraction import CANONICAL_FIELDS
        for field in sorted(CANONICAL_FIELDS):
            vals = []
            for h in headers:
                v = model_data[h].get(field)
                if v is None:
                    vals.append("null")
                else:
                    s = str(v)[:22]
                    vals.append(s)
            print(f"  {field:<30} " + " ".join(f"{v:<25}" for v in vals))


def verify_all(model_keys):
    """Final verification: check all 4 models produced valid 30-field JSONs."""
    print(f"\n{'='*70}")
    print("FINAL VERIFICATION")
    print(f"{'='*70}")

    from validation.validate_extraction import CANONICAL_FIELDS

    all_ds_ids = sorted(
        p.parent.name for p in PROCESSED.glob("*/full_pdf_metadata_result.json")
    )

    all_valid = 0
    issues = []

    for ds_id in all_ds_ids:
        model_status = {}

        # Claude
        claude_path = PROCESSED / ds_id / "full_pdf_metadata_result.json"
        if claude_path.exists():
            with open(claude_path) as f:
                d = json.load(f)
            ok, _ = validate_extraction(d, ds_id)
            model_status["Claude"] = ok
        else:
            model_status["Claude"] = False

        # Other models
        for mk in model_keys:
            cfg = MODELS[mk]
            p = EXTRACTIONS / cfg["output_dir"] / f"{ds_id}.json"
            if p.exists():
                with open(p) as f:
                    d = json.load(f)
                ok, _ = validate_extraction(d.get("extraction", {}), ds_id)
                model_status[cfg["name"]] = ok
            else:
                model_status[cfg["name"]] = False

        if all(model_status.values()):
            all_valid += 1
        else:
            failed = [m for m, ok in model_status.items() if not ok]
            issues.append((ds_id, failed))

    print(f"\n  {all_valid}/{len(all_ds_ids)} papers have valid extractions from all models")
    if issues:
        print(f"\n  Issues ({len(issues)} papers):")
        for ds_id, failed in issues[:10]:
            print(f"    {ds_id}: missing/invalid from {failed}")


def main():
    parser = argparse.ArgumentParser(description="Multi-model extraction")
    parser.add_argument("--test", action="store_true", help="Test on 3 papers only")
    parser.add_argument("--model", choices=list(MODELS.keys()) + ["all"], default="all",
                        help="Which model to run (default: all)")
    parser.add_argument("--verify", action="store_true", help="Run verification only")
    args = parser.parse_args()

    # Get all gold paper IDs
    all_ds_ids = sorted(
        p.parent.name for p in PROCESSED.glob("*/full_pdf_metadata_result.json")
    )
    log.info(f"Gold papers available: {len(all_ds_ids)}")

    ds_ids = TEST_PAPERS if args.test else all_ds_ids
    model_keys = list(MODELS.keys()) if args.model == "all" else [args.model]

    if args.verify:
        verify_all(model_keys)
        return

    # Run extraction
    for mk in model_keys:
        run_model(mk, ds_ids, test_mode=args.test)

    # Print comparison for test mode
    if args.test:
        print_comparison(ds_ids, model_keys)

    # Final verification
    if not args.test:
        verify_all(model_keys)


if __name__ == "__main__":
    main()
