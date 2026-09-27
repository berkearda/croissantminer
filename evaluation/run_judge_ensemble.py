#!/usr/bin/env python3
"""T-021 / T-066 judge runner.

Stages:
- Stage A (judge audit): score the 200-cell audit set with all candidate
  judges (default: GPT-5.4 full + Gemini 3.1 Pro + Llama 3.3 70B). The
  audit reporter (`evaluation/audit_report.py`) then computes agreement
  metrics against the human ratings and picks the single winning judge.
- Stage B (production): score the full 22 systems x 102 papers x 20
  prose fields (~44,000 cells) with only the winner judge selected by
  Stage A.

The same script handles both: pass `--audit-set audit_set_200.parquet`
for Stage A or `--build-from-gold` for Stage B. Outputs land in
`data/audit/` for Stage A and `data/judged/` for Stage B.

N9 controls (the experiment audit protocol):
- `--plan` prints what the script would do without making any API
  calls. Use this to verify inputs, costs, and outputs before spending.
- `--smoke N` runs the judge on the first N cells only and writes
  to `_smoke/`. Use this to sanity-check judge output before scaling.
- The full run will refuse to start if there is no `_smoke/` output
  for the chosen judges in the last 24h, unless `--no-smoke-required`
  is set.

Locked configuration (decisions.md 2026-04-27 PM, revised PM2):
- 3-point rubric (1=Not correct, 2=Partially correct, 3=Correct).
- Generic anchors (no per-field rubric anchors).
- Linear cell-score mapping 1->0, 2->0.5, 3->1.0 (lock pending
  Mubashara round 3 ack; survey backs linear).
- Best-of-3 architecture with pre-registered metric suite (Spearman,
  Pearson, Cohen's quadratic-weighted kappa, Krippendorff alpha
  ordinal). T-067.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

GOLD_PARQUET = ROOT / "data" / "annotations" / "gold.parquet"
AUDIT_PARQUET = ROOT / "data" / "annotations" / "audit_set_200.parquet"
EXTRACTION_BASE = ROOT / "data" / "extractions"
AUDIT_OUT_DIR = ROOT / "data" / "audit"
PROD_OUT_DIR = ROOT / "data" / "judged"
SMOKE_TTL_HOURS = 24

# Locked judge prompt (decisions.md 2026-04-27 PM, frozen).
JUDGE_SYSTEM = (
    "You are scoring metadata extractions from ML dataset papers against "
    "a human-validated reference. Output JSON only: "
    '{"score": 1, 2, or 3, "reason": "one short sentence"}'
)

JUDGE_USER_TEMPLATE_FEWSHOT = """You will rate metadata extractions against a reference. Three
worked examples first, then your task at the bottom.

==================== EXAMPLE 1 (Score = 1, Correct) ====================
Field: rai:dataPreprocessingProtocol
Reference: Two filtering steps were conducted: (1) Removed low-quality VQAs based on Stack Exchange's voting feature - excluded visual questions with scores 0 or less for either the question or answer. (2) Excluded visual questions with multiple images (e.g., GIF) or with visual answers. Final dataset contains 64,696 VQAs after filtering and removing examples where images could not be downloaded. All images were converted to png format for consistency.
Candidate: Removed visual questions with scores 0 or less, excluded visual questions with multiple images or visual answers, removed examples where the image could not be downloaded, and converted all images to png format.
Score: 1
Reason: Captures both filtering steps and post-processing in compressed form; minor omissions (final count, voting source) are acceptable.

==================== EXAMPLE 2 (Score = 2, Partially correct) ====================
Field: rai:dataCollectionRawData
Reference: The raw data source was instructables.com, a crowdsourced collection of instructions for various tasks from cooking to car repair. Users on instructables provide images or videos detailing each step and lists of required tools. Annotators were asked to glance at instructables and pull out or be inspired to construct two component tasks.
Candidate: How-to instructions from instructables.com were used as the source/scaffold for annotation prompts.
Score: 2
Reason: Names the source correctly but omits substantial content about the crowdsourced nature, the multimedia format, and the annotator workflow.

