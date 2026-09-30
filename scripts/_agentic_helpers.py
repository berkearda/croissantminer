"""Shared helpers for agentic pipelines (agentic_v2.py, agentic_lev.py).

Keeps provider abstraction, prompt hashing, _meta provenance, PDF loading,
and canonical output writing in one place so the two pipelines stay aligned
with the single-call baseline in scripts/experiments/model_comparison/.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import SYSTEM_PROMPT  # noqa: E402
from validation.validate_extraction import CANONICAL_FIELDS, validate_extraction  # noqa: E402

# ── Provenance constants (computed once at import) ─────────────────
PROMPT_HASH = hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()[:16]
try:
    GIT_COMMIT = subprocess.check_output(
        ["git", "rev-parse", "--short", "HEAD"],
        stderr=subprocess.DEVNULL,
        cwd=str(ROOT),
    ).decode().strip()
except Exception:
    GIT_COMMIT = "unknown"


# ── Backbone catalogue ─────────────────────────────────────────────
# Each entry is self-contained so the calling script only needs the key.
# `output_slug` is used to build data/extractions/agentic_{v2,lev}_<slug>/.

MODELS: dict[str, dict[str, Any]] = {
    "sonnet-4-5": {
        "name": "Claude Sonnet 4.5 (gold)",
        "model_id": "claude-sonnet-4-5-20250929",
        "provider": "anthropic",
        "output_slug": "sonnet_4_5",
        "input_price_per_mtok": 3.0,
        "output_price_per_mtok": 15.0,
    },
    "gpt-5.4": {
        "name": "GPT-5.4 full",
        "model_id": "gpt-5.4-2026-03-05",
        "provider": "openai",
        "output_slug": "gpt5_4_full",
        "max_tokens_param": "max_completion_tokens",
        "input_price_per_mtok": 1.25,
        "output_price_per_mtok": 10.0,
    },
    "gpt-5.4-mini": {
        "name": "GPT-5.4 mini",
        "model_id": "gpt-5.4-mini-2026-03-17",
        "provider": "openai",
        "output_slug": "gpt5_4_mini",
        "max_tokens_param": "max_completion_tokens",
        "input_price_per_mtok": 0.15,
        "output_price_per_mtok": 0.60,
    },
    "sonnet-4-6": {
        "name": "Claude Sonnet 4.6",
        "model_id": "claude-sonnet-4-6",
        "provider": "anthropic",
        "output_slug": "sonnet_4_6",
        "input_price_per_mtok": 3.0,
        "output_price_per_mtok": 15.0,
    },
    "gemini-3.1-pro": {
        "name": "Gemini 3.1 Pro Preview",
        "model_id": "gemini-3.1-pro-preview",
        "provider": "google",
        "output_slug": "gemini_3_1_pro",
        "input_price_per_mtok": 1.25,
        "output_price_per_mtok": 10.0,
    },
    "llama-4-scout": {
        "name": "Llama 4 Scout 17B-16E (vLLM)",
        "model_id": "meta-llama/Llama-4-Scout-17B-16E-Instruct",
        "provider": "local_vllm",
        "output_slug": "llama_4_scout",
        "base_url": os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1"),
        "api_key": os.getenv("VLLM_API_KEY", "EMPTY"),
        "input_price_per_mtok": 0.0,
        "output_price_per_mtok": 0.0,
    },
}


def resolve_backbone(key: str) -> dict[str, Any]:
    if key not in MODELS:
        raise SystemExit(
            f"Unknown backbone '{key}'. Available: {sorted(MODELS)}"
        )
    return MODELS[key]


# ── Text / JSON utilities ─────────────────────────────────────────


def sanitize_utf8(text: str) -> str:
    """Drop lone UTF-16 surrogates PyPDF2 occasionally emits."""
    return text.encode("utf-8", errors="replace").decode("utf-8")


def parse_json_response(raw_text: str) -> dict:
    text = raw_text.strip()
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0].strip()
    elif text.startswith("```"):
        text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last != -1:
        text = text[first:last + 1]
    # Strip unescaped ASCII control characters (JSON spec disallows them
    # inside strings). Models occasionally emit raw \x00-\x1f bytes,
    # which json.loads rejects. Whitelist \t, \n, \r since those are
    # valid JSON whitespace at structural positions.
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    return json.loads(text.strip())


_PREFIX_MAP = {
    "sc:name": "name", "sc:description": "description", "sc:url": "url",
    "sc:license": "license", "sc:creator": "creator", "sc:publisher": "publisher",
    "sc:datePublished": "datePublished", "sc:inLanguage": "inLanguage",
    "cr:citeAs": "citeAs", "cr:isLiveDataset": "isLiveDataset",
    "sc:citeAs": "citeAs", "sc:isLiveDataset": "isLiveDataset",
    "cr:name": "name", "cr:description": "description",
}


def normalize_field_names(metadata: dict) -> dict:
    """Strip sc:/cr: prefixes the RAI fields don't carry."""
    return {_PREFIX_MAP.get(k, k): v for k, v in metadata.items()}


