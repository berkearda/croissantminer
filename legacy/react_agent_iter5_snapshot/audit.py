"""Post-extraction LLM audit pass.

For each non-null field with a stored evidence_quote, make a single LLM call
that sees ONLY (field, value, evidence_quote) and decides keep-or-null. This
is the explicit value-vs-evidence comparison step — separate from the agent's
own context, so it can't be biased by the rest of the conversation.

Cheap by design: uses Haiku, ~22 calls per paper at ~500 input + 50 output
tokens each ≈ $0.05/paper.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import anthropic

from .schemas import FIELD_DEFINITIONS, RAI_FIELDS

AUDIT_MODEL_ID = "claude-sonnet-4-6"
AUDIT_PRICE_INPUT_PER_MTOK = 3.00
AUDIT_PRICE_OUTPUT_PER_MTOK = 15.00


AUDIT_SYSTEM = (
    "You are an extraction auditor. You will be given (field, field_definition, "
    "extracted_value, evidence_quote). The evidence_quote is a SHORT excerpt of the "
    "paper (1-3 sentences) — it will not contain every detail in the value, because "
    "the value typically summarizes multiple paragraphs. Be permissive.\n\n"
    "KEEP the value if any of:\n"
    "- The evidence quote is on the SAME topic the field asks for, AND the value is a "
    "  reasonable summary or paraphrase consistent with the quote\n"
    "- The value generalizes or synthesizes from the quote in a natural way\n"
    "- The value's claims are plausibly drawn from the same paper context as the quote\n\n"
    "NULL the value ONLY if any of:\n"
    "- The evidence quote is OFF-TOPIC — it discusses something completely different from "
    "  what the field asks for (e.g., quote is about model architecture but field is about dataset bias)\n"
    "- The evidence quote describes a model/training/evaluation procedure rather than "
    "  the DATASET ITSELF, and the value is making dataset claims (Guardrail A violation)\n"
    "- The value's main factual claim DIRECTLY CONTRADICTS the evidence quote\n\n"
    "Default to KEEP. Only null when the mismatch is obvious and severe.\n\n"
    "Reply with ONLY a JSON object on a single line:\n"
    "  {\"decision\": \"keep\"}  OR  {\"decision\": \"null\", \"reason\": \"<brief reason>\"}"
)


AUDIT_USER_TEMPLATE = (
    "field: {field}\n"
    "field_definition: {definition}\n"
    "extracted_value: {value}\n"
    "evidence_quote: {evidence}"
)


@dataclass
class AuditOutcome:
    decisions: dict[str, str]  # field -> "keep" | "null"
    null_reasons: dict[str, str]  # field -> reason for null
    n_calls: int
    input_tokens: int
    output_tokens: int
    cost_usd: float


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_decision(text: str) -> tuple[str, str]:
    m = _JSON_RE.search(text)
    if not m:
        return "keep", ""  # default to keep on parse failure
    try:
        d = json.loads(m.group(0))
    except Exception:
        return "keep", ""
    decision = str(d.get("decision", "keep")).lower()
    if decision not in ("keep", "null"):
        decision = "keep"
    return decision, str(d.get("reason", ""))[:200]


def audit_extractions(
    *,
    extracted: dict[str, Any],
    evidence: dict[str, str],
    client: anthropic.Anthropic,
    rai_only: bool = True,
) -> AuditOutcome:
    """Run a per-field LLM audit. Returns the keep/null decisions."""
    decisions: dict[str, str] = {}
    null_reasons: dict[str, str] = {}
    in_tok = out_tok = n_calls = 0
    targets = sorted(extracted.keys() & evidence.keys())
    if rai_only:
        targets = [f for f in targets if f in RAI_FIELDS]
    for field in targets:
        value = extracted[field]
        ev = evidence[field]
        if not ev:
            continue
        prompt = AUDIT_USER_TEMPLATE.format(
            field=field,
            definition=FIELD_DEFINITIONS.get(field, "")[:300],
            value=str(value)[:600],
            evidence=ev[:600],
        )
        try:
            r = client.messages.create(
                model=AUDIT_MODEL_ID,
                max_tokens=128,
                temperature=0,
                system=AUDIT_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception:
            decisions[field] = "keep"
            continue
        n_calls += 1
        in_tok += getattr(r.usage, "input_tokens", 0) or 0
        out_tok += getattr(r.usage, "output_tokens", 0) or 0
        text = "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
        decision, reason = _parse_decision(text)
        decisions[field] = decision
        if decision == "null":
            null_reasons[field] = reason or "audit: value not supported by evidence"
    cost = (in_tok / 1_000_000 * AUDIT_PRICE_INPUT_PER_MTOK
            + out_tok / 1_000_000 * AUDIT_PRICE_OUTPUT_PER_MTOK)
    return AuditOutcome(
        decisions=decisions,
        null_reasons=null_reasons,
        n_calls=n_calls,
        input_tokens=in_tok,
        output_tokens=out_tok,
        cost_usd=round(cost, 4),
    )