==================== EXAMPLE 3 (Score = 3, Not correct) ====================
Field: rai:dataManipulationProtocol
Reference: Data manipulation included: (1) Text segmentation using Segmentext model to handle broken and unstructured texts with digitization artifacts; (2) OCR correction using OCRonos model based on Llama 3 8B to correct OCR errors, wrong word cuts or merges, and broken text structures; (3) License filtering to retain only permissible licenses; (4) Format filtering to remove non-informative file types; (5) Replacement of sequences of [\\r]+\\n with \\n and recalculation of line lengths.
Candidate: PII is replaced with fictitious but realistic values. Toxic content is either removed or synthetically rewritten. Wikidata items and properties are translated into simple natural language sequences.
Score: 3
Reason: Candidate describes entirely different manipulation operations (PII replacement, toxicity, Wikidata) that do not appear in the reference (text segmentation, OCR correction, license filtering).

==================== YOUR TASK ====================
Field: {field_id}
Reference (human-validated): {gold_value}
Candidate (model output): {candidate_value}

Rubric -- rate the candidate's similarity to the reference. The
reference is the authoritative answer for this paper-field cell.

1 = Correct. The candidate conveys the same meaning as the reference,
    capturing all or nearly all of the same content. Stylistic
    differences and minor omissions are acceptable.
2 = Partially correct. The candidate covers the topic and shares
    some content with the reference, but misses or distorts
    substantial parts of the meaning.
3 = Not correct. The candidate's meaning differs substantially from
    the reference, shares little content with it, contradicts it,
    or contains hallucinated information not supported by the
    reference.

Special case: if the reference is empty / NULL / "[NULL ...]" (paper
does not document this field), score 1 if the candidate is also
empty/null; score 3 if the candidate provides content (hallucination).

Return JSON only."""


JUDGE_USER_TEMPLATE = """Field: {field_id}
Reference (human-validated): {gold_value}
Candidate (model output): {candidate_value}

Rubric -- rate the candidate's similarity to the reference. The
reference is the authoritative answer for this paper-field cell.

1 = Correct. The candidate conveys the same meaning as the reference,
    capturing all or nearly all of the same content. Stylistic
    differences and minor omissions are acceptable.
2 = Partially correct. The candidate covers the topic and shares
    some content with the reference, but misses or distorts
    substantial parts of the meaning.
3 = Not correct. The candidate's meaning differs substantially from
    the reference, shares little content with it, contradicts it,
    or contains hallucinated information not supported by the
    reference.

Special case: if the reference is empty / NULL / "[NULL ...]" (paper
does not document this field), score 1 if the candidate is also
empty/null; score 3 if the candidate provides content (hallucination).

Return JSON only."""

# ── Judge configuration ────────────────────────────────────────────


@dataclass
class JudgeCfg:
    """One candidate judge's API config."""
    slug: str
    name: str
    provider: str            # anthropic, openai, google, openai_compatible
    model_id: str
    input_price_per_mtok: float
    output_price_per_mtok: float
    base_url: str | None = None
    api_key_env: str | None = None  # env var holding the key
    skip_temperature: bool = False


