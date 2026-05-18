"""ReAct loop driving Claude Sonnet 4.5 with tool_use.

Usage:
    result = run_agent(paper_text, client, max_turns=20)
    # result = {"extracted": {...30 fields...}, "null_reasons": {...}, "meta": {...}, "trace": [...]}
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any

import anthropic

from .schemas import CANONICAL_FIELDS, CORE_FIELDS, FIELD_DEFINITIONS, RAI_FIELDS
from .tools import TOOL_SCHEMAS, MAX_PAPER_CHARS_IN_CONTEXT, ToolState, dispatch


MODEL_ID = "claude-sonnet-4-5-20250929"
# Pricing as of 2026-Q2 for Claude Sonnet 4.5 (USD per 1M tokens).
PRICE_INPUT_PER_MTOK = 3.00
PRICE_OUTPUT_PER_MTOK = 15.00
PRICE_CACHE_WRITE_PER_MTOK = 3.75  # 1.25x input
PRICE_CACHE_READ_PER_MTOK = 0.30   # 0.1x input


# Phase 0 fix (2026-05-02 audit, decisions.md AM2): per-backbone pricing
# table for non-seed backbones. Used by run_agent when backbone_key != default.
BACKBONE_PRICES: dict = {
    "sonnet-4-5":     {"in": 3.0,  "out": 15.0,  "cache_w": 3.75, "cache_r": 0.30},
    "sonnet-4-6":     {"in": 3.0,  "out": 15.0,  "cache_w": 3.75, "cache_r": 0.30},
    "gpt-5.4":        {"in": 1.25, "out": 10.0,  "cache_w": 1.25, "cache_r": 0.0},  # OpenAI: no per-call cache pricing in same way
    "gpt-5.4-mini":   {"in": 0.15, "out": 0.60,  "cache_w": 0.15, "cache_r": 0.0},
    "gemini-3.1-pro": {"in": 1.25, "out": 10.0,  "cache_w": 1.25, "cache_r": 0.0},
}


# Anti-null-bias prefix (Fix A from V2 iteration). Variants v2, v4.
ANTI_NULL_PREFIX_FOR_REACT = """\
CRITICAL — DEFAULT TO NULL WHEN UNCERTAIN.

Many Croissant fields are rarely documented in dataset papers. If the paper
does NOT explicitly discuss a field, mark_null. Do NOT generate plausible-
sounding content. Do NOT infer from related content. EVERY non-null
extract_field call must be supported by a sentence in the paper that you
saw via search_paper or in the initial paper context.

Below is your full agent specification. Apply the rules above to it.
============================================================

"""


# Verify+correct turn (Fix C). Variants v3, v4. Appended as a final user
# message after Phase 2 ends, before Phase 3 wraps up.
VERIFY_CORRECT_TURN = """\
You have completed bulk extraction (Phase 1) and gap-filling (Phase 2).

VERIFY+CORRECT PHASE: review every field you marked null. For each null:
  - If the paper TRULY does not discuss the field, keep it null.
  - If you missed a section that discusses it, search now and extract.
  - If you extracted something but cannot point to a paper sentence
    supporting it, change it to null (do NOT keep hallucinated content).

After this verify pass, do NOT make further changes."""


def _field_definitions_block() -> str:
    core = "\n".join(f"  - {f}: {FIELD_DEFINITIONS[f]}" for f in CORE_FIELDS)
    rai = "\n".join(f"  - {f}: {FIELD_DEFINITIONS[f]}" for f in RAI_FIELDS)
    return f"CORE FIELDS (10):\n{core}\n\nRAI FIELDS (20):\n{rai}"


SYSTEM_PROMPT = f"""You are a ReAct-style autonomous agent extracting Croissant 1.1 metadata from ML dataset papers.

The paper is in your context (initial user message, between <paper>...</paper> tags). Do NOT call `read_full_paper` — it's only a no-op fallback.

You MUST work in THREE PHASES. Do not skip phases; do not restart them.

## PHASE 1 — Bulk extraction from paper alone (turn 1, ONE big turn)
Issue MANY parallel tool calls in a single response — one per field you can already decide.
- `extract_field(field, value)` for every field stated or clearly implied in the paper.
- `mark_null(field, reason)` for every field that you are already confident the paper does not discuss.
- Leave only the GENUINELY UNCERTAIN fields for Phase 2. Aim to decide 20+ of the 30 fields in this turn.

## PHASE 2 — Targeted gap-filling (turns 2–4)
For each remaining undecided field, use tools to find it — again, BATCH the calls in parallel:
- `search_paper(query)` with a specific query per missing field ("annotation platform MTurk", "license terms CC-BY", "data collection timeframe", "annotator demographics", etc.).
- `search_huggingface(name)` if license / url / publisher are still unclear and the dataset is plausibly on HuggingFace.
- After results arrive, batch the resulting `extract_field` / `mark_null` calls in the NEXT turn.