def fill_canonical(metadata: dict) -> dict:
    """Ensure all 30 canonical keys exist (null where missing)."""
    for field in CANONICAL_FIELDS:
        metadata.setdefault(field, None)
    return metadata


# ── PDF loading ───────────────────────────────────────────────────


def get_paper_text(ds_id: str) -> str | None:
    """Load + clean + sanitize paper text. Mirrors extract_all_models.py."""
    from croissantminer.pdf.reader import extract_text_from_pdf as _extract
    from croissantminer.pdf.processor import clean_text as _clean

    raw_dir = ROOT / "data" / "raw"
    candidates = [
        raw_dir / f"{ds_id}.pdf",
        raw_dir / f"{ds_id.replace('_', '/')}.pdf",
    ]
    links_path = ROOT / "data" / "paper_links.json"
    if links_path.exists():
        with open(links_path) as f:
            links = json.load(f)
        match = re.search(r"(\d{4}\.\d{4,5})", links.get(ds_id, ""))
        if match:
            arxiv_id = match.group(1)
            for suffix in ("", "v1", "v2", "v3", "v4", "v5"):
                candidates.append(raw_dir / f"{arxiv_id}{suffix}.pdf")

    for path in candidates:
        if path.exists():
            return sanitize_utf8(_clean(_extract(str(path))))
    return None


def strip_references(text: str) -> str:
    """Cut off the references section (anywhere past the paper midpoint)."""
    patterns = (
        r"\n\s*References\s*\n",
        r"\n\s*REFERENCES\s*\n",
        r"\n\s*Bibliography\s*\n",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match and match.start() > len(text) * 0.5:
            return text[: match.start()]
    return text


# ── Provider-agnostic LLM call ────────────────────────────────────


def _call_anthropic(cfg, system_prompt, user_content, max_tokens):
    import anthropic

    client = anthropic.Anthropic()
    kwargs = {
        "model": cfg["model_id"],
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_content}],
    }
    if not cfg.get("skip_temperature"):
        kwargs["temperature"] = 0.0

    response = client.messages.create(**kwargs)
    raw = ""
    for block in response.content:
        if getattr(block, "type", None) == "text":
            raw += block.text
        elif hasattr(block, "text"):
            raw += block.text
    usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }
    return raw, usage


def _call_openai(cfg, system_prompt, user_content, max_tokens, base_url=None, api_key=None):
    from openai import OpenAI

    kwargs = {}
    if base_url:
        kwargs["base_url"] = base_url
    if api_key:
        kwargs["api_key"] = api_key
    client = OpenAI(**kwargs)

    params = {
        "model": cfg["model_id"],
        "temperature": 0.0,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    }
    params[cfg.get("max_tokens_param", "max_completion_tokens")] = max_tokens

    response = client.chat.completions.create(**params)
    raw = response.choices[0].message.content or ""
    usage = {
        "input_tokens": response.usage.prompt_tokens,
        "output_tokens": response.usage.completion_tokens,
    }
    return raw, usage


_OPENROUTER_MODEL_MAP = {
    "gemini-3.1-pro-preview": "google/gemini-3.1-pro-preview",
    "gemini-2.5-pro": "google/gemini-2.5-pro",
}


def _call_via_openrouter(cfg, system_prompt, user_content, max_tokens):
    """OpenAI-compatible call against OpenRouter, used to bypass Google's
    250-RPD AI-Studio cap on Gemini 3.1 Pro preview. Same model, different
    routing pool. Pricier per token but no daily request cap."""
    from openai import OpenAI

    api_key = os.environ["OPENROUTER_API_KEY"]
    model_id = _OPENROUTER_MODEL_MAP.get(cfg["model_id"], cfg["model_id"])
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
    response = client.chat.completions.create(
        model=model_id,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        temperature=0.0,
        max_tokens=max_tokens,
    )
    raw = response.choices[0].message.content or ""
    usage = {
        "input_tokens": response.usage.prompt_tokens,
        "output_tokens": response.usage.completion_tokens,
    }
    return raw, usage