JUDGES: dict[str, JudgeCfg] = {
    "claude-opus-4-7": JudgeCfg(
        slug="claude_opus_4_7",
        name="Claude Opus 4.7",
        provider="anthropic",
        model_id="claude-opus-4-7",
        input_price_per_mtok=15.0,
        output_price_per_mtok=75.0,
        skip_temperature=True,
    ),
    "gpt-5.4-full": JudgeCfg(
        slug="gpt5_4_full",
        name="GPT-5.4 full",
        provider="openai",
        model_id="gpt-5.4-2026-03-05",
        input_price_per_mtok=1.25,
        output_price_per_mtok=10.0,
    ),
    "gpt-5.5": JudgeCfg(
        slug="gpt5_5",
        name="GPT-5.5",
        provider="openai",
        model_id="gpt-5.5-2026-04-23",
        input_price_per_mtok=5.0,
        output_price_per_mtok=30.0,
        skip_temperature=True,  # GPT-5.5 only supports default temperature (1)
    ),
    "llama-4-maverick": JudgeCfg(
        slug="llama_4_maverick",
        name="Llama 4 Maverick 17B-128E (DeepInfra)",
        provider="openai_compatible",
        model_id="meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8",
        base_url="https://api.deepinfra.com/v1/openai",
        api_key_env="DEEPINFRA_API_KEY",
        input_price_per_mtok=0.20,
        output_price_per_mtok=0.60,
    ),
    "deepseek-v3-2": JudgeCfg(
        slug="deepseek_v3_2",
        name="DeepSeek V3.2 (DeepInfra)",
        provider="openai_compatible",
        model_id="deepseek-ai/DeepSeek-V3.2",
        base_url="https://api.deepinfra.com/v1/openai",
        api_key_env="DEEPINFRA_API_KEY",
        input_price_per_mtok=0.27,
        output_price_per_mtok=0.40,
    ),
    "glm-5-1": JudgeCfg(
        slug="glm_5_1",
        name="GLM-5.1 (DeepInfra)",
        provider="openai_compatible",
        model_id="zai-org/GLM-5.1",
        base_url="https://api.deepinfra.com/v1/openai",
        api_key_env="DEEPINFRA_API_KEY",
        input_price_per_mtok=0.40,
        output_price_per_mtok=1.30,
    ),
    "glm-5": JudgeCfg(
        slug="glm_5",
        name="GLM-5 (DeepInfra)",
        provider="openai_compatible",
        model_id="zai-org/GLM-5",
        base_url="https://api.deepinfra.com/v1/openai",
        api_key_env="DEEPINFRA_API_KEY",
        input_price_per_mtok=0.40,
        output_price_per_mtok=1.30,
    ),
    "kimi-k2-6": JudgeCfg(
        slug="kimi_k2_6",
        name="Kimi K2.6 (Moonshot, DeepInfra)",
        provider="openai_compatible",
        model_id="moonshotai/Kimi-K2.6",
        base_url="https://api.deepinfra.com/v1/openai",
        api_key_env="DEEPINFRA_API_KEY",
        input_price_per_mtok=0.55,
        output_price_per_mtok=2.20,
    ),
    "qwen-3-5-397b": JudgeCfg(
        slug="qwen_3_5_397b",
        name="Qwen 3.5 397B-A17B (DeepInfra)",
        provider="openai_compatible",
        model_id="Qwen/Qwen3.5-397B-A17B",
        base_url="https://api.deepinfra.com/v1/openai",
        api_key_env="DEEPINFRA_API_KEY",
        input_price_per_mtok=0.50,
        output_price_per_mtok=1.50,
    ),
    "qwen-3-max": JudgeCfg(
        slug="qwen_3_max",
        name="Qwen 3 Max (DeepInfra)",
        provider="openai_compatible",
        model_id="Qwen/Qwen3-Max",
        base_url="https://api.deepinfra.com/v1/openai",
        api_key_env="DEEPINFRA_API_KEY",
        input_price_per_mtok=1.20,
        output_price_per_mtok=6.0,
    ),
    "gemini-3.1-pro": JudgeCfg(
        slug="gemini_3_1_pro",
        name="Gemini 3.1 Pro Preview",
        provider="google",
        model_id="gemini-3.1-pro-preview",
        input_price_per_mtok=2.0,
        output_price_per_mtok=12.0,
    ),
    "gemini-2.5-pro": JudgeCfg(
        slug="gemini_2_5_pro",
        name="Gemini 2.5 Pro",
        provider="google",
        model_id="gemini-2.5-pro",
        input_price_per_mtok=1.25,
        output_price_per_mtok=10.0,
    ),
    "llama-3.3-70b": JudgeCfg(
        slug="llama_3_3_70b",
        name="Llama 3.3 70B (DeepInfra)",
        provider="openai_compatible",
        model_id="meta-llama/Llama-3.3-70B-Instruct-Turbo",
        base_url="https://api.deepinfra.com/v1/openai",
        api_key_env="DEEPINFRA_API_KEY",
        input_price_per_mtok=0.40,
        output_price_per_mtok=0.40,
    ),
}

DEFAULT_STAGE_A_JUDGES = ("gpt-5.4-full", "gemini-3.1-pro", "llama-3.3-70b")


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("judge_ensemble")


# ── Provider calls ────────────────────────────────────────────────


def call_judge(cfg: JudgeCfg, system_prompt: str, user_content: str,
              max_retries: int = 3) -> tuple[str, dict]:
    """Provider-agnostic judge call. Returns (raw_text, usage_dict)."""
    backoffs = [3, 10, 30]
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            if cfg.provider == "openai" or cfg.provider == "openai_compatible":
                return _call_openai_compatible(cfg, system_prompt, user_content)
            if cfg.provider == "google":
                return _call_google(cfg, system_prompt, user_content)
            if cfg.provider == "anthropic":
                return _call_anthropic(cfg, system_prompt, user_content)
            raise ValueError(f"unknown provider {cfg.provider}")
        except Exception as exc:  # noqa: BLE001 — retry on anything transient
            last_exc = exc
            msg = str(exc).lower()
            transient = ("rate" in msg or "429" in msg or "timeout" in msg
                        or "5" in str(getattr(exc, "status_code", ""))
                        or "overloaded" in msg)
            if attempt == max_retries - 1 or not transient:
                raise
            wait = backoffs[attempt] if attempt < len(backoffs) else 60
            log.warning("  retry %d after %ds: %s", attempt + 1, wait, str(exc)[:80])
            time.sleep(wait)
    raise last_exc  # unreachable