## PHASE 3 — Verification & normalization (final turn, ~5)
Polish the extracted values:
- `verify_url(url)` once per extracted URL to confirm it's live. If it's 4xx/5xx, re-extract or mark null.
- `lookup_spdx(text)` on the raw license text to get an SPDX identifier; overwrite the `license` field with the SPDX id if a match is found.

Then stop with a short text reply (no tool call).

## Hard extraction rules (DO NOT RELAX)
1. **Accuracy first.** Only extract what the paper states or what tool outputs verify. Never invent plausible-sounding values that contradict the paper.
2. **But extract what the paper DOES say.** If the paper contains content that matches a field definition, extract it — even if the paper doesn't use the exact field name. Do not refuse because "the paper doesn't call it X" when it describes X. When in doubt, prefer extracting over nulling.
3. **Null when truly absent.** If the paper genuinely does not discuss the topic, call `mark_null(field, reason)`.

**GUARDRAIL A — dataset vs method.** Every field on the 30-field schema describes the DATASET ITSELF. Do NOT extract properties of training methods, model architectures, data augmentations, evaluation protocols, or fine-tuning procedures that merely *use* the dataset. Example: if the paper proposes a training augmentation ("alternating horizontal flip") applied to CIFAR-10, that is NOT `rai:dataManipulationProtocol` for CIFAR-10 — the dataset itself wasn't changed. A paper that primarily proposes a new training method on an existing dataset will legitimately produce many nulls for that dataset's RAI fields — accept this; do not backfill from the paper's method details.

**GUARDRAIL B — no hallucinated specifics.** If you write a specific number, percentage, date range, or named entity in an extracted value, that specific detail MUST appear verbatim in the paper text (or in a tool result). If you cannot point to the exact sentence that states it, DO NOT include it. Either give a less specific true statement or mark null. Do not reconstruct plausible numbers from memory of similar papers.
4. **datePublished** = DATASET release date. If the paper was published at VENUE YEAR (e.g., "ICCV 2021", "NeurIPS 2023") and the dataset is released alongside, use that year. Year-only ("2021") is fine.
5. **citeAs** — if the paper gives authors + title + venue but no formatted citation string, CONSTRUCT one in standard format: "Author1, Author2, ... (Year). Title. Venue." Do not mark null just because no citation block is printed.
6. **creator** = named individuals if listed, else organization. Format: "Name1, Name2 (Org)".
7. **publisher** = org that released the dataset, NOT the conference venue.
8. **url** — if the paper mentions a project homepage, GitHub repo, or code/data release page for the dataset, extract it. Infer from context if needed (e.g., "available at https://github.com/X/Y" or "released on the OpenCompass platform" → the OpenCompass URL).
9. **license** — SPDX identifiers preferred (use `lookup_spdx` to normalize).
10. **isLiveDataset**: "Yes" if the paper describes active updates / versioning / live maintenance; "No" if the paper describes a fixed/static/released benchmark (this is the common case for ML benchmark papers); null ONLY if the paper gives no signal either way.
11. **rai:dataBiases** — include both (a) explicit bias acknowledgements AND (b) stated design decisions to avoid specific biases (e.g., "we used synthetic data to mitigate prior-knowledge bias"). Skip only completely generic "all datasets have biases" boilerplate.
12. **rai:dataCollectionMissingData** — includes ANY handling of gaps: cloud filtering, missing timestamps, incomplete records, unavailable observations.
13. **rai:dataImputationProtocol** — includes zero-padding, masking, sequence padding, default values, any fill-in strategy the paper describes.
14. **rai:dataManipulationProtocol** — includes augmentation, balancing, resampling, synthetic insertion (e.g., "needle" insertion at depths), temporal sampling decisions, masking schemes — any post-collection transformation.
15. **rai:machineAnnotationTools** — any ML model, tokenizer, classifier, or automated tool used anywhere in the annotation/labeling/filtering/measurement pipeline (e.g., GPT-4 tokenizer, OCR model, heuristic classifier).
16. **rai:dataReleaseMaintenancePlan** is null ~75% of the time — do not force content unless the paper actually describes versioning or updates.

## CRITICAL: Always batch tool calls in parallel
Every turn, issue as many tool calls as you can in a single response. Serial one-at-a-time behavior burns turns and causes failures.

