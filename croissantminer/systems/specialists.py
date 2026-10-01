"""Multi-agent specialist agents — refactored from Paul's `feat/multi-agents-paul`.

Phase 0 implementation fixes (2026-05-02 audit, decisions.md AM2):
  1. --backbone CLI flag (was hardcoded Sonnet 4.5 = gold-seed)
  2. --config flag for per-specialist backbone routing (econ/mixed/premium)
  3. --prompt-variant flag (v1=round-0, v2=Fix A, v3=Fix C, v4=A+C, ...)
  4. extract_json: prefer first balanced {...} (was greedy r'\\{.*\\}')
  5. Retry once on JSON parse failure with schema reminder
  6. MAX_TOKENS_GROUP 4096 → 8192
  7. Verify+correct phase (variants v3+)
  8. Output uses 'extraction' key (was 'metadata') — see pipeline.py
  9. Imports work from project root (sys.path adjusted)

Paul's prompts.py is left UNTOUCHED — variants v2-v5 wrap his prompts via
prefix/post-hoc logic, do not replace his work.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[2]   # the repository root

from .helpers import resolve_backbone, call_llm  # noqa: E402

# Paul's prompts (unchanged)
from .specialist_prompts import (  # noqa: E402
    AGENT1_PROMPT, AGENT2_PROMPT, AGENT3_PROMPT,
    AGENT4_PROMPT, AGENT5_PROMPT,
)


TEMPERATURE = 0
SPECIALIST_MAX_TOKENS = 8192          # fix 6: was 4096
COORDINATOR_MAX_TOKENS = 2048


AGENT_FIELDS: Dict[str, List[str]] = {
    "core": [
        "name", "description", "url", "license", "creator", "publisher",
        "datePublished", "inLanguage", "citeAs", "isLiveDataset",
    ],
    "collection": [
        "rai:dataCollection",
        "rai:dataCollectionType",
        "rai:dataCollectionMissingData",
        "rai:dataCollectionRawData",
        "rai:dataCollectionTimeframe",
    ],
    "annotation": [
        "rai:dataAnnotationProtocol",
        "rai:dataAnnotationPlatform",
        "rai:dataAnnotationAnalysis",
        "rai:annotationsPerItem",
        "rai:annotatorDemographics",
        "rai:machineAnnotationTools",
    ],
    "impact": [
        "rai:dataBiases",
        "rai:dataLimitations",
        "rai:dataSocialImpact",
        "rai:personalSensitiveInformation",
        "rai:dataUseCases",
        "rai:dataReleaseMaintenancePlan",
    ],
    "processing": [
        "rai:dataImputationProtocol",
        "rai:dataManipulationProtocol",
        "rai:dataPreprocessingProtocol",
    ],
}

ALL_FIELDS: List[str] = [field for group in AGENT_FIELDS.values() for field in group]
NULL_VALUES = {"null", "none", "n/a", "na", ""}


# Per-config backbone routing for the 5 specialists.
BACKBONE_CONFIGS: Dict[str, Dict[str, str]] = {
    "econ":    {"core": "gpt-5.4-mini", "collection": "gpt-5.4-mini",
                "annotation": "gpt-5.4-mini", "impact": "gpt-5.4-mini",
                "processing": "gpt-5.4-mini"},
    "mixed":   {"core": "gpt-5.4-mini", "collection": "sonnet-4-6",
                "annotation": "sonnet-4-6", "impact": "sonnet-4-6",
                "processing": "gpt-5.4-mini"},
    "premium": {"core": "sonnet-4-6", "collection": "sonnet-4-6",
                "annotation": "sonnet-4-6", "impact": "sonnet-4-6",
                "processing": "sonnet-4-6"},
    # 2026-05-22: uniform multi-backbone configs for cross-backbone comparison
    "gpt5_4_full": {"core": "gpt-5.4", "collection": "gpt-5.4",
                    "annotation": "gpt-5.4", "impact": "gpt-5.4",
                    "processing": "gpt-5.4"},
    "gemini_3_1_pro": {"core": "gemini-3.1-pro", "collection": "gemini-3.1-pro",
                       "annotation": "gemini-3.1-pro", "impact": "gemini-3.1-pro",
                       "processing": "gemini-3.1-pro"},
}


def normalize_nulls(obj: dict) -> dict:
    cleaned = {}
    for k, v in obj.items():
        if isinstance(v, str) and v.strip().lower() in NULL_VALUES:
            cleaned[k] = None
        else:
            cleaned[k] = v
    return cleaned


def extract_json(text: str) -> dict:
    """Fix 4: prefer FIRST balanced {...}, not greedy match."""
    text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    depth = 0
    start = -1
    for i, c in enumerate(text):
        if c == "{":
            if depth == 0:
                start = i
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                candidate = text[start:i + 1]
                try:
                    return json.loads(candidate)
                except Exception:
                    start = -1  # try next
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in response:\n{text[:300]}")
    return json.loads(match.group())


def null_dict(fields: list[str]) -> dict:
    return {f: None for f in fields}


# Anti-null-bias prefix (Fix A from V2 iteration). Variants v2, v4.
ANTI_NULL_PREFIX = """\
CRITICAL — DEFAULT TO NULL WHEN UNCERTAIN.