def _call_openai_compatible(cfg: JudgeCfg, system_prompt: str,
                           user_content: str) -> tuple[str, dict]:
    from openai import OpenAI
    kwargs = {}
    if cfg.base_url:
        kwargs["base_url"] = cfg.base_url
    if cfg.api_key_env:
        kwargs["api_key"] = os.environ[cfg.api_key_env]
    client = OpenAI(**kwargs)
    params = {
        "model": cfg.model_id,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "response_format": {"type": "json_object"},
        "max_completion_tokens": 2000,
    }
    if not cfg.skip_temperature:
        params["temperature"] = 0.0
    # 180s per-call timeout: prevents hangs on reasoning models that
    # can spin indefinitely on hard cells without server-side timeout.
    resp = client.with_options(timeout=180.0).chat.completions.create(**params)
    msg = resp.choices[0].message
    raw = msg.content or ""
    # Reasoning models (GLM-5/5.1, DeepSeek-R1, others) put the answer in
    # reasoning_content when content is empty. Fall back to that.
    if not raw.strip() and hasattr(msg, "reasoning_content"):
        raw = msg.reasoning_content or ""
    elif not raw.strip():
        # Some providers expose it via model_extra / extra fields
        extra = getattr(msg, "model_extra", None) or {}
        raw = extra.get("reasoning_content") or raw
    usage = {
        "input_tokens": resp.usage.prompt_tokens,
        "output_tokens": resp.usage.completion_tokens,
    }
    return raw, usage


def _call_google(cfg: JudgeCfg, system_prompt: str,
                user_content: str) -> tuple[str, dict]:
    import requests
    api_key = os.environ["GEMINI_API_KEY"]
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
          f"{cfg.model_id}:generateContent")
    gen_config = {
        "temperature": 0.0,
        "maxOutputTokens": 2000,
        "responseMimeType": "application/json",
    }
    # thinkingLevel is only supported on Gemini 3.x; 2.5 Pro returns 400.
    # On 3.x we set "low" because we need a 1/2/3 ordinal score, not deep
    # reasoning. Default HIGH burns 21-31s on internal thoughts and
    # frequently times out (documented Gemini 3.1 Pro Preview issue,
    # April 2026).
    if cfg.model_id.startswith("gemini-3"):
        gen_config["thinkingConfig"] = {"thinkingLevel": "low"}
    payload = {
        "contents": [{"parts": [{"text": user_content}]}],
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "generationConfig": gen_config,
    }
    # 503-aware retry with exponential backoff. The 60s default timeout
    # was below Gemini 3.1 Pro Preview's normal TTFT range, causing false
    # timeouts; bumped to 180s. 503/504 errors are retried with longer
    # waits since they indicate server overload, not slow processing.
    backoffs = [5, 15, 45, 90, 180]
    last_status, last_text = None, None
    for attempt in range(6):
        try:
            resp = requests.post(url, params={"key": api_key}, json=payload, timeout=180)
            last_status, last_text = resp.status_code, resp.text
            if resp.status_code == 200:
                break
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < 5:
                wait = backoffs[attempt]
                log.warning("  Gemini %s, sleeping %ds (attempt %d/6)",
                          resp.status_code, wait, attempt + 1)
                time.sleep(wait)
                continue
            raise RuntimeError(f"Gemini API {resp.status_code}: {resp.text[:200]}")
        except requests.exceptions.RequestException as e:
            if attempt < 5:
                wait = backoffs[attempt]
                log.warning("  Gemini network error (%s), sleeping %ds (attempt %d/6)",
                          str(e)[:100], wait, attempt + 1)
                time.sleep(wait)
                continue
            raise
    else:
        raise RuntimeError(f"Gemini API exhausted retries: {last_status} {last_text[:200]}")
    data = resp.json()
    cand0 = data["candidates"][0]
    content = cand0.get("content") or {}
    parts = content.get("parts") or []
    if not parts:
        raise RuntimeError(
            f"Gemini returned no text parts (finishReason={cand0.get('finishReason')}, "
            f"usage={data.get('usageMetadata', {})})"
        )
    raw = parts[0]["text"]
    um = data.get("usageMetadata", {})
    usage = {
        "input_tokens": um.get("promptTokenCount", 0),
        "output_tokens": um.get("candidatesTokenCount", 0),
    }
    return raw, usage