**Good (Phase 1 example — 16 parallel calls in one turn):**
```
extract_field(name, "MMLU"), extract_field(description, "..."), extract_field(creator, "..."),
extract_field(citeAs, "..."), extract_field(datePublished, "2021"), extract_field(inLanguage, "en"),
extract_field(url, "https://github.com/hendrycks/test"), extract_field(publisher, "UC Berkeley"),
extract_field(rai:dataCollection, "..."), extract_field(rai:dataCollectionType, "Manual Human Curator"),
mark_null(isLiveDataset, "not stated"), mark_null(license, "not discussed"),
mark_null(rai:dataAnnotationPlatform, "no platform mentioned"),
mark_null(rai:annotatorDemographics, "not described"),
mark_null(rai:dataImputationProtocol, "not applicable"),
mark_null(rai:dataReleaseMaintenancePlan, "no plan described")
```

**Bad:** `extract_field(name, ...)` alone in turn 1, `extract_field(description, ...)` alone in turn 2, etc.

## 30 fields to extract
{_field_definitions_block()}

## Output discipline
- `extract_field` values must be strings (or lists/dicts only where the field genuinely needs structure).
- Never pass the string "null" / "None" / "N/A" as a value — use `mark_null` instead.
- 20-turn cap is a safety net — plan to finish in 4–6 turns.
"""


@dataclass
class AgentResult:
    extracted: dict[str, Any]
    null_reasons: dict[str, str]
    meta: dict[str, Any]
    trace: list[dict[str, Any]] = field(default_factory=list)


class AgentError(Exception):
    pass


def _strip_tool_result_cache_controls(messages: list[dict]) -> None:
    """Remove cache_control from every tool_result block across the message list.

    Called before adding a fresh cache_control to the newest user turn, so the total
    number of cache breakpoints never exceeds the Anthropic per-request limit (4).
    Because the cache is content-keyed, stripping old markers does not invalidate
    previously created cache entries — later requests still prefix-hit them.
    """
    for msg in messages:
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                block.pop("cache_control", None)


def _estimate_cost(in_tok: int, out_tok: int, cache_write: int = 0, cache_read: int = 0) -> float:
    return (
        in_tok / 1_000_000 * PRICE_INPUT_PER_MTOK
        + out_tok / 1_000_000 * PRICE_OUTPUT_PER_MTOK
        + cache_write / 1_000_000 * PRICE_CACHE_WRITE_PER_MTOK
        + cache_read / 1_000_000 * PRICE_CACHE_READ_PER_MTOK
    )


def run_agent(
    paper_text: str,
    client: anthropic.Anthropic,
    *,
    dataset_id: str | None = None,
    max_turns: int = 20,
    max_tokens: int = 8192,
    temperature: float = 0.0,
    retries: int = 3,
    trace: bool = True,
    model_id: str = MODEL_ID,
    backbone_key: str = "sonnet-4-5",
    prompt_variant: str = "v1",
) -> AgentResult:
    """Run the ReAct loop on one paper's text and return extracted metadata."""
    state = ToolState(paper_text=paper_text)
    # Paper is injected into the first user message so it lives at a stable
    # cache-prefix position from turn 1. Mark read_full_paper as already called
    # so if the agent does invoke it, it returns a short "already in context" note.
    state.read_full_paper_called = True

    paper_in_context = paper_text[:MAX_PAPER_CHARS_IN_CONTEXT]
    truncation_note = ""
    if len(paper_text) > MAX_PAPER_CHARS_IN_CONTEXT:
        truncation_note = (
            f"\n\n[Note: the full paper is {len(paper_text)} chars; only the first "
            f"{MAX_PAPER_CHARS_IN_CONTEXT} are shown above. Any content past that is still "
            "indexed by `search_paper`.]"
        )

    target_line = ""
    if dataset_id:
        target_line = (
            f"\n\n**TARGET DATASET: `{dataset_id}`**\n"
            "If the paper describes multiple related datasets (e.g. a full version + a subset, "
            "or multiple variants), extract metadata ONLY for the variant identified above. "
            "The dataset id often hints at the target (e.g. 'FOMO60K' = the 60K-scan subset, "
            "'SWE-bench_Verified' = the Verified variant, 'MMLU-Pro' = the Pro version).\n"
        )

    messages: list[dict] = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "Extract the 30 Croissant metadata fields from the paper below. "
                        "Work through the fields and call `extract_field` / `mark_null` for each. "
                        "Use `search_paper` for targeted lookups (it indexes the full paper, "
                        "including any content beyond the excerpt shown here)."
                        f"{target_line}\n\n"
                        "<paper>\n"
                        f"{paper_in_context}"
                        f"\n</paper>{truncation_note}"
                    ),
                    "cache_control": {"type": "ephemeral"},
                }
            ],
        }
    ]

    total_in_tok = 0
    total_out_tok = 0
    total_cache_write = 0
    total_cache_read = 0
    trace_log: list[dict[str, Any]] = []
    turns = 0
    stop_reason = None
    response_model: str | None = None

    # Cache the (large, constant) system prompt across turns + across papers.
    # Variants v2/v4 prepend the anti-null-bias guard (Fix A).
    effective_system = (
        ANTI_NULL_PREFIX_FOR_REACT + SYSTEM_PROMPT
        if prompt_variant in ("v2", "v4") else SYSTEM_PROMPT
    )
    system_blocks = [{
        "type": "text",
        "text": effective_system,
        "cache_control": {"type": "ephemeral"},
    }]

    while turns < max_turns:
        turns += 1

        # Retry wrapper around the Claude API call
        last_err = None
        for attempt in range(retries):
            try:
                resp = client.messages.create(
                    model=model_id,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system_blocks,
                    tools=TOOL_SCHEMAS,
                    messages=messages,
                )
                break
            except (anthropic.APIError, anthropic.APIStatusError) as e:
                last_err = e
                sleep = 2.0 ** attempt
                time.sleep(sleep)
        else:
            raise AgentError(f"Claude API failed after {retries} retries: {last_err}") from last_err

        response_model = resp.model
        total_in_tok += resp.usage.input_tokens
        total_out_tok += resp.usage.output_tokens
        total_cache_write += getattr(resp.usage, "cache_creation_input_tokens", None) or 0
        total_cache_read += getattr(resp.usage, "cache_read_input_tokens", None) or 0
        stop_reason = resp.stop_reason

        # Append the assistant turn verbatim (required for follow-up tool_result blocks)
        messages.append({"role": "assistant", "content": resp.content})

        if trace:
            turn_record = {
                "turn": turns,
                "stop_reason": stop_reason,
                "input_tokens": resp.usage.input_tokens,
                "output_tokens": resp.usage.output_tokens,
                "blocks": [],
            }

        if stop_reason != "tool_use":
            # Agent has stopped (either end_turn or a safety stop).
            if trace:
                for block in resp.content:
                    if getattr(block, "type", None) == "text":
                        turn_record["blocks"].append({"type": "text", "text": block.text})
                trace_log.append(turn_record)
            break

        # Execute each tool_use block the model emitted
        tool_results: list[dict] = []
        for block in resp.content:
            btype = getattr(block, "type", None)
            if btype == "text" and trace:
                turn_record["blocks"].append({"type": "text", "text": block.text})
            elif btype == "tool_use":
                tool_input = block.input if isinstance(block.input, dict) else {}
                output_str = dispatch(state, block.name, tool_input)
                tr_block: dict[str, Any] = {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": output_str,
                }
                tool_results.append(tr_block)
                if trace:
                    turn_record["blocks"].append({
                        "type": "tool_use",
                        "name": block.name,
                        "input": tool_input,
                        "output_preview": output_str[:400],
                    })

        if trace:
            trace_log.append(turn_record)

        # Rolling cache checkpoint: mark the most-recent tool_result block, strip older markers
        # so we stay well under Anthropic's 4-checkpoint-per-request limit.
        _strip_tool_result_cache_controls(messages)
        if tool_results:
            tool_results[-1]["cache_control"] = {"type": "ephemeral"}
        messages.append({"role": "user", "content": tool_results})

        if len(state.fields_decided()) >= 30:
            # Let the model see the last tool_result, then finish next turn
            # (don't break here — model should output a terminating text message)
            pass

    # Assemble the final extraction: start from all-None, overlay extracted + null_reasons.
    final: dict[str, Any] = {f: None for f in sorted(CANONICAL_FIELDS)}
    for f, v in state.extracted.items():
        final[f] = v
    # Anything marked null is already None by default; no-op.

    meta = {
        "model": response_model or MODEL_ID,
        "num_turns": turns,
        "num_tool_calls": sum(state.tool_call_counts.values()),
        "tool_call_counts": dict(state.tool_call_counts),
        "total_input_tokens": total_in_tok,
        "total_output_tokens": total_out_tok,
        "cache_creation_input_tokens": total_cache_write,
        "cache_read_input_tokens": total_cache_read,
        "cost_usd": round(_estimate_cost(total_in_tok, total_out_tok, total_cache_write, total_cache_read), 4),
        "stop_reason": stop_reason,
        "hit_turn_cap": turns >= max_turns and stop_reason == "tool_use",
        "fields_decided": len(state.fields_decided()),
    }

    return AgentResult(
        extracted=final,
        null_reasons=dict(state.null_reasons),
        meta=meta,
        trace=trace_log if trace else [],
    )