def _call_google(cfg, system_prompt, user_content, max_tokens):
    import requests

    # 2026-05-28: route via OpenRouter when OPENROUTER_API_KEY is set, to
    # bypass Google AI Studio's 250 RPD cap on gemini-3.1-pro. Same model,
    # OpenAI-compatible endpoint; ~60% pricier per token than direct.
    if os.getenv("OPENROUTER_API_KEY"):
        return _call_via_openrouter(cfg, system_prompt, user_content, max_tokens)

    api_key = os.getenv("GEMINI_API_KEY")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{cfg['model_id']}:generateContent"
    gen_config = {"temperature": 0.0, "maxOutputTokens": max_tokens}
    # Gemini 3.x burns most output budget on internal reasoning before
    # emitting JSON, truncating extraction mid-field. Set thinkingLevel
    # to "low" so the budget goes to the actual JSON. Gemini 2.5 (and
    # earlier) reject thinkingLevel, so apply only to 3.x.
    if cfg.get("model_id", "").startswith("gemini-3"):
        gen_config["thinkingConfig"] = {"thinkingLevel": "low"}
    payload = {
        "contents": [{"parts": [{"text": user_content}]}],
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "generationConfig": gen_config,
    }
    resp = requests.post(url, params={"key": api_key}, json=payload, timeout=180)
    if resp.status_code != 200:
        raise RuntimeError(f"Gemini API error {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    try:
        raw = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raise RuntimeError(f"Unexpected Gemini response: {json.dumps(data)[:300]}")
    usage_meta = data.get("usageMetadata", {})
    usage = {
        "input_tokens": usage_meta.get("promptTokenCount", 0),
        "output_tokens": usage_meta.get("candidatesTokenCount", 0),
    }
    return raw, usage


def call_llm(
    cfg: dict,
    system_prompt: str,
    user_content: str,
    max_tokens: int = 8192,
    retries: int = 3,
) -> tuple[str, dict]:
    """Provider-agnostic call with retry on rate limits / 5xx.

    Returns (raw_text, usage). Parsing is left to the caller so each phase
    can handle its own schema.
    """
    provider = cfg["provider"]
    backoffs = [5, 15, 45]
    last_exc: Exception | None = None

    for attempt in range(retries):
        try:
            if provider == "anthropic":
                return _call_anthropic(cfg, system_prompt, user_content, max_tokens)
            if provider == "openai":
                return _call_openai(cfg, system_prompt, user_content, max_tokens)
            if provider == "google":
                return _call_google(cfg, system_prompt, user_content, max_tokens)
            if provider == "local_vllm":
                return _call_openai(
                    cfg, system_prompt, user_content, max_tokens,
                    base_url=cfg.get("base_url"),
                    api_key=cfg.get("api_key") or "EMPTY",
                )
            raise ValueError(f"Unknown provider: {provider}")
        except Exception as exc:  # noqa: BLE001 — retry on anything transient
            last_exc = exc
            msg = str(exc).lower()
            retryable = (
                "rate" in msg or "429" in msg or "timeout" in msg
                or str(getattr(exc, "status_code", "")).startswith("5") or "overloaded" in msg
            )
            if attempt == retries - 1 or not retryable:
                raise
            wait = backoffs[attempt] if attempt < len(backoffs) else 60
            time.sleep(wait)

    raise last_exc  # unreachable but keeps type-checkers quiet


def estimate_cost(cfg: dict, usage: dict, batch_discount: bool = False) -> float:
    mult = 0.5 if batch_discount else 1.0
    inp = usage.get("input_tokens", 0) / 1e6 * cfg["input_price_per_mtok"] * mult
    out = usage.get("output_tokens", 0) / 1e6 * cfg["output_price_per_mtok"] * mult
    return round(inp + out, 4)


# ── Canonical output ──────────────────────────────────────────────


def meta_block(
    cfg: dict,
    script: str,
    mode: str,
    paper_set: str = "102_dev_test_split",
    extra: dict | None = None,
) -> dict:
    block = {
        "parser": "pypdf2",
        "parser_version": "3.0.1",
        "prompt_sha256_prefix": PROMPT_HASH,
        "prompt_chars": len(SYSTEM_PROMPT),
        "model_id": cfg["model_id"],
        "provider": cfg["provider"],
        "temperature": None if cfg.get("skip_temperature") else 0.0,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "git_commit": GIT_COMMIT,
        "paper_set": paper_set,
        "script": script,
        "mode": mode,
    }
    if extra:
        block.update(extra)
    return block


def write_canonical_output(
    out_dir: Path,
    ds_id: str,
    extraction: dict,
    usage: dict,
    cfg: dict,
    meta: dict,
) -> Path:
    """Write one paper's extraction in the canonical {dataset_id, model,
    extraction, usage, valid, _meta} schema. Returns the output path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_id = ds_id.replace("/", "__")
    path = out_dir / f"{safe_id}.json"

    extraction = normalize_field_names(extraction)
    extraction = fill_canonical(extraction)
    is_valid, errors = validate_extraction(extraction, ds_id)

    payload = {
        "dataset_id": ds_id,
        "model": cfg["model_id"],
        "extraction": extraction,
        "usage": usage,
        "valid": is_valid,
        "_meta": meta,
    }
    if not is_valid:
        payload["validation_errors"] = errors

    with open(path, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return path


def output_dir_for(pipeline: str, backbone_key: str) -> Path:
    """Canonical output directory per pipeline/backbone pair."""
    cfg = resolve_backbone(backbone_key)
    return ROOT / "data" / "extractions" / f"agentic_{pipeline}_{cfg['output_slug']}"