def _call_anthropic(cfg: JudgeCfg, system_prompt: str,
                   user_content: str) -> tuple[str, dict]:
    import anthropic
    client = anthropic.Anthropic()
    kwargs = {
        "model": cfg.model_id,
        "max_tokens": 200,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_content}],
    }
    if not cfg.skip_temperature:
        kwargs["temperature"] = 0.0
    resp = client.messages.create(**kwargs)
    raw = "".join(b.text for b in resp.content if hasattr(b, "text"))
    usage = {
        "input_tokens": resp.usage.input_tokens,
        "output_tokens": resp.usage.output_tokens,
    }
    return raw, usage


# ── Response parsing ──────────────────────────────────────────────


def parse_judge_response(raw: str) -> tuple[int, str]:
    """Extract {score: int, reason: str} from a judge response.

    Tolerates code fences and extra prose around the JSON.
    """
    text = raw.strip()
    if "```" in text:
        # Strip code fences
        parts = text.split("```")
        for i, p in enumerate(parts):
            if "{" in p and "}" in p:
                text = p.lstrip("json\n").strip()
                break
    first = text.find("{")
    last = text.rfind("}")
    if first < 0 or last < 0:
        raise ValueError(f"no JSON object found in: {raw[:100]!r}")
    obj = json.loads(text[first:last + 1])
    score = int(obj["score"])
    if score not in (1, 2, 3):
        raise ValueError(f"score {score} not in {{1, 2, 3}} for: {raw[:100]!r}")
    reason = str(obj.get("reason", ""))[:300]
    return score, reason


# ── Task list construction ────────────────────────────────────────


def load_audit_tasks() -> pd.DataFrame:
    df = pd.read_parquet(AUDIT_PARQUET)
    log.info("loaded %d audit cells from %s", len(df), AUDIT_PARQUET.name)
    return df[["row_id", "paper_id", "field_id", "system_id",
               "gold_value", "candidate_value"]].copy()


# Agentic systems (architectures whose orchestration logic can be tuned).
# Per dev-set iteration policy locked 2026-05-01 in decisions.md, these are
# scored on DEV only (14 papers) for owner tuning feedback; test cells are
# held out until each owner declares their system frozen and pushes test
# extractions, at which point a separate scoring run produces the final
# held-out test number. Single-pass models are scored on all 102 papers —
# their prompt is locked across the family, no iteration possible.
AGENTIC_SYSTEMS = frozenset({
    "agentic_v2_sonnet_4_5", "agentic_lev_sonnet_4_5",
    "agentic_react_sonnet_4_5", "agentic_react_sonnet_4_6",
    "agentic_specialist_sonnet_4_5",
    "agentic_v2_gpt5_4_full", "agentic_v2_gemini_3_1_pro",
    "agentic_v2_llama4_scout",
    "agentic_lev_gpt5_4_full", "agentic_lev_gemini_3_1_pro",
    "agentic_lev_llama4_scout",
    # LEV mixed-backbone bake-off variants (Phase 0.5).
    "agentic_lev_gemini_3_1_pro_gpt5_4_mini",
    "agentic_lev_gemini_3_1_pro_sonnet_4_6",
    "agentic_lev_gemini_3_1_pro_gpt5_4_full",
})


def is_agentic_system(strat: str) -> bool:
    """Any system_id starting with 'agentic_' is agentic; iteration variants
    of the form '<base_system>_v2', '_v3', etc. inherit this naturally."""
    return strat in AGENTIC_SYSTEMS or strat.startswith("agentic_")