Many Croissant fields are rarely documented in dataset papers. If the paper
does NOT explicitly discuss a field you own, return null. Do not generate
plausible-sounding content. Do not infer from related content. Every non-null
extraction must be traceable to a sentence in the paper.

EXAMPLE — paper does NOT discuss the field:
  Paper: "We crowdsourced 10K questions and verified accuracy..."
  Field: rai:dataAnnotationPlatform
  CORRECT: null
  WRONG: "Amazon Mechanical Turk" (paper says "crowdsourced", never names MTurk)

EXAMPLE — paper DOES discuss the field:
  Paper: "Annotations were collected via Amazon Mechanical Turk with 3 workers per item."
  Field: rai:dataAnnotationPlatform
  CORRECT: "Amazon Mechanical Turk"

Now apply your specialist prompt below to the paper, applying these rules.
============================================================

"""


def build_specialist_prompt(base_prompt: str, prompt_variant: str) -> str:
    """v2/v4 prepend anti-null-bias to Paul's specialist prompt."""
    if prompt_variant in ("v2", "v4"):
        return ANTI_NULL_PREFIX + base_prompt
    return base_prompt


VERIFY_CORRECT_USER_TEMPLATE = """\
You previously extracted some fields from this paper but returned NULL for these:
{null_fields}

Re-read the paper text below and decide for each null field:
  - If the paper TRULY does not discuss the field, keep it null. Do NOT hallucinate.
  - If the paper DOES contain relevant content you missed, extract it now.

Return JSON: {{"<field_id>": "value or null", ...}}
ONLY include the fields listed above. JSON only.

PAPER TEXT:
{paper_text}"""