def build_production_tasks() -> pd.DataFrame:
    """Stage B: build the full task list from gold + extractions.

    For every (paper, prose field) cell with a settled gold_value, and
    for every system in our locked lineup that has a non-null
    extraction, emit one task row.

    Per-system-category filter applied:
    - Agentic systems: DEV 14 only (owner tuning feedback; test held out
      until owners freeze and push test extractions).
    - Single-pass and other systems: all 102 papers.
    """
    from evaluation.field_metrics import LONG_TEXT_RAI_FIELDS  # noqa: WPS433

    gold = pd.read_parquet(GOLD_PARQUET)
    gold = gold[gold["gold_value"].notna()].copy()
    gold = gold[gold["field_id"].isin(LONG_TEXT_RAI_FIELDS)].copy()

    # Load dev/test split for the agentic-systems-test-only filter.
    split = json.loads((ROOT / "data" / "agentic" / "dev_test_split.json").read_text())
    dev_papers = frozenset(split["dev"])

    # locked production lineup (matches score_against_gold.STRATEGY_DIRS).
    from evaluation.score_against_gold import STRATEGY_DIRS  # noqa: WPS433

    rows = []
    skipped_agentic_test = 0
    for paper, paper_rows in gold.groupby("paper_id"):
        for strat, sdir in STRATEGY_DIRS.items():
            # Skip agentic-system test cells until owners freeze. Score only
            # dev for now so owners get tuning feedback; the held-out test
            # number is produced by a separate scoring run after freeze.
            if is_agentic_system(strat) and paper not in dev_papers:
                skipped_agentic_test += 1
                continue
            ext_path = sdir / f"{paper}.json"
            if not ext_path.exists():
                ext_path = sdir / paper / "extraction.json"
            if not ext_path.exists():
                continue
            with open(ext_path) as f:
                payload = json.load(f)
            ext = payload.get("extraction", payload)
            for _, gold_row in paper_rows.iterrows():
                fid = gold_row["field_id"]
                short = fid.split(":")[-1] if ":" in fid else fid
                cand = ext.get(fid, ext.get(short))
                if cand is None or not str(cand).strip():
                    continue
                rows.append({
                    "paper_id": paper,
                    "field_id": fid,
                    "system_id": strat,
                    "gold_value": str(gold_row["gold_value"]),
                    "candidate_value": str(cand).strip(),
                })

    df = pd.DataFrame(rows)
    df.insert(0, "row_id", range(1, len(df) + 1))
    log.info("built %d production tasks across %d systems "
            "(skipped %d agentic-x-test paper-system pairs)",
            len(df), df["system_id"].nunique(), skipped_agentic_test)
    return df


# ── Pre-flight (N9) ───────────────────────────────────────────────


def estimate_cost(n_cells: int, judges: list[str]) -> dict:
    """Per-judge and total cost estimate. Uses 1000 in / 100 out token
    budget (locked in decisions.md 2026-04-27 PM cost calc)."""
    in_tok, out_tok = 1000, 100
    total = 0.0
    breakdown = {}
    for j in judges:
        cfg = JUDGES[j]
        cost = n_cells * (in_tok / 1e6 * cfg.input_price_per_mtok
                          + out_tok / 1e6 * cfg.output_price_per_mtok)
        breakdown[j] = round(cost, 4)
        total += cost
    return {"per_judge": breakdown, "total": round(total, 4)}


def check_smoke_recent(judge: str, out_dir: Path) -> bool:
    smoke_path = out_dir / "_smoke" / f"judge_scores_{JUDGES[judge].slug}.parquet"
    if not smoke_path.exists():
        return False
    age_h = (time.time() - smoke_path.stat().st_mtime) / 3600
    return age_h < SMOKE_TTL_HOURS


def print_plan(stage: str, tasks: pd.DataFrame, judges: list[str],
              out_dir: Path, smoke_n: int | None) -> bool:
    """Print N9-style plan; return True if all checks pass."""
    cost = estimate_cost(len(tasks), judges)
    in_min = (len(tasks) * len(judges)) // 30  # ~30 calls/min sequential
    print()
    print("=" * 60)
    print(f"PLAN: judge ensemble {stage}")
    print("=" * 60)
    print(f"Tasks:      {len(tasks)} cells")
    print(f"Judges:     {', '.join(judges)}")
    print(f"API calls:  {len(tasks) * len(judges)} total "
         f"({len(tasks)} per judge)")
    print(f"Cost:       ~${cost['total']:.2f} estimated")
    for j, c in cost["per_judge"].items():
        print(f"            {j:30s}  ~${c:.4f}")
    print(f"Time:       ~{in_min} min sequential, faster if parallelised")
    print(f"Output dir: {out_dir.relative_to(ROOT)}")
    print(f"Prompt:     locked in decisions.md 2026-04-27 PM")
    print()
    print("CHECKS")
    print("-" * 60)

    all_ok = True
    # 1. Tasks exist
    if len(tasks) == 0:
        print("[X] no tasks to run")
        all_ok = False
    else:
        print(f"[OK] {len(tasks)} tasks loaded")
    # 2. API keys
    needed_keys = {
        "openai": "OPENAI_API_KEY",
        "google": "GEMINI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
    }
    for j in judges:
        cfg = JUDGES[j]
        if cfg.api_key_env:
            key_name = cfg.api_key_env
        else:
            key_name = needed_keys.get(cfg.provider, "")
        present = bool(os.environ.get(key_name))
        flag = "OK" if present else "X"
        print(f"[{flag}] {key_name} {'set' if present else 'MISSING'} "
             f"(needed for {j})")
        if not present:
            all_ok = False
    # 3. Output dir writable
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[OK] {out_dir.relative_to(ROOT)} writable")
    # 4. Existing outputs (would they be overwritten?)
    for j in judges:
        out_path = out_dir / f"judge_scores_{JUDGES[j].slug}.parquet"
        if out_path.exists():
            print(f"[!] {out_path.name} exists — will append-and-overwrite duplicate "
                 "(paper_id,field_id,system_id) rows; pre-existing rows for "
                 "other tasks are preserved")
    # 5. Smoke required?
    if smoke_n is None and stage == "Stage B":
        # production run — require recent smoke
        for j in judges:
            if not check_smoke_recent(j, out_dir):
                print(f"[X] no recent smoke run for {j} in last {SMOKE_TTL_HOURS}h")
                all_ok = False
            else:
                print(f"[OK] recent smoke run for {j} found")

    print("-" * 60)
    print(f"VERDICT: {'PROCEED' if all_ok else 'HOLD'}")
    print()
    return all_ok


# ── Run loop ──────────────────────────────────────────────────────


def _score_one(cfg: JudgeCfg, task) -> dict:
    """Score a single task; return a row dict (success or FAIL)."""
    user = JUDGE_USER_TEMPLATE.format(
        field_id=task.field_id,
        gold_value=task.gold_value[:8000],
        candidate_value=task.candidate_value[:8000],
    )
    try:
        raw, usage = call_judge(cfg, JUDGE_SYSTEM, user)
        score, reason = parse_judge_response(raw)
        return {
            "paper_id": task.paper_id,
            "field_id": task.field_id,
            "system_id": task.system_id,
            "judge": cfg.slug,
            "score": score,
            "reason": reason,
            "input_tokens": usage["input_tokens"],
            "output_tokens": usage["output_tokens"],
            "scored_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "paper_id": task.paper_id,
            "field_id": task.field_id,
            "system_id": task.system_id,
            "judge": cfg.slug,
            "score": None,
            "reason": f"FAIL: {str(exc)[:200]}",
            "input_tokens": 0,
            "output_tokens": 0,
            "scored_at": datetime.now(timezone.utc).isoformat(),
        }