class SpecialistAgent:
    """Calls the API with a specialist system prompt and parses JSON.

    Wraps Paul's prompt content via build_specialist_prompt() (variants v2/v4)
    and adds verify+correct phase via verify_correct() (variants v3/v4/v5).
    """

    def __init__(
        self,
        name: str,
        base_prompt: str,
        assigned_fields: list[str],
        backbone_key: str,
        prompt_variant: str = "v1",
        max_tokens: int = SPECIALIST_MAX_TOKENS,
    ):
        self.name = name
        self.base_prompt = base_prompt
        self.assigned_fields = assigned_fields
        self.backbone_key = backbone_key
        self.cfg = dict(resolve_backbone(backbone_key))
        self.cfg["backbone_key"] = backbone_key
        self.prompt_variant = prompt_variant
        self.max_tokens = max_tokens

    def run(self, paper_text: str) -> tuple[dict, dict]:
        system_prompt = build_specialist_prompt(self.base_prompt, self.prompt_variant)
        user_message = f"BEGIN PAPER TEXT {paper_text} END PAPER TEXT"
        usage = {"input_tokens": 0, "output_tokens": 0}

        try:
            raw_text, u = call_llm(self.cfg, system_prompt, user_message, self.max_tokens)
            usage["input_tokens"] += u["input_tokens"]
            usage["output_tokens"] += u["output_tokens"]
        except Exception as e:
            print(f" [{self.name}] API call FAILED: {e}. Using null fallback.")
            return null_dict(self.assigned_fields), usage

        # Fix 5: app-level retry on JSON parse failure
        try:
            data = extract_json(raw_text)
        except Exception:
            retry_user = (
                f"Your previous response was not valid JSON. Return ONLY a "
                f"valid JSON object with these exact keys: "
                f"{', '.join(self.assigned_fields)}. Each value should be a "
                f"string or null.\n\n{user_message}"
            )
            try:
                raw2, u2 = call_llm(self.cfg, system_prompt, retry_user, self.max_tokens)
                usage["input_tokens"] += u2["input_tokens"]
                usage["output_tokens"] += u2["output_tokens"]
                data = extract_json(raw2)
            except Exception as e:
                print(f" [{self.name}] JSON parse failed twice: {e}. Null fallback.")
                return null_dict(self.assigned_fields), usage

        data = normalize_nulls(data)
        for f in self.assigned_fields:
            data.setdefault(f, None)
        data = {k: v for k, v in data.items() if k in self.assigned_fields}
        return data, usage

    def verify_correct(
        self, paper_text: str, current_extraction: dict
    ) -> tuple[dict, dict]:
        """Fix 7: variants v3/v4/v5 re-prompt for any null fields."""
        if self.prompt_variant not in ("v3", "v4", "v5"):
            return current_extraction, {"input_tokens": 0, "output_tokens": 0}
        nulls = [
            f for f in self.assigned_fields
            if current_extraction.get(f) is None or
               (isinstance(current_extraction.get(f), str) and
                not current_extraction[f].strip())
        ]
        if not nulls:
            return current_extraction, {"input_tokens": 0, "output_tokens": 0}
        user = VERIFY_CORRECT_USER_TEMPLATE.format(
            null_fields="\n".join(f"  - {f}" for f in nulls),
            paper_text=paper_text[:50000],
        )
        try:
            raw, usage = call_llm(self.cfg, self.base_prompt, user, self.max_tokens)
            parsed = extract_json(raw)
            parsed = normalize_nulls(parsed)
            for f in nulls:
                v = parsed.get(f)
                if v is not None and isinstance(v, str) and v.strip():
                    current_extraction[f] = v
            return current_extraction, usage
        except Exception:
            return current_extraction, {"input_tokens": 0, "output_tokens": 0}


def build_specialists(config: str, prompt_variant: str) -> list[SpecialistAgent]:
    if config not in BACKBONE_CONFIGS:
        raise ValueError(f"unknown config '{config}'. choices: {list(BACKBONE_CONFIGS)}")
    cfg_map = BACKBONE_CONFIGS[config]
    return [
        SpecialistAgent("core",        AGENT1_PROMPT, AGENT_FIELDS["core"],
                        cfg_map["core"], prompt_variant),
        SpecialistAgent("collection",  AGENT2_PROMPT, AGENT_FIELDS["collection"],
                        cfg_map["collection"], prompt_variant),
        SpecialistAgent("annotation",  AGENT3_PROMPT, AGENT_FIELDS["annotation"],
                        cfg_map["annotation"], prompt_variant),
        SpecialistAgent("impact",      AGENT4_PROMPT, AGENT_FIELDS["impact"],
                        cfg_map["impact"], prompt_variant),
        SpecialistAgent("processing",  AGENT5_PROMPT, AGENT_FIELDS["processing"],
                        cfg_map["processing"], prompt_variant),
    ]


def simple_merge(specialist_outputs: dict[str, dict]) -> dict:
    """Disjoint-fields merge. Paul's USE_SIMPLE_COORDINATOR=True default."""
    merged: dict = {}
    for fields in specialist_outputs.values():
        merged.update(fields)
    return merged