def run_judge(cfg: JudgeCfg, tasks: pd.DataFrame, out_path: Path,
             dry: bool = False) -> pd.DataFrame:
    """Score every task with one judge. Resumes from existing parquet
    if present (skips already-scored rows). Concurrency controlled by
    JUDGE_CONCURRENCY env var (default 30, DeepInfra account cap 200)."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    existing = pd.DataFrame()
    if out_path.exists():
        existing = pd.read_parquet(out_path)
        already = set(zip(existing["paper_id"], existing["field_id"],
                         existing["system_id"]))
        before = len(tasks)
        tasks = tasks[~tasks.apply(
            lambda r: (r["paper_id"], r["field_id"], r["system_id"])
            in already, axis=1)].copy()
        log.info("  %s: resuming, %d/%d tasks remain",
                cfg.slug, len(tasks), before)

    log.info("  %s: scoring %d tasks", cfg.slug, len(tasks))

    if dry:
        return existing

    concurrency = int(os.environ.get("JUDGE_CONCURRENCY", "30"))
    log.info("  %s: concurrency=%d", cfg.slug, concurrency)

    rows = []
    fail_count = 0
    task_list = list(tasks.itertuples(index=False))
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(_score_one, cfg, t) for t in task_list]
        for i, fut in enumerate(as_completed(futures)):
            row = fut.result()
            if row["score"] is None and str(row["reason"]).startswith("FAIL"):
                fail_count += 1
                if fail_count <= 10:
                    log.warning("  fail [%d] (%s, %s, %s): %s",
                                fail_count, row["paper_id"], row["field_id"],
                                row["system_id"], row["reason"][:120])
            rows.append(row)
            # Periodic save: every 25 completions.
            if (i + 1) % 25 == 0:
                df_so_far = pd.concat([existing, pd.DataFrame(rows)],
                                      ignore_index=True)
                df_so_far.to_parquet(out_path, index=False)
                log.info("  %s: %d/%d done, %d failed, snapshot saved",
                        cfg.slug, i + 1, len(task_list), fail_count)

    df_final = pd.concat([existing, pd.DataFrame(rows)], ignore_index=True)
    df_final.to_parquet(out_path, index=False)
    log.info("  %s: complete, %d total scored, %d failed", cfg.slug,
            len(df_final), fail_count)
    return df_final


# ── CLI ───────────────────────────────────────────────────────────


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--stage", choices=["a", "audit", "b", "production"],
                  default="audit",
                  help="Stage A (audit, default) or Stage B (production).")
    p.add_argument("--judges", default=",".join(DEFAULT_STAGE_A_JUDGES),
                  help="comma-separated. Stage A: defaults to all 3 candidates. "
                       "Stage B: pass only the winner judge.")
    p.add_argument("--audit-set", default=str(AUDIT_PARQUET),
                  help="path to audit parquet (Stage A only)")
    p.add_argument("--output-dir", default=None,
                  help="override output dir; default: data/audit/ for Stage A, "
                       "data/judged/ for Stage B")
    p.add_argument("--plan", action="store_true",
                  help="show plan + N9 checks, exit without running")
    p.add_argument("--smoke", type=int, default=None,
                  help="run on only N cells; output goes to <output-dir>/_smoke/")
    p.add_argument("--no-smoke-required", action="store_true",
                  help="skip the 'recent smoke run required' check (Stage B only)")
    p.add_argument("--systems", default=None,
                  help="comma-separated system_ids to filter task list (Stage B "
                       "only). Used by agentic-system owners during dev tuning "
                       "to re-score only their own system's cells.")
    args = p.parse_args()

    stage = "Stage A" if args.stage in ("a", "audit") else "Stage B"
    judges = [j.strip() for j in args.judges.split(",") if j.strip()]
    unknown = [j for j in judges if j not in JUDGES]
    if unknown:
        raise SystemExit(f"unknown judges: {unknown}; available: {list(JUDGES)}")

    # Build task list
    if stage == "Stage A":
        tasks = load_audit_tasks()
    else:
        tasks = build_production_tasks()

    if args.systems:
        wanted = {s.strip() for s in args.systems.split(",") if s.strip()}
        before = len(tasks)
        tasks = tasks[tasks["system_id"].isin(wanted)].copy()
        log.info("--systems filter: %d -> %d tasks (kept: %s)",
                before, len(tasks), sorted(wanted))
        if len(tasks) == 0:
            raise SystemExit(f"--systems filter matched 0 tasks; "
                             f"available system_ids in task list: "
                             f"{sorted(set(build_production_tasks()['system_id']))}")

    if args.smoke is not None:
        tasks = tasks.head(args.smoke).copy()
        log.info("SMOKE mode: %d tasks", len(tasks))

    # Output dir
    if args.output_dir:
        out_dir = Path(args.output_dir)
    else:
        out_dir = AUDIT_OUT_DIR if stage == "Stage A" else PROD_OUT_DIR
    if args.smoke is not None:
        out_dir = out_dir / "_smoke"

    # N9 plan
    print_plan(stage, tasks, judges, out_dir,
              smoke_n=args.smoke)
    if args.plan:
        return

    # Production run requires a recent smoke unless explicitly waived
    if (stage == "Stage B" and args.smoke is None
            and not args.no_smoke_required):
        for j in judges:
            if not check_smoke_recent(j, out_dir):
                raise SystemExit(
                    f"N9: no recent smoke run for {j}. Run "
                    f"`--smoke 10 --judges {j}` first, then re-run, or "
                    f"pass --no-smoke-required to override.")

    # Execute
    out_dir.mkdir(parents=True, exist_ok=True)
    for j in judges:
        cfg = JUDGES[j]
        out_path = out_dir / f"judge_scores_{cfg.slug}.parquet"
        log.info("=" * 60)
        log.info("JUDGE: %s -> %s", cfg.name, out_path.relative_to(ROOT))
        run_judge(cfg, tasks, out_path)


if __name__ == "__main__":
    main()
